"""workflow_engine.py - DAG execution engine for workflow instances.

Runs workflow nodes in topological order, respecting dependencies.
Port connections are fully data-driven from node_types.py port specs.
Supports replay from any node, preserving upstream context.
"""

import asyncio
import json
import os
import shutil
import time
import uuid
import sys

from collections import deque

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from web import workflow_models as wm
from web import models
from web import scheduler
from web import node_types as nt
from web import providers
from web import inline_nodes
from web import dag


class WorkflowCancelledError(Exception):
    """Raised when a workflow is cancelled by user request."""
    pass


class WorkflowEngine:
    def __init__(self):
        self.event_queues: dict[str, asyncio.Queue] = {}
        self.cancel_flags: dict[str, bool] = {}
        self.running_instances: dict[str, asyncio.Task] = {}

    def get_event_queue(self, instance_id: str) -> asyncio.Queue:
        if instance_id not in self.event_queues:
            self.event_queues[instance_id] = asyncio.Queue()
        return self.event_queues[instance_id]

    async def _emit(self, instance_id: str, event: str, data: dict):
        q = self.get_event_queue(instance_id)
        await q.put({"event": event, "data": data})

    async def run(self, workflow_id: str, instance_id: str):
        inst_task = asyncio.create_task(self._execute(workflow_id, instance_id))
        self.running_instances[instance_id] = inst_task
        asyncio.create_task(self._monitor_instance(instance_id, inst_task))

    async def cancel(self, instance_id: str):
        inst = wm.get_workflow_instance(instance_id)
        if not inst:
            return False
        if inst["status"] == "running":
            self.cancel_flags[instance_id] = True
            for nr in inst.get("node_runs", []):
                if nr.get("task_id") and nr["status"] == "running":
                    await scheduler.get_scheduler().cancel(nr["task_id"])
        return True

    async def replay(self, workflow_id: str, instance_id: str, from_node: str):
        """Replay a workflow from a specific node, preserving upstream context."""
        inst = wm.get_workflow_instance(instance_id)
        if not inst:
            raise ValueError("Instance not found")

        ctx = inst.get("context", {})

        # Determine which nodes are before the replay point
        wf_def = wm.get_workflow_definition(workflow_id)
        if not wf_def:
            raise ValueError("Workflow definition not found")
        graph = wf_def["graph"]
        nodes = graph.get("nodes", [])
        edges = self._normalize_edges(graph)

        node_map = {str(n["id"]): n for n in nodes}
        adj, in_degree = self._build_dag(node_map, edges)

        # Topological sort to find execution order
        order = self._topsort(node_map, adj, in_degree)
        if from_node not in order:
            raise ValueError(f"Node {from_node} not found in workflow")

        replay_idx = order.index(from_node)

        # Nodes before the replay point — keep their context
        # Nodes at and after — clear context and re-execute
        preserved_ctx = {}
        for nid in order[:replay_idx]:
            if nid in ctx:
                preserved_ctx[nid] = ctx[nid]

        # Archive previous round outputs for nodes being replayed
        round_num = (inst.get("round", 0) or 0) + 1

        # Mark existing instance as being replayed
        wm.update_workflow_instance(instance_id, status="running", current_node=None,
                                     finished_at=None, round_num=round_num)

        # Reset node runs for nodes at and after replay point
        for nid in order[replay_idx:]:
            node_runs = inst.get("node_runs", [])
            for nr in node_runs:
                if str(nr.get("node_id")) == nid:
                    wm.update_node_run(nr["id"], status="pending", task_id=None,
                                        error=None, finished_at=None)

        # Execute from replay point
        inst_task = asyncio.create_task(
            self._execute(workflow_id, instance_id, start_node=from_node,
                          preserved_ctx=preserved_ctx, round_num=round_num)
        )
        self.running_instances[instance_id] = inst_task
        asyncio.create_task(self._monitor_instance(instance_id, inst_task))

        return round_num

    def _normalize_edges(self, graph: dict) -> list[dict]:
        return dag.normalize_edges(graph)

    def _build_dag(self, node_map, edges):
        return dag.build_dag(node_map, edges)

    def _topsort(self, node_map, adj, in_degree):
        return dag.topsort(node_map, adj, in_degree)

    def _build_port_edge_map(self, node_map, edges):
        return dag.build_port_edge_map(node_map, edges)

    def _build_upstream(self, nid, ctx, edge_map):
        return dag.build_upstream(nid, ctx, edge_map)

    def _enrich_ctx(self, nid, resolved_inputs, resolved_params, ctx, edge_map):
        return dag.enrich_ctx(nid, resolved_inputs, resolved_params, ctx, edge_map)

    def _resolve_input(self, node_id, port_name, edge_map, ctx):
        return dag.resolve_input(node_id, port_name, edge_map, ctx)

    async def _execute(self, workflow_id, instance_id, start_node=None,
                        preserved_ctx=None, round_num=0):
        """Execute a workflow instance. If start_node is set, skip nodes before it."""
        wf_def = wm.get_workflow_definition(workflow_id)
        if not wf_def:
            await self._emit(instance_id, "error", {"error": "Workflow not found"})
            wm.update_workflow_instance(instance_id, status="failed", finished_at=time.time(),
                                        error_message="Workflow not found")
            await self._emit(instance_id, "done", {})
            return

        graph = wf_def["graph"]
        nodes = graph.get("nodes", [])
        edges = self._normalize_edges(graph)

        if not nodes:
            await self._emit(instance_id, "error", {"error": "Workflow has no nodes"})
            wm.update_workflow_instance(instance_id, status="failed", finished_at=time.time(),
                                        error_message="Workflow has no nodes")
            await self._emit(instance_id, "done", {})
            return

        node_map = {str(n["id"]): n for n in nodes}
        adj, in_degree = self._build_dag(node_map, edges)
        order = self._topsort(node_map, adj, in_degree)

        if order is None:
            await self._emit(instance_id, "error", {"error": "Workflow contains a cycle"})
            wm.update_workflow_instance(instance_id, status="failed", finished_at=time.time(),
                                        error_message="Workflow contains a cycle")
            await self._emit(instance_id, "done", {})
            return

        # Build port edge map using node type definitions
        edge_map = self._build_port_edge_map(node_map, edges)

        # Validate port type compatibility across all edges
        port_errors = dag.validate_port_compatibility(node_map, edges)
        if port_errors:
            err_msg = "Port type compatibility errors:\n" + "\n".join(port_errors)
            await self._emit(instance_id, "error", {"error": err_msg})
            wm.update_workflow_instance(instance_id, status="failed", finished_at=time.time(),
                                        error_message=err_msg)
            await self._emit(instance_id, "done", {})
            return

        # Runtime context: node_id → {port_name: file_path}
        ctx = preserved_ctx or {}
        # Merge persisted context (includes _inputs, _work_dir from server)
        inst = wm.get_workflow_instance(instance_id)
        if inst:
            persisted = inst.get("context", {})
            if persisted:
                ctx.update(persisted)
        # Backward compat: older instances stored _work_dir inside _inputs
        if not ctx.get("_work_dir"):
            inputs = ctx.get("_inputs", {})
            if isinstance(inputs, dict):
                wd = inputs.get("_work_dir")
                if wd:
                    ctx["_work_dir"] = wd
        if round_num:
            ctx["_round"] = round_num

        # Determine execution list
        if start_node and start_node in order:
            exec_list = order[order.index(start_node):]
        else:
            exec_list = order

        total = len(order)
        offset = order.index(exec_list[0]) if exec_list else 0

        # Pre-create node run records for ALL nodes so they exist even if execution fails early.
        # This ensures every node in the workflow has a record regardless of early termination.
        exec_node_runs = {}  # nid -> node_run dict
        for nid in exec_list:
            nr = wm.create_node_run(instance_id, nid)
            exec_node_runs[nid] = nr

        for idx, nid in enumerate(exec_list):
            if self.cancel_flags.get(instance_id):
                # Mark remaining unstarted nodes as cancelled
                for later_nid in exec_list[idx + 1:]:
                    if later_nid in exec_node_runs:
                        wm.update_node_run(exec_node_runs[later_nid]["id"], status="cancelled",
                                            finished_at=time.time())
                wm.update_workflow_instance(instance_id, status="cancelled", finished_at=time.time())
                await self._emit(instance_id, "cancelled", {"message": "Workflow cancelled"})
                return

            node = node_map[nid]
            node_type = node.get("type", "").replace("wf_", "", 1) if node.get("type", "").startswith("wf_") else node.get("type", "")
            nt_def = nt.get_node_type(node_type)
            # LiteGraph serializes configured values under "properties"
            node_params = dict(node.get("params", {}))
            if not node_params:
                props = node.get("properties", {})
                if isinstance(props, dict):
                    node_params = dict(props)
            node_label = node.get("title", node_type)

            nr = exec_node_runs[nid]
            wm.update_workflow_instance(instance_id, current_node=nid)

            await self._emit(instance_id, "node_start", {
                "node_id": nid,
                "node_type": node_type,
                "label": node_label,
                "round": round_num,
                "progress": {"current": offset + idx, "total": total},
            })

            try:
                if node_type == "file_input":
                    await self._run_file_input(nid, node, node_params, ctx, instance_id, nr["id"])
                elif node_type == "text_input":
                    await self._run_text_input(nid, node, node_params, ctx, instance_id, nr["id"])
                elif node_type == "text_to_image":
                    await self._run_text2img(nid, node, node_params, edge_map, ctx, instance_id, nr["id"])
                elif node_type == "output_file":
                    await self._run_output(nid, node, edge_map, ctx, instance_id, nr["id"])
                elif node_type in nt.node_pipeline_map():
                    await self._run_pipeline(nid, node, node_type, node_params, edge_map, ctx, instance_id, nr["id"], round_num)
                elif nt_def and nt_def.inline and node_type in inline_nodes.INLINE_HANDLERS:
                    await self._run_inline(nid, node, node_type, node_params, ctx, instance_id, nr["id"], node_map, edges)
                else:
                    raise ValueError(f"Unknown node type: {node_type}")

                # Cascade: enrich context with inputs/params/upstream for downstream nodes
                self._enrich_ctx(nid, {}, node_params, ctx, edge_map)

                # Persist context immediately so task detail page can display
                # intermediate outputs even while workflow is still running
                wm.update_node_run(nr["id"], status="completed", finished_at=time.time())
                wm.update_workflow_context(instance_id, ctx)
                await self._emit(instance_id, "node_complete", {
                    "node_id": nid,
                    "node_type": node_type,
                    "outputs": ctx.get(nid, {}),
                    "round": round_num,
                })
            except WorkflowCancelledError:
                wm.update_node_run(nr["id"], status="cancelled", finished_at=time.time())
                for later_nid in exec_list[idx + 1:]:
                    if later_nid in exec_node_runs:
                        wm.update_node_run(exec_node_runs[later_nid]["id"], status="cancelled",
                                            finished_at=time.time())
                wm.update_workflow_instance(instance_id, status="cancelled", finished_at=time.time())
                await self._emit(instance_id, "cancelled", {"message": "Workflow cancelled"})
                await self._emit(instance_id, "done", {})
                return
            except Exception as e:
                error_msg = str(e)
                wm.update_node_run(nr["id"], status="failed", error=error_msg, finished_at=time.time())
                # Mark the linked task as failed if one exists (re-read from DB — run methods may have set task_id)
                nr_updated = wm.get_node_run(nr["id"])
                if nr_updated and nr_updated.get("task_id"):
                    models.update_task_status(nr_updated["task_id"], "failed", {"error": error_msg})
                # Mark remaining unstarted nodes as skipped
                for later_nid in exec_list[idx + 1:]:
                    if later_nid in exec_node_runs:
                        wm.update_node_run(exec_node_runs[later_nid]["id"], status="skipped",
                                            error="Skipped due to upstream failure", finished_at=time.time())
                await self._emit(instance_id, "node_error", {
                    "node_id": nid,
                    "node_type": node_type,
                    "error": error_msg,
                })
                wm.update_workflow_instance(instance_id, status="failed", finished_at=time.time(),
                                              error_message=error_msg)
                wm.update_workflow_context(instance_id, ctx)
                await self._emit(instance_id, "done", {})
                return

        wm.update_workflow_instance(instance_id, status="completed", current_node=None, finished_at=time.time())
        wm.update_workflow_context(instance_id, ctx)
        await self._emit(instance_id, "workflow_complete", {"context": ctx, "round": round_num})
        await self._emit(instance_id, "done", {})

    async def _run_text2img(self, nid, node, node_params, edge_map, ctx, instance_id, node_run_id):
        cascade = self._build_upstream(str(nid), ctx, edge_map)
        runtime_params = (ctx.get("_node_params", {}) or {}).get(str(nid), {})
        prompt = self._resolve_input(nid, "prompt", edge_map, ctx) or runtime_params.get("prompt") or node_params.get("prompt", "")
        if not prompt:
            raise ValueError("No prompt provided for text_to_image")

        size = runtime_params.get("size") or node_params.get("size", "2048x2048")
        provider_id = runtime_params.get("provider") or node_params.get("provider", "volcengine")

        # Create a task record so failures are visible in the dashboard
        task_id = uuid.uuid4().hex[:12]
        pipeline_type = "text_to_image"
        work_dir = ctx.get("_work_dir", scheduler.TASKS_DIR)
        dir_name = models.make_task_dir_name(task_id, pipeline_type, prompt[:30])
        task_dir = os.path.join(work_dir, dir_name) if work_dir else os.path.join(scheduler.TASKS_DIR, dir_name)
        os.makedirs(task_dir, exist_ok=True)
        display_name = f"文生图 {prompt[:40]}"
        models.create_task(task_id, pipeline_type, {"provider": provider_id, "size": size, "prompt": prompt}, "", display_name)
        wm.update_node_run(node_run_id, task_id=task_id)

        await self._emit(instance_id, "node_progress", {
            "node_id": nid, "task_id": task_id, "percent": 10,
            "message": f"Generating image with {provider_id}...",
        })

        prov = providers.get_provider(provider_id)
        if not prov:
            configs = providers.load_providers_config()
            cfg = next((c for c in configs if c["id"] == provider_id), None)
            if cfg and not cfg.get("enabled", True):
                models.update_task_status(task_id, "failed", {"error": f"Provider '{provider_id}' is disabled"})
                raise ValueError(f"Provider '{provider_id}' is disabled. Enable it in config/providers.yaml")
            if cfg and not providers.is_key_configured(cfg.get("api_key", "")):
                models.update_task_status(task_id, "failed", {"error": f"Provider '{provider_id}' API key not configured"})
                raise ValueError(f"Provider '{provider_id}' API key not configured. Set the environment variable in config/providers.yaml")
            models.update_task_status(task_id, "failed", {"error": f"Provider '{provider_id}' not available"})
            raise ValueError(f"Provider '{provider_id}' not available")

        # Validate size against provider supported sizes, fall back to default
        supported_sizes = prov.config.get("sizes", [])
        if supported_sizes and size not in supported_sizes:
            fallback = prov.default_size
            await self._emit(instance_id, "node_progress", {
                "node_id": nid, "percent": 5,
                "message": f"Size {size} not supported by {provider_id}, using {fallback}",
            })
            size = fallback

        result = await prov.generate(prompt, size)
        ctx[nid] = {"image": result.image_path, "_inputs": {"prompt": prompt}, "_params": {"size": size, "provider": provider_id}}

        models.add_output_file(task_id, "image", result.image_path, "result")
        models.update_task_status(task_id, "completed", {
            "output": result.image_path, "provider": provider_id, "size": size,
            "width": result.width, "height": result.height, "elapsed_ms": result.elapsed_ms,
        })

        await self._emit(instance_id, "node_progress", {
            "node_id": nid, "task_id": task_id, "percent": 100, "message": "Image generated",
        })

    async def _run_inline(self, nid, node, node_type, node_params, ctx, instance_id, node_run_id, node_map, edges):
        handler = inline_nodes.INLINE_HANDLERS[node_type]
        await self._emit(instance_id, "node_progress", {
            "node_id": nid, "percent": 10, "message": f"Running {node_type}...",
        })
        result = await handler(nid, node, node_params, ctx, instance_id, node_run_id, self, node_map, edges)
        # Attach cascade metadata if not set by handler
        node_data = ctx.get(str(nid), {})
        if "_inputs" not in node_data:
            node_data["_inputs"] = {}
        if "_params" not in node_data:
            node_data["_params"] = dict(node_params)
        ctx[str(nid)] = node_data
        await self._emit(instance_id, "node_progress", {
            "node_id": nid, "percent": 100, "message": f"{node_type} complete",
        })
        return result

    async def _run_file_input(self, nid, node, node_params, ctx, instance_id, node_run_id):
        inputs = ctx.get("_inputs", {}).get(nid, {})
        src_path = inputs.get("file")
        if not src_path or not os.path.exists(str(src_path)):
            raise ValueError(f"File input '{nid}': no file provided or file not found")
        work_dir = ctx.get("_work_dir", "")
        dest = os.path.join(work_dir, os.path.basename(str(src_path))) if work_dir else str(src_path)
        if str(src_path) != dest and work_dir:
            os.makedirs(work_dir, exist_ok=True)
            shutil.copy2(str(src_path), dest)
        ctx[nid] = {"file": dest, "_inputs": {"file": str(src_path)}}
        await self._emit(instance_id, "node_progress", {
            "node_id": nid, "percent": 100, "message": f"File loaded: {os.path.basename(dest)}",
        })

    async def _run_text_input(self, nid, node, node_params, ctx, instance_id, node_run_id):
        inputs = ctx.get("_inputs", {}).get(nid, {})
        text = inputs.get("text", "")
        if not text:
            raise ValueError(f"Text input '{nid}': no text provided")
        # Persist text as a downloadable .txt file
        work_dir = ctx.get("_work_dir", "")
        if work_dir:
            text_path = os.path.join(work_dir, f"prompt_{nid}.txt")
            os.makedirs(work_dir, exist_ok=True)
            with open(text_path, "w", encoding="utf-8") as f:
                f.write(text)
        ctx[nid] = {"text": text, "_inputs": {"text": text}}
        await self._emit(instance_id, "node_progress", {
            "node_id": nid, "percent": 100, "message": f"Text received ({len(text)} chars)",
        })

    async def _run_pipeline(self, nid, node, node_type, node_params, edge_map, ctx, instance_id, node_run_id, round_num=0):
        # Use node type definition to determine input port requirements
        nt_def = nt.get_node_type(node_type)
        if not nt_def:
            raise ValueError(f"No node type definition for: {node_type}")

        # Find the primary input port (first required file-type input)
        input_file = None
        resolved_port_type = None
        for port in nt_def.inputs:
            if port.type in ("image", "stl", "mesh", "file", "any"):
                val = self._resolve_input(nid, port.name, edge_map, ctx)
                if val and os.path.exists(val):
                    input_file = val
                    resolved_port_type = port.type
                    break

        if not input_file:
            raise ValueError(f"No input file for node {node_type}:{nid}")

        # Validate file extension against expected port type (warn only, don't block)
        warning = dag.validate_file_for_port(input_file, resolved_port_type)
        if warning:
            await self._emit(instance_id, "node_progress", {
                "node_id": nid, "message": f"⚠ {warning}",
            })

        pipeline_type = nt.node_pipeline_map()[node_type]

        import web.schemas as schemas
        pt = schemas.PIPELINE_TYPES.get(pipeline_type, {})
        # Priority: runtime overrides > editor properties > schema defaults
        runtime_params = (ctx.get("_node_params", {}) or {}).get(str(nid), {})
        merged_params = {}
        for pdef in pt.get("params", []):
            pname = pdef["name"]
            if pname in runtime_params:
                merged_params[pname] = runtime_params[pname]
            elif pname in node_params:
                merged_params[pname] = node_params[pname]
            elif "default" in pdef:
                merged_params[pname] = pdef["default"]

        task_id = uuid.uuid4().hex[:12]
        dir_name = models.make_task_dir_name(task_id, pipeline_type, os.path.basename(input_file))
        task_dir = os.path.join(scheduler.TASKS_DIR, dir_name)
        os.makedirs(task_dir, exist_ok=True)

        ext = os.path.splitext(input_file)[1]
        task_input = os.path.join(task_dir, f"input{ext}")
        shutil.copy2(input_file, task_input)

        display_name = models.generate_display_name(pipeline_type, merged_params, task_input)
        models.create_task(task_id, pipeline_type, merged_params, task_input, display_name)
        wm.update_node_run(node_run_id, task_id=task_id)

        sched = scheduler.get_scheduler()
        await sched.submit(task_id, pipeline_type, merged_params, task_input)

        task_queue = sched.get_event_queue(task_id)
        await self._emit(instance_id, "node_progress", {
            "node_id": nid, "task_id": task_id, "percent": 0, "message": f"Started {pipeline_type}...",
        })

        # Block until task completes; scheduler emits events on the queue
        while True:
            msg = await task_queue.get()
            if msg["event"] == "done":
                break
            if msg["event"] == "error":
                task = models.get_task(task_id)
                err = msg["data"].get("error", "")
                if task and task.get("result"):
                    err = err or task["result"].get("error", "")
                raise RuntimeError(err or "Task failed")
            if msg["event"] in ("progress", "preview", "log"):
                data = dict(msg["data"])
                data["node_id"] = nid
                data["task_id"] = task_id
                await self._emit(instance_id, f"node_{msg['event']}", data)

        task = models.get_task(task_id)
        if not task:
            raise RuntimeError(f"Task {task_id} not found after completion")
        if task["status"] == "failed":
            error = task.get("result", {}).get("error", "Task failed")
            raise RuntimeError(error)
        if task["status"] == "cancelled":
            raise WorkflowCancelledError("Task cancelled")

        # Map output files to port names using node type output definitions
        ctx[nid] = {}
        result = task.get("result", {})
        output_files = task.get("output_files", [])

        # Build extension→port_name map from node type outputs
        ext_port_map = {}
        for port in nt_def.outputs:
            exts = dag.PORT_TYPE_EXTENSIONS.get(port.type, [])
            if exts:
                for file_ext in exts:
                    ext_port_map.setdefault(file_ext, port.name)

        for of in output_files:
            path = of["path"]
            if not os.path.exists(path):
                continue
            file_ext = os.path.splitext(path)[1].lower()
            if file_ext in ext_port_map:
                port_name = ext_port_map[file_ext]
                if port_name not in ctx[nid]:
                    ctx[nid][port_name] = path
                    continue
            # Fallback: assign by first unmatched port of matching type
            for port in nt_def.outputs:
                if port.name not in ctx[nid]:
                    exts = dag.PORT_TYPE_EXTENSIONS.get(port.type, [])
                    if exts is None or file_ext in exts:
                        ctx[nid][port.name] = path
                        break

        # Supplement from result dict using node type outputs
        result_path_keys = {
            "stl": ["output", "stl", "colored_obj"],
            "3mf": ["output_3mf"],
            "color_map": ["color_map"],
            "grid": ["grid"],
            "repaired_mesh": ["final_output"],
            "mesh": ["output", "stl"],
            "preview": ["preview"],
            "views_dir": ["views_dir"],
            "color_preview": ["color_preview", "preview"],
            "swaps": ["swaps"],
        }
        for port in nt_def.outputs:
            if port.name not in ctx[nid]:
                for rk in result_path_keys.get(port.name, []):
                    val = result.get(rk)
                    if val and isinstance(val, str):
                        if port.type == "dir":
                            if os.path.isdir(val):
                                ctx[nid][port.name] = val
                        elif os.path.exists(val):
                            ctx[nid][port.name] = val
                        break

        # Attach resolved params for cascade
        ctx[nid]["_params"] = merged_params
        ctx[nid]["_inputs"] = {"file": input_file} if input_file else {}

    async def _run_output(self, nid, node, edge_map, ctx, instance_id, node_run_id):
        input_path = self._resolve_input(nid, "file", edge_map, ctx)
        if input_path:
            ctx[nid] = {"file": input_path, "_inputs": {"file": input_path}}
        else:
            ctx[nid] = {}

    async def _monitor_instance(self, instance_id: str, task: asyncio.Task):
        try:
            await task
        except asyncio.CancelledError:
            try:
                wm.update_workflow_instance(instance_id, status="cancelled",
                                            finished_at=time.time())
            except Exception:
                pass
        except Exception as e:
            error_msg = str(e)
            await self._emit(instance_id, "error", {"error": error_msg})
            try:
                wm.update_workflow_instance(instance_id, status="failed",
                                            error_message=error_msg, finished_at=time.time())
            except Exception:
                pass
        finally:
            try:
                await self._emit(instance_id, "done", {})
            except Exception:
                pass


_engine: WorkflowEngine = None


def get_engine() -> WorkflowEngine:
    global _engine
    if _engine is None:
        _engine = WorkflowEngine()
    return _engine
