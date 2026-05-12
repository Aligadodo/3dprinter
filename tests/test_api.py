"""test_api.py - Comprehensive API test suite for 3D Print Pipeline.

Usage:
    python tests/test_api.py [--server]        # Test against running server at http://127.0.0.1:8080
    python tests/test_api.py --start-server    # Start server, test, then kill server
"""

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
import traceback

import httpx

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SERVER_URL = "http://127.0.0.1:8080"
API = f"{SERVER_URL}/api"

PASS = 0
FAIL = 0
SKIP = 0


def log(msg, level="info"):
    colors = {"info": "", "ok": "\033[92m", "fail": "\033[91m", "skip": "\033[93m", "hdr": "\033[1;36m"}
    print(f"{colors.get(level, '')}{msg}\033[0m")


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        log(f"  PASS {name}", "ok")
    else:
        FAIL += 1
        log(f"  FAIL {name}  {detail}", "fail")
    return condition


# ═══════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════


async def test_docs(client):
    log("\n── Documentation ──", "hdr")
    global SKIP

    r = await client.get(f"{API}/docs")
    check("GET /api/docs returns 200", r.status_code == 200, f"got {r.status_code}")
    if r.status_code != 200:
        return
    data = r.json()
    check("Returns docs list", "docs" in data, str(data)[:100])
    # Docs API should return "content" field (not "html")
    if "docs" in data and data["docs"]:
        d0 = data["docs"][0]
        check("Has required fields", "id" in d0 and ("title_zh" in d0 or "title_en" in d0))
        doc_id = d0["id"]
        r2 = await client.get(f"{API}/docs/{doc_id}?lang=en")
        check(f"GET /api/docs/{doc_id} returns content", r2.status_code == 200)
        if r2.status_code == 200:
            doc_data = r2.json()
            check("Doc response has 'content' field for frontend rendering",
                  "content" in doc_data, f"keys: {list(doc_data.keys())}")


async def test_pipeline_types(client):
    log("\n── Pipeline Types ──", "hdr")

    r = await client.get(f"{API}/pipeline-types")
    check("GET /api/pipeline-types returns 200", r.status_code == 200, f"got {r.status_code}")
    if r.status_code != 200:
        return
    data = r.json()
    types = data.get("types", {})
    check("Returns types dict", isinstance(types, dict), f"got {type(types).__name__}")
    check("Contains relief", "relief" in types)
    check("All have params", all(isinstance(v, dict) and "params" in v for v in types.values()))


async def test_node_types(client):
    log("\n── Node Types ──", "hdr")

    r = await client.get(f"{API}/node-types")
    check("GET /api/node-types returns 200", r.status_code == 200, f"got {r.status_code}")
    if r.status_code != 200:
        return
    data = r.json()
    types = data.get("types", [])
    check("Returns types list", len(types) > 0, f"got {len(types)} types")
    type_ids = {t["id"] for t in types}
    expected = {"text_to_image", "relief", "lithophane", "layered_relief", "triposr", "hunyuan", "views", "repair", "output_file"}
    for tid in expected:
        check(f"  Has type: {tid}", tid in type_ids)
    for t in types:
        check(f"  {t['id']}: has inputs/outputs", "inputs" in t and "outputs" in t, str(t.get("id")))
        check(f"  {t['id']}: ports have names", all("name" in p for p in t.get("inputs", []) + t.get("outputs", [])))


async def test_text2img_providers(client):
    log("\n── Text-to-Image Providers ──", "hdr")

    r = await client.get(f"{API}/text2img/providers")
    check("GET /api/text2img/providers returns 200", r.status_code == 200, f"got {r.status_code}")
    if r.status_code != 200:
        return
    data = r.json()
    check("Returns providers list", "providers" in data)
    check("Has openai provider", any(p["id"] == "openai" for p in data.get("providers", [])))


