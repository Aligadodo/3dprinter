"""models.py - SQLite database layer for task management."""

import sqlite3
import os
import time
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasks.db")
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            pipeline_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            display_name TEXT NOT NULL DEFAULT '',
            params_json TEXT NOT NULL DEFAULT '{}',
            input_file TEXT,
            result_json TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS output_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            file_type TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'result',
            path TEXT NOT NULL,
            created_at REAL NOT NULL,
            FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
        CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at);
        CREATE INDEX IF NOT EXISTS idx_output_task ON output_files(task_id);
    """)
    conn.commit()

    # Migrations: add columns that may not exist in older DBs
    for col, col_def in [
        ("display_name", "TEXT NOT NULL DEFAULT ''"),
        ("category", "TEXT NOT NULL DEFAULT 'result'"),
    ]:
        table = "tasks" if col == "display_name" else "output_files"
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}")
            conn.commit()
        except sqlite3.OperationalError:
            pass

    conn.close()


def make_task_dir_name(task_id: str, pipeline_type: str, input_filename: str = "") -> str:
    """Generate a structured directory name: YYYY-MM-DD-<id8>-<abbr>-<stem>.

    Example: 2026-05-10-a1b2c3d4-rlf-photo
    """
    from datetime import datetime
    date = datetime.now().strftime("%Y-%m-%d")
    short_id = task_id[:8]

    type_abbr = {
        "relief": "rlf", "lithophane": "lith", "layered_relief": "layr",
        "triposr": "tri", "hunyuan": "hun", "views": "view", "repair": "rep",
    }.get(pipeline_type, pipeline_type[:4])

    stem = ""
    if input_filename:
        stem = os.path.splitext(input_filename)[0]
        # Keep only alphanumeric, Chinese, dash, underscore; replace others with dash
        cleaned = []
        for ch in stem:
            if ch.isalnum() or ('一' <= ch <= '鿿') or ch in '_-':
                cleaned.append(ch)
            elif ch in ' .()（）':
                cleaned.append('-')
        stem = ''.join(cleaned)[:20].strip('-')
        if stem:
            stem = '-' + stem

    return f"{date}-{short_id}-{type_abbr}{stem}"


def generate_display_name(pipeline_type: str, params: dict, input_file: str = None) -> str:
    """Generate a human-readable task name from type + time + filename + key params."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Use pipeline type label directly (simple, works without schemas import)
    type_labels = {
        "relief": "浮雕", "lithophane": "夜灯", "layered_relief": "套色浮雕",
        "triposr": "TripoSR", "hunyuan": "Hunyuan3D",
        "views": "六视图", "repair": "网格修复",
    }
    label = type_labels.get(pipeline_type, pipeline_type)

    filename = os.path.basename(input_file) if input_file else ""

    key_parts = []
    if pipeline_type in ("relief", "lithophane"):
        w = params.get("width") or ""
        h = params.get("height") or ""
        if w and h:
            key_parts.append(f"{w}×{h}mm")
        d = params.get("max_depth") or ""
        if d:
            key_parts.append(f"深{d}mm")
        c = params.get("colors") or 0
        if c > 0:
            key_parts.append(f"{c}色")
    elif pipeline_type in ("triposr", "hunyuan"):
        fmt = params.get("format") or ""
        if fmt:
            key_parts.append(fmt.upper())
        res = params.get("resolution") or ""
        if res:
            key_parts.append(f"{res}px")
    elif pipeline_type == "views":
        res = params.get("resolution") or ""
        if res:
            key_parts.append(f"{res}px")
    elif pipeline_type == "layered_relief":
        c = params.get("colors") or 4
        key_parts.append(f"{c}色层")
        lh = params.get("layer_height") or ""
        if lh:
            key_parts.append(f"层高{lh}mm")
        fmt = params.get("format") or ""
        if fmt == "3mf":
            key_parts.append("3MF")
    elif pipeline_type == "repair":
        fmt = params.get("output_format") or ""
        if fmt:
            key_parts.append(fmt.upper())

    key_str = " ".join(key_parts)
    parts = [label, now]
    if filename:
        parts.append(filename)
    if key_str:
        parts.append(f"({key_str})")

    return " ".join(parts)


def create_task(task_id: str, pipeline_type: str, params: dict, input_file: str = None,
                display_name: str = "") -> dict:
    conn = get_db()
    now = time.time()
    if not display_name:
        display_name = generate_display_name(pipeline_type, params, input_file)
    conn.execute(
        "INSERT INTO tasks (id, pipeline_type, status, display_name, params_json, input_file, created_at, updated_at) VALUES (?, ?, 'queued', ?, ?, ?, ?, ?)",
        (task_id, pipeline_type, display_name, json.dumps(params), input_file, now, now)
    )
    conn.commit()
    task = dict(conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone())
    conn.close()
    return _format_task(task)


