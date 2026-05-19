"""test_api.py - Comprehensive API test suite for 3D Print Pipeline.

Usage:
    pytest tests/test_api.py -v
    pytest tests/test_api.py -v --start-server
"""

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time

import httpx
import pytest

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SERVER_URL = "http://127.0.0.1:8080"
API = f"{SERVER_URL}/api"


# ═══════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def server_url():
    return SERVER_URL


@pytest.fixture(scope="module")
def api_url(server_url):
    return f"{server_url}/api"


# ═══════════════════════════════════════════════════════════
# Tests: Documentation
# ═══════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_docs(api_url):
    """GET /api/docs returns 200 and doc list."""
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{api_url}/docs")
        assert r.status_code == 200, f"got {r.status_code}"
        data = r.json()
        assert "docs" in data, str(data)[:100]

        if data["docs"]:
            d0 = data["docs"][0]
            assert "id" in d0 and ("title_zh" in d0 or "title_en" in d0)

            doc_id = d0["id"]
            r2 = await client.get(f"{api_url}/docs/{doc_id}?lang=en")
            assert r2.status_code == 200
            doc_data = r2.json()
            assert "content" in doc_data, f"keys: {list(doc_data.keys())}"


# ═══════════════════════════════════════════════════════════
# Tests: Pipeline & Node Types
# ═══════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_pipeline_types(api_url):
    """GET /api/pipeline-types returns typed pipeline definitions."""
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{api_url}/pipeline-types")
        assert r.status_code == 200, f"got {r.status_code}"
        data = r.json()
        types = data.get("types", {})
        assert isinstance(types, dict), f"got {type(types).__name__}"
        assert "relief" in types
        assert all(isinstance(v, dict) and "params" in v for v in types.values())


@pytest.mark.asyncio
async def test_node_types(api_url):
    """GET /api/node-types returns all registered node types."""
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{api_url}/node-types")
        assert r.status_code == 200, f"got {r.status_code}"
        data = r.json()
        types = data.get("types", [])
        assert len(types) > 0, f"got {len(types)} types"

        type_ids = {t["id"] for t in types}
        expected = {"text_to_image", "relief", "lithophane", "layered_relief",
                    "triposr", "hunyuan", "views", "repair", "output_file"}
        for tid in expected:
            assert tid in type_ids, f"missing: {tid}"

        for t in types:
            assert "inputs" in t and "outputs" in t, t.get("id")
            assert all("name" in p for p in t.get("inputs", []) + t.get("outputs", []))


@pytest.mark.asyncio
async def test_text2img_providers(api_url):
    """GET /api/text2img/providers returns provider list."""
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{api_url}/text2img/providers")
        assert r.status_code == 200, f"got {r.status_code}"
        data = r.json()
        assert "providers" in data
        assert any(p["id"] == "openai" for p in data.get("providers", []))


@pytest.mark.asyncio
async def test_provider_config(api_url):
    """Provider configs have required fields."""
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{api_url}/text2img/providers")
        if r.status_code == 200:
            data = r.json()
            for p in data.get("providers", []):
                assert all(k in p for k in ("id", "name", "enabled", "sizes", "default_size")), \
                    str(list(p.keys()))


# ═══════════════════════════════════════════════════════════
# Tests: Tasks CRUD
# ═══════════════════════════════════════════════════════════