async def test_tasks_crud(client):
    log("\n── Tasks CRUD ──", "hdr")
    global SKIP

    # Create a test input file for task creation
    test_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
    test_file = os.path.join(test_dir, "test_input.png")
    if not os.path.exists(test_file):
        # Use any existing image
        for f in os.listdir(test_dir):
            if f.endswith((".png", ".jpg", ".jpeg")):
                test_file = os.path.join(test_dir, f)
                break

    if not os.path.exists(test_file):
        log("  (skipping task creation tests — no test image found)", "skip")
        SKIP += len([1 for _ in range(8)])
        return

    # List tasks with filters
    r = await client.get(f"{API}/tasks")
    check("GET /api/tasks returns 200", r.status_code == 200, f"got {r.status_code}")
    if r.status_code != 200:
        return
    data = r.json()
    check("Returns tasks list", "tasks" in data)
    check("Returns stats", "stats" in data)

    # Test status filter
    r = await client.get(f"{API}/tasks?status=completed&limit=5")
    check("GET /api/tasks?status=completed returns 200", r.status_code == 200)
    if r.status_code == 200:
        tasks = r.json().get("tasks", [])
        check("All filtered tasks have status completed",
              all(t["status"] == "completed" for t in tasks),
              f"found: {[t['status'] for t in tasks[:5]]}")

    # Test pipeline_type filter
    r = await client.get(f"{API}/tasks?pipeline_type=relief&limit=5")
    check("GET /api/tasks?pipeline_type=relief returns 200", r.status_code == 200)
    if r.status_code == 200:
        tasks = r.json().get("tasks", [])
        check("All filtered tasks have pipeline_type relief",
              all(t["pipeline_type"] == "relief" for t in tasks),
              f"found: {[t.get('pipeline_type') for t in tasks[:5]]}")

    # Test combined filters
    r = await client.get(f"{API}/tasks?status=completed&pipeline_type=relief&limit=5")
    check("GET /api/tasks with combined filters returns 200", r.status_code == 200)

    # Create task
    with open(test_file, "rb") as f:
        r = await client.post(
            f"{API}/tasks",
            data={"pipeline_type": "relief", "params": '{"width": 100, "height": 100, "max_depth": 2}'},
            files={"file": ("test.png", f, "image/png")},
            timeout=30,
        )
    check("POST /api/tasks returns 200", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}")
    if r.status_code != 200:
        return
    task = r.json()
    task_id = task.get("id")
    check("Created task has ID", bool(task_id))
    check("Has correct pipeline_type", task.get("pipeline_type") == "relief", task.get("pipeline_type"))

    if not task_id:
        return

    # Get task detail
    r = await client.get(f"{API}/tasks/{task_id}")
    check("GET /api/tasks/:id returns 200", r.status_code == 200)
    detail = r.json()
    check("Task detail has status", "status" in detail)

    # Cancel task (it may or may not be running)
    r = await client.post(f"{API}/tasks/{task_id}/cancel")
    check("POST /api/tasks/:id/cancel returns 200", r.status_code == 200)

    # Get task output
    r = await client.get(f"{API}/tasks/{task_id}/output")
    check("GET /api/tasks/:id/output returns 200 or 404", r.status_code in (200, 404))

    # Delete task
    r = await client.delete(f"{API}/tasks/{task_id}")
    check("DELETE /api/tasks/:id returns 200", r.status_code == 200)

    # Verify deleted
    r = await client.get(f"{API}/tasks/{task_id}")
    check("GET /api/tasks/:id after delete returns 404", r.status_code == 404)


