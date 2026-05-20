"""workflow_models.py - SQLite layer for workflow definitions, instances, and node runs."""

import json
import os
import time
import uuid
import sqlite3

from web.models import get_db

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasks.db")


def init_workflow_db():
    """Create workflow tables if they don't exist. Called alongside models.init_db()."""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS workflow_definitions (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            graph_json TEXT NOT NULL,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS workflow_instances (
            id TEXT PRIMARY KEY,
            workflow_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'running',
            current_node TEXT,
            context_json TEXT DEFAULT '{}',
            round_num INTEGER DEFAULT 0,
            started_at REAL NOT NULL,
            finished_at REAL,
            FOREIGN KEY (workflow_id) REFERENCES workflow_definitions(id)
        );

        CREATE TABLE IF NOT EXISTS workflow_node_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            instance_id TEXT NOT NULL,
            node_id TEXT NOT NULL,
            task_id TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            error TEXT,
            started_at REAL,
            finished_at REAL,
            FOREIGN KEY (instance_id) REFERENCES workflow_instances(id)
        );

        CREATE INDEX IF NOT EXISTS idx_wf_instances_status ON workflow_instances(status);
        CREATE INDEX IF NOT EXISTS idx_wf_node_runs_instance ON workflow_node_runs(instance_id);
    """)
    conn.commit()

    # Migration: add round_num column if not present
    try:
        conn.execute("ALTER TABLE workflow_instances ADD COLUMN round_num INTEGER DEFAULT 0")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # column already exists

    # Migration: add error_message column
    try:
        conn.execute("ALTER TABLE workflow_instances ADD COLUMN error_message TEXT DEFAULT ''")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # column already exists

    conn.close()


# ---------------------------------------------------------------------------
# Workflow Definition CRUD
# ---------------------------------------------------------------------------

def list_workflow_definitions() -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM workflow_definitions ORDER BY updated_at DESC"
    ).fetchall()
    conn.close()
    return [_format_definition(dict(r)) for r in rows]


def get_workflow_definition(wf_id: str) -> dict | None:
    conn = get_db()
    row = conn.execute("SELECT * FROM workflow_definitions WHERE id = ?", (wf_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return _format_definition(dict(row))


def create_workflow_definition(name: str, graph_json: str, description: str = "") -> dict:
    conn = get_db()
    wf_id = uuid.uuid4().hex[:12]
    now = time.time()
    conn.execute(
        "INSERT INTO workflow_definitions (id, name, description, graph_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (wf_id, name, description, graph_json, now, now)
    )
    conn.commit()
    row = conn.execute("SELECT * FROM workflow_definitions WHERE id = ?", (wf_id,)).fetchone()
    conn.close()
    return _format_definition(dict(row))


def update_workflow_definition(wf_id: str, name: str = None, graph_json: str = None, description: str = None) -> dict | None:
    conn = get_db()
    row = conn.execute("SELECT * FROM workflow_definitions WHERE id = ?", (wf_id,)).fetchone()
    if not row:
        conn.close()
        return None
    now = time.time()
    updates = ["updated_at = ?"]
    params = [now]
    if name is not None:
        updates.append("name = ?")
        params.append(name)
    if graph_json is not None:
        updates.append("graph_json = ?")
        params.append(graph_json)
    if description is not None:
        updates.append("description = ?")
        params.append(description)
    params.append(wf_id)
    assert all(u.split(" =")[0] in {"name", "graph_json", "description", "updated_at"} for u in updates), f"illegal column in: {updates}"
    conn.execute(f"UPDATE workflow_definitions SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    row = conn.execute("SELECT * FROM workflow_definitions WHERE id = ?", (wf_id,)).fetchone()
    conn.close()
    return _format_definition(dict(row))


def delete_workflow_definition(wf_id: str) -> bool:
    conn = get_db()
    row = conn.execute("SELECT * FROM workflow_definitions WHERE id = ?", (wf_id,)).fetchone()
    if not row:
        conn.close()
        return False
    conn.execute("DELETE FROM workflow_node_runs WHERE instance_id IN (SELECT id FROM workflow_instances WHERE workflow_id = ?)", (wf_id,))
    conn.execute("DELETE FROM workflow_instances WHERE workflow_id = ?", (wf_id,))
    conn.execute("DELETE FROM workflow_definitions WHERE id = ?", (wf_id,))
    conn.commit()
    conn.close()
    return True


# ---------------------------------------------------------------------------
# Workflow Instance CRUD
# ---------------------------------------------------------------------------

def create_workflow_instance(wf_id: str, inputs: dict = None, instance_id: str = None) -> dict:
    conn = get_db()
    inst_id = instance_id or uuid.uuid4().hex[:12]
    now = time.time()
    inputs = dict(inputs or {})
    work_dir = inputs.pop("_work_dir", None)
    ctx = {"_inputs": inputs}
    if work_dir:
        ctx["_work_dir"] = work_dir
    conn.execute(
        "INSERT INTO workflow_instances (id, workflow_id, status, context_json, started_at) VALUES (?, ?, 'running', ?, ?)",
        (inst_id, wf_id, json.dumps(ctx), now)
    )
    conn.commit()
    row = conn.execute("SELECT * FROM workflow_instances WHERE id = ?", (inst_id,)).fetchone()
    conn.close()
    return _format_instance(dict(row))


def get_workflow_instance(inst_id: str) -> dict | None:
    conn = get_db()
    row = conn.execute("SELECT * FROM workflow_instances WHERE id = ?", (inst_id,)).fetchone()
    if not row:
        conn.close()
        return None
    inst = dict(row)
    inst["node_runs"] = _get_node_runs(conn, inst_id)
    _attach_node_run_outputs(conn, inst["node_runs"])
    conn.close()
    return _format_instance(inst)


def update_workflow_instance(inst_id: str, status: str = None, current_node: str = None,
                              finished_at: float = None, round_num: int = None,
                              error_message: str = None) -> dict | None:
    conn = get_db()
    row = conn.execute("SELECT * FROM workflow_instances WHERE id = ?", (inst_id,)).fetchone()
    if not row:
        conn.close()
        return None

    updates = []
    params = []
    if status is not None:
        updates.append("status = ?")
        params.append(status)
    if current_node is not None:
        updates.append("current_node = ?")
        params.append(current_node)
    if finished_at is not None:
        updates.append("finished_at = ?")
        params.append(finished_at)
    if round_num is not None:
        updates.append("round_num = ?")
        params.append(round_num)
    if error_message is not None:
        updates.append("error_message = ?")
        params.append(error_message)
    if not updates:
        conn.close()
        return _format_instance(dict(row))

    params.append(inst_id)
    assert all(u.split(" =")[0] in {"status", "current_node", "finished_at", "round_num", "error_message"} for u in updates), f"illegal column in: {updates}"
    conn.execute(f"UPDATE workflow_instances SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    row = conn.execute("SELECT * FROM workflow_instances WHERE id = ?", (inst_id,)).fetchone()
    inst = dict(row)
    inst["node_runs"] = _get_node_runs(conn, inst_id)
    conn.close()
    return _format_instance(inst)


def update_workflow_context(inst_id: str, context: dict):
    conn = get_db()
    conn.execute(
        "UPDATE workflow_instances SET context_json = ? WHERE id = ?",
        (json.dumps(context), inst_id)
    )
    conn.commit()
    conn.close()


def list_workflow_instances(limit: int = 20) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM workflow_instances ORDER BY started_at DESC LIMIT ?", (limit,)
    ).fetchall()
    result = []
    for row in rows:
        inst = dict(row)
        inst["node_runs"] = _get_node_runs(conn, inst["id"])
        result.append(_format_instance(inst))
    conn.close()
    return result


# ---------------------------------------------------------------------------
# Node Run CRUD
# ---------------------------------------------------------------------------

def create_node_run(instance_id: str, node_id: str) -> dict:
    conn = get_db()
    now = time.time()
    conn.execute(
        "INSERT INTO workflow_node_runs (instance_id, node_id, status, started_at) VALUES (?, ?, 'running', ?)",
        (instance_id, node_id, now)
    )
    conn.commit()
    row_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    row = conn.execute("SELECT * FROM workflow_node_runs WHERE id = ?", (row_id,)).fetchone()
    conn.close()
    return dict(row)


def update_node_run(node_run_id: int, status: str = None, task_id: str = None,
                    error: str = None, finished_at: float = None):
    conn = get_db()
    updates = []
    params = []
    if status is not None:
        updates.append("status = ?")
        params.append(status)
    if task_id is not None:
        updates.append("task_id = ?")
        params.append(task_id)
    if error is not None:
        updates.append("error = ?")
        params.append(error)
    if finished_at is not None:
        updates.append("finished_at = ?")
        params.append(finished_at)
    if updates:
        params.append(node_run_id)
        assert all(u.split(" =")[0] in {"status", "task_id", "error", "finished_at"} for u in updates), f"illegal column in: {updates}"
        conn.execute(f"UPDATE workflow_node_runs SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
    conn.close()


def get_node_run(node_run_id: int) -> dict | None:
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM workflow_node_runs WHERE id = ?", (node_run_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_node_runs(conn, instance_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM workflow_node_runs WHERE instance_id = ? ORDER BY id",
        (instance_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def _attach_node_run_outputs(conn, node_runs: list[dict]):
    """Attach task output_files and summary to each node_run that has a task_id."""
    for nr in node_runs:
        if not nr.get("task_id"):
            continue
        # output_files from tasks.output_files table
        nr["output_files"] = _get_task_output_files(conn, nr["task_id"])
        # Task summary (params, result, display_name)
        nr["task"] = _get_task_summary(conn, nr["task_id"])


def _get_task_output_files(conn, task_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM output_files WHERE task_id = ? ORDER BY category, created_at",
        (task_id,)
    ).fetchall()
    files = []
    for r in rows:
        f = dict(r)
        fp = f.get("path", "")
        # Derive URL from path
        if "output" in fp.replace("\\", "/"):
            f["url"] = "/api/files/output/" + fp.replace("\\", "/").split("output/", 1)[1]
        else:
            f["url"] = ""
        # Derive filename from path
        f["filename"] = fp.replace("\\", "/").split("/")[-1] if fp else ""
        files.append(f)
    return files


def _get_task_summary(conn, task_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not row:
        return None
    task = dict(row)
    task["params"] = json.loads(task.get("params_json", "{}"))
    task["result"] = json.loads(task["result_json"]) if task.get("result_json") else None
    task.pop("params_json", None)
    task.pop("result_json", None)
    return task


def _format_definition(d: dict) -> dict:
    d["graph"] = json.loads(d.get("graph_json", "{}"))
    d.pop("graph_json", None)
    return d


def _format_instance(d: dict) -> dict:
    d["context"] = json.loads(d.get("context_json", "{}"))
    d.pop("context_json", None)
    d["round"] = d.get("round_num", 0)
    return d


def get_workflow_context_for_task(task_id: str) -> dict | None:
    """Return workflow context for a task, or None if it's not a workflow task.
    Returns: {instance_id, workflow_name, node_id, node_type} or None
    """
    conn = get_db()
    row = conn.execute("""
        SELECT wnr.instance_id, wnr.node_id, wd.name AS workflow_name, wd.id AS workflow_id
        FROM workflow_node_runs wnr
        JOIN workflow_instances wi ON wnr.instance_id = wi.id
        JOIN workflow_definitions wd ON wi.workflow_id = wd.id
        WHERE wnr.task_id = ?
    """, (task_id,)).fetchone()
    conn.close()
    if not row:
        return None

    # Determine node_type from the workflow's graph
    result = {
        "instance_id": row["instance_id"],
        "node_id": row["node_id"],
        "workflow_name": row["workflow_name"],
        "workflow_id": row["workflow_id"],
        "node_type": None,
    }

    # Try to extract node_type from the graph definition
    wf = get_workflow_definition(row["workflow_id"])
    if wf and "graph" in wf:
        for node in wf["graph"].get("nodes", []):
            if str(node.get("id")) == str(row["node_id"]):
                result["node_type"] = node.get("type")
                result["node_label"] = node.get("title") or node.get("type", "")
                # Build a params dict with labels from the full spec
                params = node.get("params", {}) if isinstance(node, dict) else {}
                result["params"] = params
                break

    return result


def reset_node_runs_for_replay(conn, instance_id: str, node_ids: list[str]):
    """Reset node runs to pending for replay."""
    for nid in node_ids:
        conn.execute(
            "UPDATE workflow_node_runs SET status='pending', task_id=NULL, error=NULL, "
            "started_at=NULL, finished_at=NULL WHERE instance_id=? AND node_id=? AND status!='pending'",
            (instance_id, nid)
        )