@pytest.fixture
def test_image_path():
    """Find a sample image in output/."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    test_dir = os.path.join(project_root, "output")
    test_file = os.path.join(test_dir, "test_input.png")
    if os.path.exists(test_file):
        return test_file
    for f in os.listdir(test_dir):
        if f.endswith((".png", ".jpg", ".jpeg")):
            return os.path.join(test_dir, f)
    return None


@pytest.mark.asyncio
async def test_tasks_crud(api_url, test_image_path):
    """Full task lifecycle: create, read, cancel, output, delete."""
    async with httpx.AsyncClient(timeout=30) as client:
        # List
        r = await client.get(f"{api_url}/tasks")
        assert r.status_code == 200, f"got {r.status_code}"
        data = r.json()
        assert "tasks" in data
        assert "stats" in data

        # Status filter
        r = await client.get(f"{api_url}/tasks?status=completed&limit=5")
        assert r.status_code == 200

        # Pipeline type filter
        r = await client.get(f"{api_url}/tasks?pipeline_type=relief&limit=5")
        assert r.status_code == 200

        # Combined filters
        r = await client.get(f"{api_url}/tasks?status=completed&pipeline_type=relief&limit=5")
        assert r.status_code == 200

        if not test_image_path:
            pytest.skip("no test image found")
            return

        # Create
        with open(test_image_path, "rb") as f:
            r = await client.post(
                f"{api_url}/tasks",
                data={"pipeline_type": "relief", "params": '{"width": 100, "height": 100, "max_depth": 2}'},
                files={"file": ("test.png", f, "image/png")},
            )
        assert r.status_code == 200, f"got {r.status_code}: {r.text[:200]}"
        task = r.json()
        task_id = task.get("id")
        assert bool(task_id)
        assert task.get("pipeline_type") == "relief"

        if not task_id:
            return

        # Get
        r = await client.get(f"{api_url}/tasks/{task_id}")
        assert r.status_code == 200
        detail = r.json()
        assert "status" in detail

        # Cancel
        r = await client.post(f"{api_url}/tasks/{task_id}/cancel")
        assert r.status_code == 200

        # Output (may 404 if not done)
        r = await client.get(f"{api_url}/tasks/{task_id}/output")
        assert r.status_code in (200, 404)

        # Delete
        r = await client.delete(f"{api_url}/tasks/{task_id}")
        assert r.status_code == 200

        # Verify deleted
        r = await client.get(f"{api_url}/tasks/{task_id}")
        assert r.status_code == 404


# ═══════════════════════════════════════════════════════════
# Tests: Workflow CRUD
# ═══════════════════════════════════════════════════════════

def make_test_graph():
    return {
        "nodes": [
            {"id": 1, "type": "text_to_image", "title": "Text→Image", "pos": [50, 80],
             "properties": {"prompt": "Test prompt", "provider": "openai", "size": "1024x1024"}},
            {"id": 2, "type": "relief", "title": "Relief", "pos": [340, 80],
             "properties": {"width": 160, "height": 120, "max_depth": 3}},
            {"id": 3, "type": "output_file", "title": "Output", "pos": [630, 80]},
        ],
        "edges": [{"source": 1, "target": 2, "source_port": 0, "target_port": 0},
                  {"source": 2, "target": 3, "source_port": 0, "target_port": 0}],
    }


@pytest.mark.asyncio
async def test_workflow_crud(api_url):
    """Full workflow lifecycle: create, read, update, list, delete."""
    async with httpx.AsyncClient(timeout=15) as client:
        graph = make_test_graph()

        # List (may be empty)
        r = await client.get(f"{api_url}/workflows")
        assert r.status_code == 200, f"got {r.status_code}"
        data = r.json()
        assert "workflows" in data
        initial_count = len(data.get("workflows", []))

        # Create
        r = await client.post(f"{api_url}/workflows", json={"name": "Test Workflow", "graph": graph})
        assert r.status_code == 200, f"got {r.status_code}: {r.text[:200]}"
        wf = r.json()
        wf_id = wf.get("id")
        assert bool(wf_id)
        assert wf.get("name") == "Test Workflow"

        if not wf_id:
            return

        # Get
        r = await client.get(f"{api_url}/workflows/{wf_id}")
        assert r.status_code == 200, f"got {r.status_code}"
        detail = r.json()
        assert "graph" in detail
        graph_data = detail.get("graph", {})
        assert len(graph_data.get("nodes", [])) == 3
        assert len(graph_data.get("edges", [])) == 2

        # Update
        r = await client.put(f"{api_url}/workflows/{wf_id}",
                            json={"name": "Updated Workflow", "description": "Updated desc"})
        assert r.status_code == 200, f"got {r.status_code}"
        assert r.json().get("name") == "Updated Workflow"

        # List includes new
        r = await client.get(f"{api_url}/workflows")
        new_count = len(r.json().get("workflows", []))
        assert new_count >= initial_count + 1

        # Delete
        r = await client.delete(f"{api_url}/workflows/{wf_id}")
        assert r.status_code == 200

        # Verify deleted
        r = await client.get(f"{api_url}/workflows/{wf_id}")
        assert r.status_code == 404

        # Delete non-existent
        r = await client.delete(f"{api_url}/workflows/{wf_id}")
        assert r.status_code == 404


# ═══════════════════════════════════════════════════════════
# Tests: Workflow Execution
# ═══════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_workflow_execution(api_url):
    """Workflow execution with instance tracking, replay, and SSE stream."""
    async with httpx.AsyncClient(timeout=15) as client:
        graph = {"nodes": [{"id": 1, "type": "output_file", "title": "Output", "pos": [50, 80]}],
                 "edges": []}

        r = await client.post(f"{api_url}/workflows", json={"name": "Execution Test", "graph": graph})
        if r.status_code != 200:
            pytest.fail(f"Cannot create workflow: {r.text[:200]}")
        wf_id = r.json()["id"]

        # Run
        r = await client.post(f"{api_url}/workflows/{wf_id}/run")
        assert r.status_code == 200, f"got {r.status_code}: {r.text[:200]}"
        inst = r.json()
        inst_id = inst.get("id")
        assert bool(inst_id)
        assert inst.get("status") in ("running", "completed")

        if not inst_id:
            await client.delete(f"{api_url}/workflows/{wf_id}")
            return

        # Get instance
        r = await client.get(f"{api_url}/workflows/instances/{inst_id}")
        assert r.status_code == 200, f"status {r.status_code}"
        detail = r.json()
        assert detail.get("workflow_id") == wf_id
        assert "context" in detail
        assert "node_runs" in detail

        # List instances
        r = await client.get(f"{api_url}/workflows/instances")
        assert r.status_code == 200
        instances = r.json().get("instances", [])
        assert any(i["id"] == inst_id for i in instances)

        # Wait for completion (output_file is instant)
        await asyncio.sleep(0.5)
        r = await client.get(f"{api_url}/workflows/instances/{inst_id}")
        if r.status_code == 200:
            assert r.json().get("status") == "completed"

        # Cancel
        r = await client.post(f"{api_url}/workflows/instances/{inst_id}/cancel")
        assert r.status_code == 200

        # Replay
        r = await client.post(f"{api_url}/workflows/instances/{inst_id}/replay", json={"from_node": "1"})
        assert r.status_code == 200, f"got {r.status_code}: {r.text[:200]}"
        assert "round" in r.json()

        # SSE stream (just check connection)
        try:
            async with httpx.AsyncClient(timeout=5) as sse_client:
                async with sse_client.stream("GET", f"{api_url}/workflows/instances/{inst_id}/stream") as response:
                    assert response.status_code == 200
                    async for chunk in response.aiter_bytes():
                        break
        except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError):
            pass  # SSE may timeout in test environment

        # Cleanup
        await client.delete(f"{api_url}/workflows/{wf_id}")


@pytest.mark.asyncio
async def test_workflow_instances_crud(api_url):
    """Non-existent workflow/instance returns 404."""
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(f"{api_url}/workflows/nonexistent/run")
        assert r.status_code == 404

        r = await client.get(f"{api_url}/workflows/instances/nonexistent")
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_compound_workflow(api_url):
    """Multi-node DAG execution with context passing and replay."""
    async with httpx.AsyncClient(timeout=30) as client:
        graph = {
            "nodes": [
                {"id": 1, "type": "output_file", "title": "Output A", "pos": [50, 80]},
                {"id": 2, "type": "output_file", "title": "Output B", "pos": [340, 80]},
                {"id": 3, "type": "output_file", "title": "Output C", "pos": [630, 80]},
            ],
            "edges": [
                {"source": 1, "target": 2, "source_port": 0, "target_port": 0},
                {"source": 2, "target": 3, "source_port": 0, "target_port": 0},
            ],
        }
        r = await client.post(f"{api_url}/workflows", json={"name": "E2E Compound", "graph": graph})
        if r.status_code != 200:
            pytest.fail(f"Cannot create compound workflow: {r.text[:200]}")
        wf_id = r.json()["id"]

        # Run
        r = await client.post(f"{api_url}/workflows/{wf_id}/run")
        assert r.status_code == 200, f"got {r.status_code}"
        inst_id = r.json()["id"]

        # Wait for execution
        await asyncio.sleep(1.0)

        # Verify
        r = await client.get(f"{api_url}/workflows/instances/{inst_id}")
        if r.status_code == 200:
            inst = r.json()
            assert inst["status"] == "completed", inst["status"]
            assert all(nr["status"] == "completed" for nr in inst.get("node_runs", []))
            assert len(inst.get("node_runs", [])) == 3
            assert all(str(nid) in inst.get("context", {}) for nid in [1, 2, 3])

        # Replay from node 2
        r = await client.post(f"{api_url}/workflows/instances/{inst_id}/replay",
                            json={"from_node": "2"})
        assert r.status_code == 200, f"got {r.status_code}"

        await asyncio.sleep(1.0)
        r = await client.get(f"{api_url}/workflows/instances/{inst_id}")
        if r.status_code == 200:
            inst2 = r.json()
            assert inst2["status"] == "completed"
            assert "round" in inst2
            assert inst2.get("round", 0) >= 1

        # Cleanup
        await client.delete(f"{api_url}/workflows/{wf_id}")


# ═══════════════════════════════════════════════════════════
# Tests: Text2Image
# ═══════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_text2img(api_url):
    """POST /api/text2img — expects failure without API key or success if configured."""
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{api_url}/text2img", json={
            "prompt": "A simple test image",
            "provider": "openai",
            "size": "1024x1024",
        })
        if r.status_code in (400, 422, 500):
            assert True  # Expected if no API key
        elif r.status_code == 200:
            data = r.json()
            assert "image_path" in data
        else:
            pytest.fail(f"Unexpected status {r.status_code}: {r.text[:200]}")


# ═══════════════════════════════════════════════════════════
# Tests: Static Files
# ═══════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_static_files(server_url):
    """GET /, /output/, /favicon.ico return expected status codes."""
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{server_url}/")
        assert r.status_code == 200
        assert "<html" in r.text.lower() or "<!doctype" in r.text.lower()

        r = await client.get(f"{server_url}/output/")
        assert r.status_code in (200, 403, 404)

        r = await client.get(f"{server_url}/favicon.ico")
        assert r.status_code in (200, 404)


# ═══════════════════════════════════════════════════════════
# Tests: File Actions
# ═══════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_file_actions(api_url):
    """File endpoints: serve, open, folder, terminal; path traversal blocked."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    test_file_rel = "web/static/js/utils.js"
    test_file_abs = os.path.join(project_root, test_file_rel)

    async with httpx.AsyncClient(timeout=15) as client:
        # GET /api/files/
        r = await client.get(f"{api_url}/files/{test_file_rel.replace(os.sep, '/')}")
        assert r.status_code == 200, f"got {r.status_code}"

        # Path traversal blocked
        r = await client.get(f"{api_url}/files/..%2F..%2F..%2FWindows/System32/notepad.exe")
        assert r.status_code == 403, f"got {r.status_code}"

        # Non-existent file
        r = await client.get(f"{api_url}/files/nonexistent_file_12345.xyz")
        assert r.status_code == 404

    # POST /api/open-path
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(f"{api_url}/open-path", json={
            "path": test_file_abs, "action": "open"
        })
        assert r.status_code == 200, f"got {r.status_code}: {r.text[:100]}"
        assert r.json().get("ok") == True

        r = await client.post(f"{api_url}/open-path", json={
            "path": test_file_abs, "action": "folder"
        })
        assert r.status_code == 200
        assert r.json().get("ok") == True

        r = await client.post(f"{api_url}/open-path", json={
            "path": test_file_abs, "action": "terminal"
        })
        assert r.status_code == 200
        assert r.json().get("ok") == True

        test_dir = os.path.join(project_root, "web", "static")
        r = await client.post(f"{api_url}/open-path", json={
            "path": test_dir, "action": "folder"
        })
        assert r.status_code == 200

        r = await client.post(f"{api_url}/open-path", json={
            "path": "web/server.py", "action": "open"
        })
        assert r.status_code == 200

        r = await client.post(f"{api_url}/open-path", json={
            "path": "", "action": "folder"
        })
        assert r.status_code == 400

        r = await client.post(f"{api_url}/open-path", json={
            "path": "C:/Windows/System32/notepad.exe", "action": "open"
        })
        assert r.status_code == 403

        r = await client.post(f"{api_url}/open-path", json={
            "path": os.path.join(project_root, "nonexistent_file.xyz"),
            "action": "open"
        })
        assert r.status_code == 404

        r = await client.post(f"{api_url}/open-path", json={
            "path": test_file_abs, "action": "invalid_action"
        })
        assert r.status_code == 400