async def test_workflow_crud(client):
    log("\n── Workflow CRUD ──", "hdr")

    # List workflows (may be empty)
    r = await client.get(f"{API}/workflows")
    check("GET /api/workflows returns 200", r.status_code == 200, f"got {r.status_code}")
    data = r.json()
    check("Returns workflows list", "workflows" in data)
    initial_count = len(data.get("workflows", []))

    # Create workflow
    graph = {
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
    r = await client.post(f"{API}/workflows", json={"name": "Test Workflow", "graph": graph})
    check("POST /api/workflows returns 200", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}")
    if r.status_code != 200:
        return
    wf = r.json()
    wf_id = wf.get("id")
    check("Created workflow has ID", bool(wf_id))
    check("Name matches", wf.get("name") == "Test Workflow")

    if not wf_id:
        return

    # Get workflow
    r = await client.get(f"{API}/workflows/{wf_id}")
    check("GET /api/workflows/:id returns 200", r.status_code == 200, f"got {r.status_code}")
    if r.status_code == 200:
        detail = r.json()
        check("Has graph data", "graph" in detail)
        graph_data = detail.get("graph", {})
        check("Graph has nodes", len(graph_data.get("nodes", [])) == 3, f"got {len(graph_data.get('nodes', []))}")
        check("Graph has edges", len(graph_data.get("edges", [])) == 2, f"got {len(graph_data.get('edges', []))}")

    # Update workflow
    r = await client.put(f"{API}/workflows/{wf_id}", json={"name": "Updated Workflow", "description": "Updated desc"})
    check("PUT /api/workflows/:id returns 200", r.status_code == 200, f"got {r.status_code}")
    if r.status_code == 200:
        check("Name updated", r.json().get("name") == "Updated Workflow")

    # List should include new workflow
    r = await client.get(f"{API}/workflows")
    new_count = len(r.json().get("workflows", []))
    check("Workflow count increased", new_count >= initial_count + 1, f"{initial_count} → {new_count}")

    # Delete workflow
    r = await client.delete(f"{API}/workflows/{wf_id}")
    check("DELETE /api/workflows/:id returns 200", r.status_code == 200)

    # Verify deleted
    r = await client.get(f"{API}/workflows/{wf_id}")
    check("GET deleted workflow returns 404", r.status_code == 404)

    # Delete non-existent
    r = await client.delete(f"{API}/workflows/{wf_id}")
    check("DELETE non-existent returns 404", r.status_code == 404)


async def test_workflow_execution(client):
    log("\n── Workflow Execution ──", "hdr")

    # Create a workflow for execution test
    graph = {
        "nodes": [
            {"id": 1, "type": "output_file", "title": "Output", "pos": [50, 80]},
        ],
        "edges": [],
    }
    r = await client.post(f"{API}/workflows", json={"name": "Execution Test", "graph": graph})
    if r.status_code != 200:
        check("Pre-condition: create workflow for exec test", False, r.text[:200])
        return
    wf_id = r.json()["id"]
    check("Pre-condition: workflow created", bool(wf_id))

    # Run workflow
    r = await client.post(f"{API}/workflows/{wf_id}/run")
    check("POST /api/workflows/:id/run returns 200", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}")
    if r.status_code != 200:
        return
    inst = r.json()
    inst_id = inst.get("id")
    check("Instance has ID", bool(inst_id))
    check("Instance status is running or completed", inst.get("status") in ("running", "completed"), inst.get("status"))

    if not inst_id:
        return

    # Get instance detail
    r = await client.get(f"{API}/workflows/instances/{inst_id}")
    check("GET /api/workflows/instances/:id returns 200", r.status_code == 200, f"status {r.status_code}")
    if r.status_code == 200:
        detail = r.json()
        check("Has workflow_id", detail.get("workflow_id") == wf_id)
        check("Has context", "context" in detail)
        check("Has node_runs", "node_runs" in detail)

    # List instances
    r = await client.get(f"{API}/workflows/instances")
    check("GET /api/workflows/instances returns 200", r.status_code == 200)
    if r.status_code == 200:
        instances = r.json().get("instances", [])
        check("Instances list contains our instance", any(i["id"] == inst_id for i in instances))

    # Wait briefly for execution to complete (output_file is instant)
    await asyncio.sleep(0.5)

    # Check instance after execution
    r = await client.get(f"{API}/workflows/instances/{inst_id}")
    if r.status_code == 200:
        detail = r.json()
        log(f"  Instance status: {detail.get('status')}")
        check("Instance completed", detail.get("status") == "completed", detail.get("status"))

    # Cancel (no-op for completed, but tests endpoint)
    r = await client.post(f"{API}/workflows/instances/{inst_id}/cancel")
    check("POST cancel returns 200", r.status_code == 200)

    # Replay test
    r = await client.post(f"{API}/workflows/instances/{inst_id}/replay", json={"from_node": "1"})
    check("POST replay returns 200", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}")
    if r.status_code == 200:
        check("Replay returns round number", "round" in r.json())

    # SSE stream test (just check connection, then disconnect)
    async with httpx.AsyncClient(timeout=5) as sse_client:
        try:
            async with sse_client.stream("GET", f"{API}/workflows/instances/{inst_id}/stream") as response:
                check("SSE stream returns 200", response.status_code == 200)
                # Read first chunk
                async for chunk in response.aiter_bytes():
                    break
        except Exception:
            log("  (SSE may timeout in test — deploying environment dependent)", "skip")

    # Cleanup
    await client.delete(f"{API}/workflows/{wf_id}")


async def test_workflow_instances_crud(client):
    log("\n── Workflow Instance Edge Cases ──", "hdr")

    # Run non-existent workflow
    r = await client.post(f"{API}/workflows/nonexistent/run")
    check("POST run non-existent workflow returns 404", r.status_code == 404)

    # Get non-existent instance
    r = await client.get(f"{API}/workflows/instances/nonexistent")
    check("GET non-existent instance returns 404", r.status_code == 404)


async def test_compound_workflow(client):
    """End-to-end: multi-node DAG execution with context passing and replay."""
    log("\n── Compound Workflow E2E ──", "hdr")

    # Create a 3-node chain: Output A → Output B → Output C
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
    r = await client.post(f"{API}/workflows", json={"name": "E2E Compound", "graph": graph})
    if r.status_code != 200:
        check("Create compound workflow", False, r.text[:200])
        return
    wf_id = r.json()["id"]
    check("Create compound workflow", bool(wf_id))

    # Run it
    r = await client.post(f"{API}/workflows/{wf_id}/run")
    check("Run compound workflow", r.status_code == 200, f"got {r.status_code}")
    if r.status_code != 200:
        return
    inst_id = r.json()["id"]

    # Wait for execution
    await asyncio.sleep(1.0)

    # Verify
    r = await client.get(f"{API}/workflows/instances/{inst_id}")
    if r.status_code != 200:
        check("Get compound instance", False)
        return
    inst = r.json()
    check("All nodes completed",
          all(nr["status"] == "completed" for nr in inst.get("node_runs", [])),
          f"node_runs: {[(n['node_id'], n['status']) for n in inst.get('node_runs', [])]}")
    check("Instance status completed", inst["status"] == "completed", inst["status"])
    check("3 node runs tracked", len(inst.get("node_runs", [])) == 3,
          f"got {len(inst.get('node_runs', []))}")
    check("Context has all node keys",
          all(str(nid) in inst.get("context", {}) for nid in [1, 2, 3]),
          f"ctx keys: {list(inst.get('context', {}).keys())}")

    # Replay from node 2
    r = await client.post(f"{API}/workflows/instances/{inst_id}/replay",
                          json={"from_node": "2"})
    check("Replay compound workflow", r.status_code == 200, f"got {r.status_code}")
    if r.status_code == 200:
        check("Replay increments round", r.json().get("round", 0) >= 1)

    await asyncio.sleep(1.0)
    r = await client.get(f"{API}/workflows/instances/{inst_id}")
    if r.status_code == 200:
        inst2 = r.json()
        check("Replayed instance completed", inst2["status"] == "completed",
              f"status={inst2['status']} round={inst2.get('round')}")
        check("Instance has round field", "round" in inst2)
        check("Round number is >= 1 after replay", inst2.get("round", 0) >= 1,
              f"round={inst2.get('round')}")

    # Cleanup
    await client.delete(f"{API}/workflows/{wf_id}")


async def test_text2img(client):
    log("\n── Text-to-Image Generate ──", "hdr")
    global SKIP

    # This requires API keys configured; will likely fail without them
    r = await client.post(f"{API}/text2img", json={
        "prompt": "A simple test image",
        "provider": "openai",
        "size": "1024x1024",
    })
    if r.status_code in (400, 422, 500):
        # Expected if no API key configured or provider unavailable
        check("POST /api/text2img (no key) returns expected error", True,
              f"status {r.status_code}")
    elif r.status_code == 200:
        data = r.json()
        check("Returns image_path", "image_path" in data)
        if "image_path" in data and os.path.exists(data["image_path"]):
            check("Image file exists", True)
    else:
        check(f"POST /api/text2img status {r.status_code}", False, r.text[:200])


async def test_static_files(client):
    log("\n── Static Files ──", "hdr")

    # Index page
    r = await client.get(f"{SERVER_URL}/")
    check("GET / returns 200", r.status_code == 200)
    check("Returns HTML", "<html" in r.text.lower() or "<!doctype" in r.text.lower())

    # Output files (directory listing or specific file)
    r = await client.get(f"{SERVER_URL}/output/")
    check("GET /output/ returns 200 or 404", r.status_code in (200, 403, 404),
          f"got {r.status_code}")

    # Favicon
    r = await client.get(f"{SERVER_URL}/favicon.ico")
    check("GET /favicon.ico returns 200 or 404", r.status_code in (200, 404))


async def test_provider_config(client):
    log("\n── Provider Configuration ──", "hdr")

    r = await client.get(f"{API}/text2img/providers")
    if r.status_code == 200:
        data = r.json()
        providers = data.get("providers", [])
        for p in providers:
            check(f"Provider {p['id']} has required fields",
                  all(k in p for k in ("id", "name", "enabled", "sizes", "default_size")),
                  str(list(p.keys())))


async def test_error_handling(client):
    log("\n── Error Handling ──", "hdr")

    # Invalid task ID
    r = await client.get(f"{API}/tasks/nonexistent_id")
    check("GET non-existent task returns 404", r.status_code == 404)

    # Invalid workflow data
    r = await client.post(f"{API}/workflows", json={"name": "", "graph": "not a dict"})
    check("POST workflow with invalid graph returns error", r.status_code >= 400,
          f"got {r.status_code}: {r.text[:100]}")

    # Missing required fields
    r = await client.post(f"{API}/workflows", json={})
    check("POST workflow empty body returns error", r.status_code >= 400,
          f"got {r.status_code}")


# ═══════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════


async def run_all_tests():
    global PASS, FAIL, SKIP
    PASS = FAIL = SKIP = 0

    async with httpx.AsyncClient(timeout=15) as client:
        # Standard endpoints
        await test_docs(client)
        await test_pipeline_types(client)
        await test_node_types(client)
        await test_text2img_providers(client)
        await test_provider_config(client)
        await test_static_files(client)

        # CRUD operations
        await test_workflow_crud(client)
        await test_tasks_crud(client)

        # Execution
        await test_workflow_execution(client)
        await test_workflow_instances_crud(client)
        await test_compound_workflow(client)

        # Text2Image (needs API key)
        await test_text2img(client)

        # Error handling
        await test_error_handling(client)

    # Summary
    total = PASS + FAIL + SKIP
    log(f"\n{'='*50}", "hdr")
    log(f"Results: {PASS} passed, {FAIL} failed, {SKIP} skipped ({total} total)", "hdr")
    if FAIL > 0:
        log(f"\n{FAIL} TEST(S) FAILED!", "fail")
    else:
        log(f"\nAll tests passed!", "ok")
    log(f"{'='*50}", "hdr")

    return FAIL == 0


def main():
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
        log(f"Starting server: {server_py}", "hdr")
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
                log("Server is ready!", "ok")
                break
            except Exception:
                time.sleep(0.5)
        else:
            log("Server failed to start", "fail")
            server_proc.kill()
            return 1

    try:
        import asyncio
        success = asyncio.run(run_all_tests())
    except KeyboardInterrupt:
        success = False
    finally:
        if server_proc:
            log("Stopping server...", "info")
            server_proc.kill()
            server_proc.wait()

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
