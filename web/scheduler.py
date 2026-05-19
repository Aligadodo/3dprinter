"""scheduler.py - Async task runner with GPU lock and subprocess management."""

import asyncio
import os
import sys
import json
import time
import uuid
import shutil

import web.models as models

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(SCRIPT_DIR, "scripts")
TASKS_DIR = os.path.join(SCRIPT_DIR, "output", "tasks")

os.makedirs(TASKS_DIR, exist_ok=True)


GPU_TASKS = {"triposr", "hunyuan", "views"}
CPU_MAX = 3


class TaskScheduler:
    def __init__(self):
        self.gpu_lock = asyncio.Lock()
        self.cpu_semaphore = asyncio.Semaphore(CPU_MAX)
        self.running_tasks: dict[str, asyncio.Task] = {}
        self.event_queues: dict[str, asyncio.Queue] = {}
        self.cancel_flags: dict[str, bool] = {}

    def get_event_queue(self, task_id: str) -> asyncio.Queue:
        if task_id not in self.event_queues:
            self.event_queues[task_id] = asyncio.Queue()
        return self.event_queues[task_id]

    def task_dir(self, task_id: str) -> str:
        return os.path.join(TASKS_DIR, task_id)

    async def submit(self, task_id: str, pipeline_type: str, params: dict, input_file: str = None):
        """Submit a task to the queue. Starts immediately if resources available."""
        task = asyncio.create_task(self._run_task(task_id, pipeline_type, params, input_file))
        self.running_tasks[task_id] = task
        asyncio.create_task(self._monitor_task(task_id, task))

    async def cancel(self, task_id: str):
        """Cancel a running or queued task."""
        task = models.get_task(task_id)
        if not task:
            return False
        if task["status"] == "running":
            self.cancel_flags[task_id] = True
        elif task["status"] == "queued":
            models.update_task_status(task_id, "cancelled")
            await self._emit(task_id, "cancelled", {"message": "Task cancelled"})
        return True

    async def _run_task(self, task_id: str, pipeline_type: str, params: dict, input_file: str = None):
        """Execute a pipeline task, managing GPU lock and subprocess."""
        import web.schemas as schemas

        pt = schemas.PIPELINE_TYPES.get(pipeline_type)
        if not pt:
            models.update_task_status(task_id, "failed", {"error": f"Unknown pipeline type: {pipeline_type}"})
            return

        needs_gpu = pt.get("gpu", False)

        if needs_gpu:
            await self._emit(task_id, "status", {"status": "queued", "message": f"Waiting for GPU (queued: {models.get_queue_stats().get('queued', 0)})"})
            async with self.gpu_lock:
                await self._execute(task_id, pipeline_type, pt, params, input_file)
        else:
            async with self.cpu_semaphore:
                await self._execute(task_id, pipeline_type, pt, params, input_file)

    async def _execute(self, task_id: str, pipeline_type: str, pt: dict, params: dict, input_file: str = None):
        """Run the actual subprocess."""
        if self.cancel_flags.get(task_id):
            models.update_task_status(task_id, "cancelled")
            await self._emit(task_id, "cancelled", {"message": "Task cancelled before start"})
            return

        models.update_task_status(task_id, "running")
        await self._emit(task_id, "status", {"status": "running", "message": f"Starting {pt['label']}..."})

        cmd = self._build_command(pipeline_type, pt, params, input_file)

        await self._emit(task_id, "log", {"line": f"$ {' '.join(cmd)}"})

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=SCRIPTS_DIR,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )

            stdout_lines = []
            stderr_lines = []

            async def read_stream(stream, collector):
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    text = line.decode("utf-8", errors="replace").rstrip()
                    collector.append(text)
                    # Parse progress events from script stdout
                    evt = self._parse_event_line(text)
                    if evt:
                        await self._emit(task_id, evt[0], evt[1])
                    else:
                        await self._emit(task_id, "log", {"line": text})
                    if self.cancel_flags.get(task_id):
                        proc.terminate()
                        break

            await asyncio.gather(
                read_stream(proc.stdout, stdout_lines),
                read_stream(proc.stderr, stderr_lines),
            )

            await proc.wait()

            if self.cancel_flags.get(task_id):
                models.update_task_status(task_id, "cancelled")
                await self._emit(task_id, "cancelled", {"message": "Task cancelled by user"})
                return

            stdout_text = "\n".join(stdout_lines)

            if proc.returncode != 0:
                stderr_text = "\n".join(stderr_lines)
                error_msg = stderr_text[-500:] if stderr_text else f"Exit code: {proc.returncode}"

                # Persist full stderr to task directory for debugging
                stderr_log_path = ""
                td = self.task_dir(task_id)
                try:
                    os.makedirs(td, exist_ok=True)
                    stderr_log_path = os.path.join(td, "stderr.log")
                    with open(stderr_log_path, "w", encoding="utf-8") as f:
                        f.write(stderr_text)
                except OSError:
                    stderr_log_path = ""

                error_data = {"error": error_msg, "stderr_tail": error_msg}
                if stderr_log_path:
                    error_data["stderr_log"] = stderr_log_path
                models.update_task_status(task_id, "failed", error_data)
                await self._emit(task_id, "error", {"error": error_msg, "stage": pipeline_type, "stderr_log": stderr_log_path} if stderr_log_path else {"error": error_msg, "stage": pipeline_type})
                return

            # Parse JSON result from stdout
            result = self._parse_result(stdout_text)
            if not result:
                models.update_task_status(task_id, "failed", {"error": "Could not parse result JSON", "stdout": stdout_text[-500:]})
                await self._emit(task_id, "error", {"error": "Could not parse result JSON"})
                return

            # Collect output files with categories
            self._collect_output_files(task_id, result, pipeline_type, input_file)

            # Register input file
            if input_file and os.path.exists(input_file):
                models.add_output_file(task_id, os.path.splitext(input_file)[1].lower(), input_file, "input")

            models.update_task_status(task_id, "completed", result)
            await self._emit(task_id, "complete", result)

        except Exception as e:
            models.update_task_status(task_id, "failed", {"error": str(e)})
            await self._emit(task_id, "error", {"error": str(e)})

    def _build_command(self, pipeline_type: str, pt: dict, params: dict, input_file: str = None) -> list:
        script = pt["script"]
        cmd = [sys.executable, os.path.join(SCRIPTS_DIR, script)]

        if input_file:
            cmd.append(input_file)

        param_map = {
            "relief": {
                "width": "--width", "height": "--height", "max_depth": "--max-depth",
                "base_thickness": "--base-thickness", "detail": "--detail",
                "colors": "--colors", "pixel_spacing": "--pixel-spacing",
            },
            "lithophane": {
                "width": "--width", "height": "--height", "max_depth": "--max-depth",
                "base_thickness": "--base-thickness", "detail": "--detail",
                "colors": "--colors",
            },
            "layered_relief": {
                "width": "--width", "height": "--height", "colors": "--colors",
                "layer_height": "--layer-height", "base_thickness": "--base-thickness",
                "edge_smooth": "--edge-smooth", "pixel_spacing": "--pixel-spacing",
                "format": "--format", "printer": "--printer",
                "multi_color_mode": "--multi-color-mode",
            },
            "triposr": {
                "format": "--format", "resolution": "--resolution",
                "foreground_ratio": "--foreground-ratio",
            },
            "hunyuan": {
                "mode": "--mode", "steps": "--steps", "resolution": "--resolution",
                "seed": "--seed", "format": "--format",
            },
            "views": {
                "resolution": "--resolution",
            },
            "repair": {
                "output_format": "--output", "scale": "--scale",
            },
            "mesh_simplify": {
                "target_faces": "--target-faces", "method": "--method",
            },
            "mesh_smooth": {
                "iterations": "--iterations", "lambda": "--lambda", "mu": "--mu",
            },
            "mesh_scale": {
                "scale": "--scale", "target_width": "--target-width", "uniform": "--uniform",
            },
            "mesh_boolean": {
                "bool_op": "--op",
            },
            "mesh_stitch": {
                "stitch_smooth": "--smooth-steps",
                "stitch_lambda": "--lambda",
            },
            "mesh_cut": {
                "cut_plane_co": "--plane-co",
                "cut_plane_no": "--plane-no",
                "cut_fill": "--fill",
            },
            "mesh_decorate": {
                "deco_displacement": "--displacement",
            },
        }

        mapping = param_map.get(pipeline_type, {})
        for param_name, cli_flag in mapping.items():
            if param_name in params:
                value = params[param_name]
                if isinstance(value, bool):
                    if value:
                        cmd.append(cli_flag)
                elif value is not None and value != "":
                    cmd.append(cli_flag)
                    cmd.append(str(value))

        if pipeline_type == "triposr" and params.get("no_bg_remove"):
            cmd.append("--no-bg-remove")
        if pipeline_type == "hunyuan" and params.get("skip_bg_remove"):
            cmd.append("--skip-bg-remove")
        if pipeline_type == "lithophane":
            cmd.append("--lithophane")
        if pipeline_type == "views" and params.get("no_grid"):
            cmd.append("--no-grid")

        return cmd

    def _parse_event_line(self, line: str) -> tuple | None:
        """Parse a progress event JSON line from script stdout.
        Returns (event_type, data_dict) or None if not an event line."""
        if line.startswith('{"event"'):
            try:
                obj = json.loads(line)
                event = obj.pop("event", None)
                if event:
                    return (event, obj)
            except (json.JSONDecodeError, KeyError):
                pass
        return None

    def _parse_result(self, stdout: str) -> dict | None:
        """Parse the final result JSON from stdout, skipping progress event lines."""
        decoder = json.JSONDecoder()
        # Parse all JSON objects; return the last one without an "event" key
        best = None
        pos = 0
        while pos < len(stdout):
            try:
                obj, end = decoder.raw_decode(stdout, pos)
                if "event" not in obj:
                    best = obj
                pos = end
            except json.JSONDecodeError:
                pos += 1
        return best

    def _collect_output_files(self, task_id: str, result: dict, pipeline_type: str, input_file: str = None):
        """Scan result for output file paths and register them with categories."""
        preview_keys = ["color_preview", "grid", "preview"]
        result_keys = ["output", "stl", "colored_obj", "final_output", "repair_output",
                       "alignment_pins", "output_3mf", "color_map"]

        for key in preview_keys:
            path = result.get(key)
            if path and isinstance(path, str) and os.path.exists(path) and os.path.isfile(path):
                ext = os.path.splitext(path)[1].lower()
                cat = "result" if key == "color_map" else "preview"
                models.add_output_file(task_id, ext, path, cat)

        for key in result_keys:
            path = result.get(key)
            if path and isinstance(path, str) and os.path.exists(path) and os.path.isfile(path):
                ext = os.path.splitext(path)[1].lower()
                models.add_output_file(task_id, ext, path, "result")

        # Backwards compat: old-format per-layer STLs + assembly manifest
        for layer in result.get("layers", []):
            if isinstance(layer, dict):
                stl_path = layer.get("stl")
                if stl_path and isinstance(stl_path, str) and os.path.exists(stl_path) and os.path.isfile(stl_path):
                    models.add_output_file(task_id, ".stl", stl_path, "result")
        for layer in result.get("layers", []):
            if isinstance(layer, dict) and layer.get("stl"):
                adir = os.path.dirname(layer["stl"])
                if adir and os.path.isdir(adir):
                    for fname in sorted(os.listdir(adir)):
                        if fname.endswith("_assembly.json"):
                            fpath = os.path.join(adir, fname)
                            if os.path.isfile(fpath):
                                models.add_output_file(task_id, ".json", fpath, "result")
                            break
                    break

        dir_keys = ["views_dir"]
        for key in dir_keys:
            path = result.get(key)
            if path and isinstance(path, str) and os.path.isdir(path):
                for fname in sorted(os.listdir(path)):
                    fpath = os.path.join(path, fname)
                    if os.path.isfile(fpath):
                        ext = os.path.splitext(fname)[1].lower()
                        is_img = ext in (".png", ".jpg", ".jpeg", ".webp", ".bmp")
                        models.add_output_file(task_id, ext, fpath, "preview" if is_img else "result")

        # Sub-results from pipeline.py (generate/repair/views)
        for sub_key in ("generate", "repair", "views"):
            sub = result.get(sub_key, {})
            if isinstance(sub, dict):
                for key in ("output", "stl", "final_output"):
                    sub_path = sub.get(key)
                    if sub_path and isinstance(sub_path, str) and os.path.exists(sub_path) and os.path.isfile(sub_path):
                        ext = os.path.splitext(sub_path)[1].lower()
                        models.add_output_file(task_id, ext, sub_path, "result")
                sub_grid = sub.get("grid")
                if sub_grid and isinstance(sub_grid, str) and os.path.exists(sub_grid) and os.path.isfile(sub_grid):
                    models.add_output_file(task_id, ".png", sub_grid, "preview")

    async def _emit(self, task_id: str, event: str, data: dict):
        """Send an SSE event to the task's event queue."""
        q = self.get_event_queue(task_id)
        await q.put({"event": event, "data": data})

    async def _monitor_task(self, task_id: str, task: asyncio.Task):
        """Monitor task completion and clean up."""
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception as e:
            await self._emit(task_id, "error", {"error": str(e)})
        finally:
            try:
                await self._emit(task_id, "done", {})
            except Exception:
                pass


# Singleton instance
scheduler: TaskScheduler = None


def get_scheduler() -> TaskScheduler:
    global scheduler
    if scheduler is None:
        scheduler = TaskScheduler()
    return scheduler