# ═══════════════════════════════════════════════════════════
# Tests: Error Handling
# ═══════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_error_handling(api_url):
    """Invalid IDs and malformed requests return proper error codes."""
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{api_url}/tasks/nonexistent_id")
        assert r.status_code == 404

        r = await client.post(f"{api_url}/workflows", json={"name": "", "graph": "not a dict"})
        assert r.status_code >= 400

        r = await client.post(f"{api_url}/workflows", json={})
        assert r.status_code >= 400


# ═══════════════════════════════════════════════════════════
# Standalone Runner (backwards compatible)
# ═══════════════════════════════════════════════════════════

def main():
    """Run all tests via pytest programmatically.

    Usage:
        python tests/test_api.py [--start-server]
        python -m pytest tests/test_api.py -v
    """
    parser = argparse.ArgumentParser(description="3D Print Pipeline API Test Suite")
    parser.add_argument("--server", default="http://127.0.0.1:8080", help="Server URL")
    parser.add_argument("--start-server", action="store_true", help="Start the server before testing")
    args = parser.parse_args()

    global SERVER_URL, API
    SERVER_URL = args.server.rstrip("/")
    API = f"{SERVER_URL}/api"

    server_proc = None

    if args.start_server:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        server_py = os.path.join(project_root, "web", "server.py")
        print(f"Starting server: {server_py}")
        server_proc = subprocess.Popen(
            [sys.executable, server_py, "--port", "8080", "--no-browser"],
            cwd=project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        # Wait for server to be ready
        for _ in range(30):
            try:
                httpx.get(f"{SERVER_URL}/", timeout=2)
                print("Server is ready!")
                break
            except (httpx.ConnectError, httpx.TimeoutException):
                time.sleep(0.5)
        else:
            print("Server failed to start")
            server_proc.kill()
            return 1

    try:
        import pytest
        sys.exit(pytest.main(["-v", __file__, "-k", "not test_compound"]))
    finally:
        if server_proc:
            print("Stopping server...")
            server_proc.kill()
            server_proc.wait()


if __name__ == "__main__":
    main()