def get_task(task_id: str) -> dict | None:
    conn = get_db()
    row = conn.execute(
        "SELECT t.*, wnr.instance_id AS wf_instance_id, wnr.node_id AS wf_node_id "
        "FROM tasks t LEFT JOIN workflow_node_runs wnr ON t.id = wnr.task_id "
        "WHERE t.id = ?", (task_id,)
    ).fetchone()
    if not row:
        conn.close()
        return None
    task = dict(row)
    task["is_workflow_task"] = bool(task.pop("wf_instance_id", None))
    task["workflow_instance_id"] = task.pop("wf_instance_id", None)
    task["_wf_node_id"] = task.pop("wf_node_id", None)
    task["output_files"] = _get_output_files(conn, task_id)
    conn.close()
    return _format_task(task)


def list_tasks(status: str = None, pipeline_type: str = None, limit: int = 50, offset: int = 0) -> list[dict]:
    conn = get_db()
    base_query = (
        "SELECT t.*, wnr.instance_id AS wf_instance_id, wnr.node_id AS wf_node_id "
        "FROM tasks t LEFT JOIN workflow_node_runs wnr ON t.id = wnr.task_id"
    )
    conditions = []
    params = []
    if status:
        conditions.append("t.status = ?")
        params.append(status)
    if pipeline_type:
        conditions.append("t.pipeline_type = ?")
        params.append(pipeline_type)
    where_clause = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    order_clause = " ORDER BY t.created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    rows = conn.execute(base_query + where_clause + order_clause, params).fetchall()
    tasks = []
    for row in rows:
        task = dict(row)
        task["is_workflow_task"] = bool(task.pop("wf_instance_id", None))
        task["workflow_instance_id"] = task.pop("wf_instance_id", None)
        task["_wf_node_id"] = task.pop("wf_node_id", None)
        task["output_files"] = _get_output_files(conn, task["id"])
        tasks.append(_format_task(task))
    conn.close()
    return tasks


def update_task_status(task_id: str, status: str, result_json: dict = None):
    conn = get_db()
    now = time.time()
    if result_json:
        conn.execute(
            "UPDATE tasks SET status = ?, result_json = ?, updated_at = ? WHERE id = ?",
            (status, json.dumps(result_json), now, task_id)
        )
    else:
        conn.execute(
            "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
            (status, now, task_id)
        )
    conn.commit()
    conn.close()


def add_output_file(task_id: str, file_type: str, path: str, category: str = "result"):
    conn = get_db()
    conn.execute(
        "INSERT INTO output_files (task_id, file_type, path, category, created_at) VALUES (?, ?, ?, ?, ?)",
        (task_id, file_type, path, category, time.time())
    )
    conn.commit()
    conn.close()


def delete_task(task_id: str) -> dict | None:
    conn = get_db()
    task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not task:
        conn.close()
        return None
    result = dict(task)
    # Collect paths for cleanup
    paths = [row["path"] for row in conn.execute(
        "SELECT path FROM output_files WHERE task_id = ?", (task_id,)
    ).fetchall()]
    if result.get("input_file"):
        paths.append(result["input_file"])
    conn.execute("DELETE FROM output_files WHERE task_id = ?", (task_id,))
    conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()

    # Clean up task directory (use input_file dir as task root)
    task_dir = None
    if result.get("input_file"):
        task_dir = os.path.dirname(result["input_file"])
    if task_dir and os.path.isdir(task_dir):
        try:
            import shutil
            shutil.rmtree(task_dir, ignore_errors=True)
        except Exception:
            pass

    return _format_task(result)


def get_queue_stats() -> dict:
    conn = get_db()
    stats = {}
    for status in ("queued", "running", "completed", "failed", "cancelled"):
        count = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE status = ?", (status,)
        ).fetchone()[0]
        stats[status] = count
    conn.close()
    return stats


def _get_output_files(conn, task_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM output_files WHERE task_id = ? ORDER BY category, created_at",
        (task_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def _format_task(task: dict) -> dict:
    task["params"] = json.loads(task.get("params_json", "{}"))
    task["result"] = json.loads(task["result_json"]) if task.get("result_json") else None
    task.pop("params_json", None)
    task.pop("result_json", None)
    # Add URL for each output file
    for f in task.get("output_files", []):
        abs_path = f["path"]
        try:
            rel = os.path.relpath(abs_path, PROJECT_ROOT).replace("\\", "/")
        except ValueError:
            rel = abs_path.replace("\\", "/")
        f["url"] = "/api/files/" + rel
        f["filename"] = os.path.basename(abs_path)
    # Add input_file URL
    if task.get("input_file"):
        try:
            rel = os.path.relpath(task["input_file"], PROJECT_ROOT).replace("\\", "/")
        except ValueError:
            rel = task["input_file"].replace("\\", "/")
        task["input_file_url"] = "/api/files/" + rel
    return task
