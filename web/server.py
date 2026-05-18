"""server.py - FastAPI web server for the 3D print pipeline UI."""

import argparse
import contextlib
import json
import os
import sys
import uuid
import time
import asyncio
import mimetypes
import platform
import shutil
import subprocess

from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

# Add project root to path for imports
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from web import models, schemas, scheduler, providers, node_types, workflow_models, workflow_engine

# ---------------------------------------------------------------------------
# Docs serving
# ---------------------------------------------------------------------------

import markdown as _md

DOCS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

TASKS_DIR = os.path.join(PROJECT_ROOT, "output", "tasks")
TEMPLATES_DIR = os.path.join(PROJECT_ROOT, "web", "templates")
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

os.makedirs(TASKS_DIR, exist_ok=True)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    models.init_db()
    workflow_models.init_workflow_db()
    scheduler.get_scheduler()
    yield
    # Shutdown
    sched = scheduler.get_scheduler()
    for task_id in list(sched.running_tasks.keys()):
        await sched.cancel(task_id)


app = FastAPI(title="3D Print Pipeline", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add cache-control for JS/CSS modules during development
@app.middleware("http")
async def add_cache_control(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/static/") and (path.endswith(".js") or path.endswith(".css")):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ---------------------------------------------------------------------------
# REST API — Tasks
# ---------------------------------------------------------------------------

@app.get("/api/tasks")
async def list_tasks(status: str = None, pipeline_type: str = None, limit: int = 50, offset: int = 0):
    tasks = models.list_tasks(status=status, pipeline_type=pipeline_type, limit=limit, offset=offset)
    stats = models.get_queue_stats()
    return {"tasks": tasks, "stats": stats}


@app.post("/api/tasks")
async def create_task(
    pipeline_type: str = Form(...),
    params: str = Form("{}"),
    file: UploadFile = File(None),
):
    # Validate pipeline type
    if pipeline_type not in schemas.PIPELINE_TYPES:
        raise HTTPException(400, f"Unknown pipeline type: {pipeline_type}")

    pt = schemas.PIPELINE_TYPES[pipeline_type]
    task_params = json.loads(params) if isinstance(params, str) else params

    # Generate task ID and create task directory
    task_id = uuid.uuid4().hex[:12]
    dir_name = models.make_task_dir_name(task_id, pipeline_type, file.filename if file else "")
    task_dir = os.path.join(TASKS_DIR, dir_name)
    os.makedirs(task_dir, exist_ok=True)

    # Save uploaded file into task directory
    input_file = None
    if file:
        ext = os.path.splitext(file.filename)[1].lower()
        if pt.get("accepts") and ext not in pt["accepts"]:
            raise HTTPException(400, f"File type {ext} not accepted. Allowed: {pt['accepts']}")
        safe_name = f"input{ext}"
        input_file = os.path.join(task_dir, safe_name)
        content = await file.read()
        with open(input_file, "wb") as f:
            f.write(content)

    if not input_file:
        raise HTTPException(400, "No input file provided")

    # Generate display name
    display_name = models.generate_display_name(pipeline_type, task_params, input_file)
    task = models.create_task(task_id, pipeline_type, task_params, input_file, display_name)

    # Submit to scheduler
    await scheduler.get_scheduler().submit(task_id, pipeline_type, task_params, input_file)

    return task


@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    task = models.get_task(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return task


@app.get("/api/tasks/{task_id}/workflow")
async def get_task_workflow_context(task_id: str):
    """Return workflow context for a task (if it belongs to one)."""
    ctx = workflow_models.get_workflow_context_for_task(task_id)
    if not ctx:
        raise HTTPException(404, "Task is not part of a workflow")
    return ctx


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str):
    # Cancel if running
    await scheduler.get_scheduler().cancel(task_id)
    task = models.delete_task(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return task


@app.post("/api/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    ok = await scheduler.get_scheduler().cancel(task_id)
    return {"cancelled": ok}


@app.post("/api/tasks/{task_id}/retry")
async def retry_task(task_id: str):
    task = models.get_task(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    if task["status"] not in ("failed", "cancelled"):
        raise HTTPException(400, "Only failed or cancelled tasks can be retried")

    # Create a new task directory and copy the input file
    new_id = uuid.uuid4().hex[:12]
    old_input = task.get("input_file")
    old_filename = os.path.basename(old_input) if old_input else ""
    dir_name = models.make_task_dir_name(new_id, task["pipeline_type"], old_filename)
    new_task_dir = os.path.join(TASKS_DIR, dir_name)
    os.makedirs(new_task_dir, exist_ok=True)

    new_input_file = None
    old_input = task.get("input_file")
    if old_input and os.path.exists(old_input):
        ext = os.path.splitext(old_input)[1]
        new_input_file = os.path.join(new_task_dir, f"input{ext}")
        shutil.copy2(old_input, new_input_file)

    display_name = models.generate_display_name(task["pipeline_type"], task["params"], new_input_file)
    new_task = models.create_task(new_id, task["pipeline_type"], task["params"], new_input_file, display_name)
    await scheduler.get_scheduler().submit(new_id, task["pipeline_type"], task["params"], new_input_file)
    return new_task


# ---------------------------------------------------------------------------
# SSE Stream
# ---------------------------------------------------------------------------

@app.get("/api/tasks/{task_id}/stream")
async def task_stream(task_id: str, request: Request):
    sched = scheduler.get_scheduler()
    queue = sched.get_event_queue(task_id)

    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=30.0)
                if msg["event"] == "done":
                    break
                yield f"event: {msg['event']}\ndata: {json.dumps(msg['data'], ensure_ascii=False)}\n\n"
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
            except Exception:
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# File Serving
# ---------------------------------------------------------------------------

@app.get("/api/files/{file_path:path}")
async def serve_file(file_path: str):
    """Serve output files (images, STL) for preview."""
    # Security: only allow paths under project root
    full_path = os.path.normpath(os.path.join(PROJECT_ROOT, file_path))
    if not full_path.startswith(os.path.normpath(PROJECT_ROOT)):
        raise HTTPException(403, "Access denied")

    if not os.path.isfile(full_path):
        raise HTTPException(404, "File not found")

    # For STL/OBJ files, return as download
    ext = os.path.splitext(full_path)[1].lower()
    if ext in (".stl", ".obj", ".glb", ".3mf"):
        return FileResponse(full_path, media_type="application/octet-stream",
                          filename=os.path.basename(full_path))

    return FileResponse(full_path)


# ---------------------------------------------------------------------------
# Local File Actions (open folder / terminal)
# ---------------------------------------------------------------------------

@app.post("/api/open-path")
async def open_path(request: Request):
    """Open a file path in the system file manager or terminal. Localhost only."""
    body = await request.json()
    path = body.get("path", "")
    action = body.get("action", "folder")  # "open" | "folder" | "terminal"

    if not path:
        raise HTTPException(400, "Missing path")

    # Security: only allow under PROJECT_ROOT
    full_path = os.path.normpath(os.path.join(PROJECT_ROOT, path)) if not os.path.isabs(path) else os.path.normpath(path)
    if not full_path.startswith(os.path.normpath(PROJECT_ROOT)):
        raise HTTPException(403, "Access denied")

    if not os.path.exists(full_path):
        raise HTTPException(404, "Path not found")

    try:
        system = platform.system()
        if action == "open":
            if system == "Windows":
                # os.startfile can block; use cmd /c start which is truly async
                subprocess.Popen(["cmd", "/c", "start", "", full_path], shell=False)
            elif system == "Darwin":
                subprocess.Popen(["open", full_path])
            else:
                subprocess.Popen(["xdg-open", full_path])
        elif action == "folder":
            folder = full_path if os.path.isdir(full_path) else os.path.dirname(full_path)
            if system == "Windows":
                if not os.path.isdir(full_path):
                    subprocess.Popen(["explorer", "/select,", full_path])
                else:
                    subprocess.Popen(["explorer", folder])
            elif system == "Darwin":
                if not os.path.isdir(full_path):
                    subprocess.Popen(["open", "-R", full_path])
                else:
                    subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
        elif action == "terminal":
            folder = full_path if os.path.isdir(full_path) else os.path.dirname(full_path)
            if system == "Windows":
                if shutil.which("wt"):
                    subprocess.Popen(["wt", "-d", folder])
                else:
                    subprocess.Popen(["cmd", "/c", "start", "cmd", "/c", f"cd /d {folder} && cmd"])
            elif system == "Darwin":
                subprocess.Popen(["open", "-a", "Terminal", folder])
            else:
                term = os.environ.get("TERMINAL", "")
                if term:
                    subprocess.Popen([term, "-e", f"cd {folder} && $SHELL"])
                else:
                    subprocess.Popen(["xdg-terminal", f"--working-directory={folder}"])
        else:
            raise HTTPException(400, f"Unknown action: {action}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Failed to open: {e}")

    return {"ok": True}


# ---------------------------------------------------------------------------
# Pipeline Info
# ---------------------------------------------------------------------------

@app.get("/api/pipeline-types")
async def pipeline_types():
    """Return available pipeline types with parameter schemas."""
    return {"types": schemas.PIPELINE_TYPES}


# ---------------------------------------------------------------------------
# Text-to-Image
# ---------------------------------------------------------------------------

@app.get("/api/text2img/providers")
async def text2img_providers():
    """List available text-to-image providers and their capabilities."""
    return {"providers": providers.list_providers()}


@app.post("/api/text2img")
async def text2img_generate(request: Request):
    """Generate an image from a text prompt."""
    body = await request.json()
    prompt = body.get("prompt", "").strip()
    if not prompt:
        raise HTTPException(400, "Missing prompt")

    provider_id = body.get("provider", "volcengine")
    size = body.get("size", "")

    prov = providers.get_provider(provider_id)
    if not prov:
        raise HTTPException(400, f"Provider '{provider_id}' not found or not enabled")

    try:
        result = await prov.generate(prompt, size)
    except Exception as e:
        raise HTTPException(500, str(e))

    return {
        "image_path": result.image_path,
        "provider": result.provider,
        "width": result.width,
        "height": result.height,
        "revised_prompt": result.revised_prompt,
    }


# ---------------------------------------------------------------------------
# Node Types
# ---------------------------------------------------------------------------

@app.get("/api/node-types")
async def get_node_types():
    """Return all registered workflow node types with port specs."""
    return {
        "types": node_types.all_node_types(),
        "categories": node_types.CATEGORIES,
    }


# ---------------------------------------------------------------------------
# Workflow Definitions
# ---------------------------------------------------------------------------

@app.get("/api/workflows")
async def list_workflows():
    """List saved workflow definitions."""
    return {"workflows": workflow_models.list_workflow_definitions()}


@app.post("/api/workflows")
async def create_workflow(request: Request):
    """Save a new workflow definition."""
    body = await request.json()
    name = body.get("name", "").strip()
    graph = body.get("graph", {})
    description = body.get("description", "")
    if not name:
        raise HTTPException(400, "Missing workflow name")
    if not graph:
        raise HTTPException(400, "Missing workflow graph")
    wf = workflow_models.create_workflow_definition(name, json.dumps(graph), description)
    return wf


# ---------------------------------------------------------------------------
# Workflow Execution — instances routes BEFORE {wf_id} to avoid path collision
# ---------------------------------------------------------------------------

@app.get("/api/workflows/instances")
async def list_workflow_instances(limit: int = 20):
    """List recent workflow instances."""
    return {"instances": workflow_models.list_workflow_instances(limit)}


@app.get("/api/workflows/instances/{inst_id}")
async def get_workflow_instance(inst_id: str):
    """Get a workflow instance with node run statuses."""
    inst = workflow_models.get_workflow_instance(inst_id)
    if not inst:
        raise HTTPException(404, "Instance not found")
    return inst


@app.get("/api/workflows/instances/{inst_id}/stream")
async def workflow_stream(inst_id: str, request: Request):
    """SSE stream for workflow execution progress."""
    engine = workflow_engine.get_engine()
    queue = engine.get_event_queue(inst_id)

    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=30.0)
                if msg["event"] == "done":
                    break
                yield f"event: {msg['event']}\ndata: {json.dumps(msg['data'], ensure_ascii=False)}\n\n"
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
            except Exception:
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@app.post("/api/workflows/instances/{inst_id}/cancel")
async def cancel_workflow(inst_id: str):
    """Cancel a running workflow instance."""
    engine = workflow_engine.get_engine()
    ok = await engine.cancel(inst_id)
    return {"cancelled": ok}


@app.post("/api/workflows/instances/{inst_id}/replay")
async def replay_workflow(inst_id: str, request: Request):
    """Replay a workflow instance from a specific node."""
    body = await request.json()
    from_node = body.get("from_node", "")

    inst = workflow_models.get_workflow_instance(inst_id)
    if not inst:
        raise HTTPException(404, "Instance not found")

    if inst["status"] not in ("completed", "failed", "cancelled"):
        raise HTTPException(400, "Can only replay from completed, failed, or cancelled instances")

    if not from_node:
        raise HTTPException(400, "Missing from_node parameter")

    engine = workflow_engine.get_engine()
    try:
        round_num = await engine.replay(inst["workflow_id"], inst_id, from_node)
        return {"ok": True, "round": round_num}
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/workflows/instances/{inst_id}/download")
async def download_workflow_outputs(inst_id: str):
    """Download all workflow instance outputs as a ZIP file."""
    import zipfile, io

    inst = workflow_models.get_workflow_instance(inst_id)
    if not inst:
        raise HTTPException(404, "Instance not found")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        added = set()
        ctx = inst.get("context", {})
        for nid, outputs in ctx.items():
            if nid.startswith("_"):
                continue
            if isinstance(outputs, dict):
                for port_name, file_path in outputs.items():
                    if not isinstance(file_path, str) or file_path in added:
                        continue
                    fp = str(file_path)
                    if os.path.isfile(fp):
                        added.add(fp)
                        arcname = f"node_{nid}/{port_name}/{os.path.basename(fp)}"
                        zf.write(fp, arcname)

        # Also include task output_files not in context
        for nr in inst.get("node_runs", []):
            for of in nr.get("output_files", []):
                fp = of.get("path", "")
                if fp and os.path.isfile(fp) and fp not in added:
                    added.add(fp)
                    arcname = f"node_{nr['node_id']}/{of.get('category','files')}/{os.path.basename(fp)}"
                    zf.write(fp, arcname)

    buf.seek(0)
    return StreamingResponse(buf, media_type="application/zip",
                             headers={"Content-Disposition": f"attachment; filename=workflow_{inst_id}.zip"})


# ---------------------------------------------------------------------------
# Workflow Definition CRUD (by ID) — keep parameterized routes AFTER specific ones
# ---------------------------------------------------------------------------

@app.get("/api/workflows/{wf_id}")
async def get_workflow(wf_id: str):
    """Get a workflow definition with graph JSON."""
    wf = workflow_models.get_workflow_definition(wf_id)
    if not wf:
        raise HTTPException(404, "Workflow not found")
    return wf


@app.put("/api/workflows/{wf_id}")
async def update_workflow(wf_id: str, request: Request):
    """Update a workflow definition."""
    body = await request.json()
    updates = {}
    if "name" in body:
        updates["name"] = body["name"].strip()
    if "graph" in body:
        updates["graph_json"] = json.dumps(body["graph"])
    if "description" in body:
        updates["description"] = body["description"]
    wf = workflow_models.update_workflow_definition(wf_id, **updates)
    if not wf:
        raise HTTPException(404, "Workflow not found")
    return wf


@app.delete("/api/workflows/{wf_id}")
async def delete_workflow(wf_id: str):
    """Delete a workflow definition and its instances."""
    ok = workflow_models.delete_workflow_definition(wf_id)
    if not ok:
        raise HTTPException(404, "Workflow not found")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Workflow Execution
# ---------------------------------------------------------------------------

@app.get("/api/workflows/{wf_id}/inputs")
async def get_workflow_inputs(wf_id: str):
    """Return the input nodes for a workflow, so the frontend can auto-generate a form."""
    wf = workflow_models.get_workflow_definition(wf_id)
    if not wf:
        raise HTTPException(404, "Workflow not found")
    graph = wf.get("graph", {})
    input_ids = node_types.get_input_node_ids(graph)
    inputs_info = []

    # Backward compat: title → node_type mapping for corrupted workflows
    title_to_type = {
        "file_input": "file_input", "File Input": "file_input", "File": "file_input",
        "text_input": "text_input", "Text Input": "text_input",
    }

    for n in graph.get("nodes", []):
        nid = str(n.get("id"))
        if nid in input_ids:
            raw_type = n.get("type", "")
            node_type_id = raw_type.replace("wf_", "", 1) if raw_type.startswith("wf_") else raw_type
            # If type is empty, try to infer from title
            if not node_type_id:
                node_type_id = title_to_type.get(n.get("title", ""), raw_type)
            nt_def = node_types.get_node_type(node_type_id)
            inputs_info.append({
                "node_id": nid,
                "node_type": node_type_id,
                "label": n.get("title", nt_def.label if nt_def else n.get("type")),
                "params": nt_def.params if nt_def else {},
                "outputs": [p.to_dict() for p in nt_def.outputs] if nt_def else [],
            })
    return {"inputs": inputs_info}


@app.post("/api/workflows/{wf_id}/run")
async def run_workflow(
    wf_id: str,
    file: UploadFile = File(None),
    inputs: str = Form("{}"),
    node_params: str = Form("{}"),
    node_inputs: str = Form("{}"),
):
    """Execute a workflow with optional file upload, text inputs, and node parameter overrides.

    - file: uploaded file (assigned to the first file_input node if not explicitly mapped)
    - inputs: JSON string of {node_id: {port_name: value}}
    - node_params: JSON string of {node_id: {param_name: value}} — runtime overrides for pipeline node params
    - node_inputs: JSON string of {target_node_id: {target_port: {source_node, source_port}}} — runtime edge overrides
    """
    wf = workflow_models.get_workflow_definition(wf_id)
    if not wf:
        raise HTTPException(404, "Workflow not found")

    graph = wf.get("graph", {})
    inputs_dict = json.loads(inputs) if isinstance(inputs, str) else (inputs or {})
    node_params_dict = json.loads(node_params) if isinstance(node_params, str) else (node_params or {})
    node_inputs_dict = json.loads(node_inputs) if isinstance(node_inputs, str) else (node_inputs or {})

    # Generate instance ID and work directory
    inst_id = uuid.uuid4().hex[:12]
    work_dir = os.path.join(TASKS_DIR, "workflows", inst_id)
    os.makedirs(work_dir, exist_ok=True)

    # Save uploaded file and assign to first file_input node
    if file and file.filename:
        safe_name = os.path.basename(file.filename)
        file_path = os.path.join(work_dir, safe_name)
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        file_input_nodes = [str(n["id"]) for n in graph.get("nodes", [])
                          if n.get("type") in ("file_input", "wf_file_input")]
        for fnid in file_input_nodes:
            if fnid not in inputs_dict or "file" not in inputs_dict.get(fnid, {}):
                inputs_dict.setdefault(fnid, {})["file"] = file_path
                break

    inputs_dict["_work_dir"] = work_dir
    inst = workflow_models.create_workflow_instance(wf_id, inputs=inputs_dict, instance_id=inst_id)

    # Store node_params at context top level so engine can access via ctx["_node_params"]
    if node_params_dict:
        inst_ctx = workflow_models.get_workflow_instance(inst_id)
        if inst_ctx:
            ctx_data = inst_ctx.get("context", {})
            ctx_data["_node_params"] = node_params_dict
            workflow_models.update_workflow_context(inst_id, ctx_data)

    # Store node_inputs (runtime edge overrides) in context for _resolve_input
    if node_inputs_dict:
        inst_ctx = workflow_models.get_workflow_instance(inst_id)
        if inst_ctx:
            ctx_data = inst_ctx.get("context", {})
            ctx_data["_node_inputs"] = node_inputs_dict
            workflow_models.update_workflow_context(inst_id, ctx_data)

    engine = workflow_engine.get_engine()
    await engine.run(wf_id, inst_id)
    return inst


# ---------------------------------------------------------------------------
# Documentation
# ---------------------------------------------------------------------------

@app.get("/api/docs")
async def list_docs():
    """List available documentation files."""
    index_path = os.path.join(DOCS_DIR, "index.json")
    if not os.path.exists(index_path):
        return {"docs": []}
    with open(index_path, "r", encoding="utf-8") as f:
        docs = json.load(f)
    return {"docs": docs}


@app.get("/api/docs/{doc_id}")
async def get_doc(doc_id: str, lang: str = "zh"):
    """Serve documentation content as HTML (rendered from Markdown)."""
    if lang not in ("zh", "en"):
        lang = "zh"
    # Block path traversal
    if ".." in doc_id or "/" in doc_id or "\\" in doc_id:
        raise HTTPException(400, "Invalid doc_id")

    md_path = os.path.normpath(os.path.join(DOCS_DIR, f"{doc_id}.{lang}.md"))
    if not md_path.startswith(os.path.normpath(DOCS_DIR)):
        raise HTTPException(403, "Access denied")
    if not os.path.exists(md_path):
        # Fallback to Chinese
        md_path = os.path.normpath(os.path.join(DOCS_DIR, f"{doc_id}.zh.md"))
        if not md_path.startswith(os.path.normpath(DOCS_DIR)):
            raise HTTPException(403, "Access denied")
    if not os.path.exists(md_path):
        raise HTTPException(404, "Document not found")

    with open(md_path, "r", encoding="utf-8") as f:
        md_content = f.read()

    html = _md.markdown(md_content, extensions=["tables", "fenced_code", "codehilite"])
    return {"content": html, "lang": lang, "doc_id": doc_id}


# ---------------------------------------------------------------------------
# Iteration records (auto-scanned from docs/iterations/)
# ---------------------------------------------------------------------------

import re as _re

ITERATIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "iterations")
PROJECT_DOCS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs")


def _parse_iteration_meta(fname, content, source="iteration", mtime=0):
    """Extract metadata from an iteration/docs markdown file.
    Returns dict with keys: title, datetime, date, summary, tags, branch, changed_files, plan_name, source
    """
    # Parse timestamp from filename: YYYY-MM-DD-HHmmss-... or use file mtime
    ts_match = _re.match(r'^(\d{4}-\d{2}-\d{2})-(\d{2})(\d{2})(\d{2})', fname)
    if ts_match:
        date_str = ts_match.group(1)
        time_str = f"{ts_match.group(2)}:{ts_match.group(3)}:{ts_match.group(4)}"
        datetime_str = f"{date_str} {time_str}"
    else:
        # For docs without timestamp prefix, use file modification time
        from datetime import datetime as _dt
        if mtime:
            dt = _dt.fromtimestamp(mtime)
            date_str = dt.strftime('%Y-%m-%d')
            time_str = dt.strftime('%H:%M:%S')
            datetime_str = dt.strftime('%Y-%m-%d %H:%M:%S')
        else:
            date_match = _re.match(r'^(\d{4}-\d{2}-\d{2})', fname)
            date_str = date_match.group(1) if date_match else fname[:10]
            time_str = ""
            datetime_str = date_str

    lines = content.split('\n')

    # Title: first H1
    title = fname
    m = _re.search(r'^#\s+(.+)$', content, _re.MULTILINE)
    if m:
        title = m.group(1).strip()

    # Extract metadata fields
    branch = ""
    plan_name = ""
    m_branch = _re.search(r'\*\*分支\*\*:\s*(.+)', content)
    if m_branch:
        branch = m_branch.group(1).strip()
    m_plan = _re.search(r'\*\*方案\*\*:\s*(.+)', content)
    if m_plan:
        plan_name = m_plan.group(1).strip()

    # Count changed files
    changed_files = 0
    m_files = _re.search(r'共修改\s*\*{0,2}(\d+)\*{0,2}\s*个文件', content)
    if m_files:
        changed_files = int(m_files.group(1))

    # Tags: auto-detect from content categories
    tags = []
    if _re.search(r'前端|frontend|\.js|\.css|\.html', content, _re.IGNORECASE):
        tags.append('frontend')
    if _re.search(r'后端|backend|\.py|server', content, _re.IGNORECASE):
        tags.append('backend')
    if _re.search(r'测试|test', content, _re.IGNORECASE) and not _re.search(r'测试', title):
        tags.append('test')
    if _re.search(r'工作流|workflow', content, _re.IGNORECASE):
        tags.append('workflow')
    if _re.search(r'修复|bugfix|fix', content, _re.IGNORECASE):
        tags.append('bugfix')
    if _re.search(r'配置|config', content, _re.IGNORECASE):
        tags.append('config')
    if '无文件变更' in content or '调研' in content or '设计阶段' in content:
        tags.append('design')
    if _re.search(r'复盘|postmortem|retrospective|回顾|复盘', content, _re.IGNORECASE):
        tags.append('postmortem')
    if _re.search(r'评估|evaluation|assessment', content, _re.IGNORECASE):
        tags.append('evaluation')
    if _re.search(r'架构|architecture|pipeline', content, _re.IGNORECASE):
        tags.append('architecture')
    if _re.search(r'指南|guide|setup|环境', content, _re.IGNORECASE):
        tags.append('guide')

    # Summary: extract first meaningful paragraph.
    # Reports have structure: H1 → **meta** lines → ## section → content
    # Skip meta lines (key: value), headings, and short labels; grab first real text.
    summary = ""
    past_meta = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Skip H1 title
        if stripped.startswith('# ') and not stripped.startswith('## '):
            past_meta = True
            continue
        # Skip metadata lines (bold key-value) and horizontal rules
        if not past_meta:
            continue
        if _re.match(r'^\*\*[^*]+\*\*:', stripped):
            continue
        if stripped.startswith('---'):
            continue
        # Skip section headings
        if stripped.startswith('## '):
            continue
        # Skip sub-headings and metadata-like patterns
        if stripped.startswith('### ') or stripped.startswith('- **'):
            continue
        # Skip "Context:" or "Summary:" labels that prefix real content
        if _re.match(r'^(Context|Summary|概述|摘要)[:：]?\s*$', stripped, _re.IGNORECASE):
            continue
        # Found real content — strip markdown prefixes
        if len(stripped) > 15:
            # Strip blockquote markers and list markers
            clean = _re.sub(r'^>\s*', '', stripped)
            clean = _re.sub(r'^[-*]\s+', '', clean)
            summary = clean[:120]
            if len(clean) > 120:
                summary += '…'
            break

    # Fallback summary from structured data if no paragraph found
    if not summary:
        parts = []
        if plan_name:
            parts.append(f"方案: {plan_name}")
        if changed_files:
            parts.append(f"修改 {changed_files} 个文件")
        if branch and branch != 'N/A':
            parts.append(f"分支: {branch}")
        summary = ' / '.join(parts) if parts else None

    return {
        "title": title,
        "datetime": datetime_str,
        "date": date_str,
        "time": time_str,
        "summary": summary,
        "tags": tags,
        "branch": branch,
        "changedFiles": changed_files,
        "planName": plan_name,
        "source": source,
    }


@app.get("/api/iterations")
async def list_iterations():
    """List all iteration records + project docs (docs/iterations/*.md + docs/*.md)"""
    items = []

    # Scan iteration records
    if os.path.isdir(ITERATIONS_DIR):
        for fname in os.listdir(ITERATIONS_DIR):
            if not fname.endswith('.md') or fname == 'INDEX.md':
                continue
            fpath = os.path.join(ITERATIONS_DIR, fname)
            mtime = os.path.getmtime(fpath)
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
            meta = _parse_iteration_meta(fname, content, source="iteration", mtime=mtime)
            meta["id"] = fname[:-3]
            meta["mtime"] = mtime
            items.append(meta)

    # Scan project docs (docs/*.md, excluding iterations/ dir)
    if os.path.isdir(PROJECT_DOCS_DIR):
        for fname in os.listdir(PROJECT_DOCS_DIR):
            if not fname.endswith('.md'):
                continue
            fpath = os.path.join(PROJECT_DOCS_DIR, fname)
            if not os.path.isfile(fpath):
                continue
            # Skip files that are in iterations/ — already scanned above
            rel = os.path.relpath(fpath, ITERATIONS_DIR) if os.path.isdir(ITERATIONS_DIR) else ""
            if rel and not rel.startswith('..'):
                continue
            mtime = os.path.getmtime(fpath)
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
            meta = _parse_iteration_meta(fname, content, source="doc", mtime=mtime)
            # Use filename as id (with path encoding for uniqueness)
            meta["id"] = fname[:-3]
            meta["mtime"] = mtime
            items.append(meta)

    # Sort newest first
    items.sort(key=lambda x: -x["mtime"])
    for item in items:
        del item["mtime"]
    return JSONResponse(content={"iterations": items})


@app.get("/api/iterations/{iter_id}", response_class=JSONResponse)
async def get_iteration(iter_id: str):
    """Render a single iteration or doc record as Markdown HTML"""
    # Block path traversal
    if ".." in iter_id or "/" in iter_id or "\\" in iter_id:
        raise HTTPException(400, "Invalid iter_id")

    safe_iters = os.path.normpath(ITERATIONS_DIR)
    safe_docs = os.path.normpath(PROJECT_DOCS_DIR)

    # Try iterations dir first, then project docs dir
    md_path = os.path.normpath(os.path.join(ITERATIONS_DIR, f"{iter_id}.md"))
    if not (md_path.startswith(safe_iters) or md_path.startswith(safe_docs)):
        raise HTTPException(403, "Access denied")
    if not os.path.exists(md_path):
        md_path = os.path.normpath(os.path.join(PROJECT_DOCS_DIR, f"{iter_id}.md"))
        if not (md_path.startswith(safe_iters) or md_path.startswith(safe_docs)):
            raise HTTPException(403, "Access denied")
    if not os.path.exists(md_path):
        raise HTTPException(404, f"Record not found: {iter_id}")
    with open(md_path, "r", encoding="utf-8") as f:
        md_content = f.read()
    html = _md.markdown(md_content, extensions=["tables", "fenced_code", "codehilite"])
    title = iter_id
    m = _re.search(r'^#\s+(.+)$', md_content, _re.MULTILINE)
    if m:
        title = m.group(1).strip()
    # Determine source from path
    source = "iteration" if ITERATIONS_DIR in os.path.dirname(md_path) else "doc"
    return JSONResponse(content={"content": html, "title": title, "id": iter_id, "source": source})


# ---------------------------------------------------------------------------
# Static Frontend
# ---------------------------------------------------------------------------

@app.get("/")
async def index(request: Request):
    # Detect language from Accept-Language header
    al = request.headers.get("accept-language", "zh")
    lang = "zh" if al.startswith("zh") else "en"
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()
        html = html.replace('<html lang="zh">', f'<html lang="{lang}">')
        return HTMLResponse(html)
    # Fallback: try old templates dir
    old_path = os.path.join(TEMPLATES_DIR, "index.html")
    if os.path.exists(old_path):
        with open(old_path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>3D Print Pipeline</h1><p>Frontend not found.</p>")


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser(description="3D Print Pipeline Web Server")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (use 0.0.0.0 for LAN)")
    parser.add_argument("--port", type=int, default=8080, help="Port number")
    parser.add_argument("--no-browser", action="store_true", help="Don't open browser on start")
    args = parser.parse_args()

    print(f"\n  3D Print Pipeline Web Server")
    print(f"  {'='*40}")
    print(f"  Local:   http://{args.host}:{args.port}")
    if args.host == "0.0.0.0":
        import socket
        local_ip = socket.gethostbyname(socket.gethostname())
        print(f"  LAN:     http://{local_ip}:{args.port}")
    print(f"  API docs: http://{args.host}:{args.port}/docs")
    print()

    if not args.no_browser and args.host in ("127.0.0.1", "localhost"):
        import webbrowser
        webbrowser.open(f"http://127.0.0.1:{args.port}")

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
