"""test_workflow_engine.py - Unit tests for workflow engine logic.

Tests the DAG execution engine in isolation (no server, no database).

Usage:
    python tests/test_workflow_engine.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web.workflow_engine import WorkflowEngine

PASS = 0
FAIL = 0


def log(msg, level="info"):
    colors = {"ok": "\033[92m", "fail": "\033[91m", "skip": "\033[93m", "hdr": "\033[1;36m"}
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
# Topological Sort Tests
# ═══════════════════════════════════════════════════════════

def test_topsort_linear():
    log("\n── Topological Sort: Linear chain ──", "hdr")
    engine = WorkflowEngine()
    node_map = {str(i): {"id": i, "type": "test"} for i in [1, 2, 3]}
    adj = {"1": ["2"], "2": ["3"], "3": []}
    in_degree = {"1": 0, "2": 1, "3": 1}

    result = engine._topsort(node_map, adj, in_degree)
    check("Returns list", result is not None)
    check("Correct order", result == ["1", "2", "3"], f"got {result}")


def test_topsort_parallel():
    log("\n── Topological Sort: Parallel branches ──", "hdr")
    engine = WorkflowEngine()
    node_map = {str(i): {"id": i, "type": "test"} for i in [1, 2, 3, 4]}
    adj = {"1": ["3"], "2": ["3"], "3": ["4"], "4": []}
    in_degree = {"1": 0, "2": 0, "3": 2, "4": 1}

    result = engine._topsort(node_map, adj, in_degree)
    check("Returns list", result is not None)
    check("Correct length", len(result) == 4)
    check("1 before 3", result.index("1") < result.index("3"))
    check("2 before 3", result.index("2") < result.index("3"))
    check("3 before 4", result.index("3") < result.index("4"))


def test_topsort_disconnected():
    log("\n── Topological Sort: Disconnected nodes ──", "hdr")
    engine = WorkflowEngine()
    node_map = {str(i): {"id": i, "type": "test"} for i in [1, 2]}
    adj = {"1": [], "2": []}
    in_degree = {"1": 0, "2": 0}

    result = engine._topsort(node_map, adj, in_degree)
    check("Returns list", result is not None)
    check("Correct length", len(result) == 2)


def test_topsort_cycle():
    log("\n── Topological Sort: Cycle detection ──", "hdr")
    engine = WorkflowEngine()
    node_map = {str(i): {"id": i, "type": "test"} for i in [1, 2, 3]}
    adj = {"1": ["2"], "2": ["3"], "3": ["1"]}  # 1→2→3→1 (cycle)
    in_degree = {"1": 1, "2": 1, "3": 1}

    result = engine._topsort(node_map, adj, in_degree)
    check("Returns None on cycle", result is None)


def test_topsort_empty():
    log("\n── Topological Sort: Empty graph ──", "hdr")
    engine = WorkflowEngine()
    result = engine._topsort({}, {}, {})
    check("Returns empty list", result == [])


# ═══════════════════════════════════════════════════════════
# Edge Normalization Tests
# ═══════════════════════════════════════════════════════════

def test_normalize_edges_litegraph():
    log("\n── Edge Normalization: LiteGraph format ──", "hdr")
    engine = WorkflowEngine()
    graph = {
        "links": [
            [0, 1, 0, 2, 0, "image"],   # [linkId, srcId, srcSlot, tgtId, tgtSlot, type]
            [1, 2, 0, 3, 0, "stl"],
        ]
    }
    edges = engine._normalize_edges(graph)
    check("Returns 2 edges", len(edges) == 2)
    check("First edge source=1", edges[0]["source"] == "1")
    check("First edge target=2", edges[0]["target"] == "2")
    check("Source port is int", isinstance(edges[0]["source_port"], int))


def test_normalize_edges_legacy():
    log("\n── Edge Normalization: Legacy format ──", "hdr")
    engine = WorkflowEngine()
    graph = {
        "edges": [
            {"source": "1", "source_port": 0, "target": "2", "target_port": 0},
        ]
    }
    edges = engine._normalize_edges(graph)
    check("Returns 1 edge", len(edges) == 1)
    check("Correct source", edges[0]["source"] == "1")


def test_normalize_edges_empty():
    log("\n── Edge Normalization: Empty graph ──", "hdr")
    engine = WorkflowEngine()
    check("Empty links returns []", engine._normalize_edges({}) == [])
    check("No links returns []", engine._normalize_edges({"nodes": []}) == [])


# ═══════════════════════════════════════════════════════════
# Port Edge Map Tests
# ═══════════════════════════════════════════════════════════

def test_build_port_edge_map_single_output():
    log("\n── Port Edge Map: Single output node ──", "hdr")
    engine = WorkflowEngine()
    node_map = {
        "1": {"id": 1, "type": "text_to_image"},
        "2": {"id": 2, "type": "relief"},
    }
    edges = [{"source": "1", "source_port": 0, "target": "2", "target_port": 0}]

    edge_map = engine._build_port_edge_map(node_map, edges)

    check("Edge map has entry for relief's input", ("2", "image") in edge_map)
    src_nid, src_port = edge_map[("2", "image")]
    check("Source is text_to_image", src_nid == "1")
    check("Source port is 'image'", src_port == "image")


def test_build_port_edge_map_out_of_range_slot():
    log("\n── Port Edge Map: Slot out of range is skipped ──", "hdr")
    engine = WorkflowEngine()
    node_map = {
        "1": {"id": 1, "type": "text_to_image"},  # has 1 output
        "2": {"id": 2, "type": "relief"},          # has 1 input
    }
    # src_slot=99 is out of range for text_to_image which has only 1 output
    edges = [{"source": "1", "source_port": 99, "target": "2", "target_port": 0}]

    edge_map = engine._build_port_edge_map(node_map, edges)

    # Out-of-range slot should result in None → entry not added
    check("No entry added for out-of-range src_slot",
          all(k[0] != "2" or k[1] != "image" for k in edge_map.keys()))


def test_build_port_edge_map_multi_output():
    log("\n── Port Edge Map: Multi-output node ──", "hdr")
    engine = WorkflowEngine()
    node_map = {
        "1": {"id": 1, "type": "text_to_image"},
        "2": {"id": 2, "type": "relief"},
        "3": {"id": 3, "type": "output_file"},
    }
    # text_to_image → relief (port 0)
    # relief → output_file (port 0 = stl)
    edges = [
        {"source": "1", "source_port": 0, "target": "2", "target_port": 0},
        {"source": "2", "source_port": 0, "target": "3", "target_port": 0},
    ]

    edge_map = engine._build_port_edge_map(node_map, edges)

    check("relief gets image from text_to_image",
          edge_map.get(("2", "image")) == ("1", "image"))
    check("output_file gets stl from relief",
          edge_map.get(("3", "file")) == ("2", "stl"))


# ═══════════════════════════════════════════════════════════
# DAG Build Tests
# ═══════════════════════════════════════════════════════════

def test_build_dag():
    log("\n── DAG Build ──", "hdr")
    engine = WorkflowEngine()
    node_map = {str(i): {"id": i, "type": "test"} for i in [1, 2, 3]}
    edges = [{"source": "1", "target": "2"}, {"source": "2", "target": "3"}]

    adj, in_degree = engine._build_dag(node_map, edges)

    check("1 has outgoing to 2", "2" in adj.get("1", []))
    check("2 has outgoing to 3", "3" in adj.get("2", []))
    check("3 has no outgoing", len(adj.get("3", [])) == 0)
    check("1 has in-degree 0", in_degree["1"] == 0)
    check("2 has in-degree 1", in_degree["2"] == 1)
    check("3 has in-degree 1", in_degree["3"] == 1)


def test_build_dag_with_missing_nodes():
    log("\n── DAG Build: Edges to missing nodes are ignored ──", "hdr")
    engine = WorkflowEngine()
    node_map = {"1": {"id": 1, "type": "test"}}
    edges = [{"source": "1", "target": "999"}]  # node 999 doesn't exist

    adj, in_degree = engine._build_dag(node_map, edges)

    check("Edge to missing node is ignored", "999" not in adj.get("1", []))


# ═══════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════

def main():
    log("3D Print Pipeline — Workflow Engine Unit Tests", "hdr")

    test_functions = [
        # Topological sort
        test_topsort_linear,
        test_topsort_parallel,
        test_topsort_disconnected,
        test_topsort_cycle,
        test_topsort_empty,
        # Edge normalization
        test_normalize_edges_litegraph,
        test_normalize_edges_legacy,
        test_normalize_edges_empty,
        # Port edge map
        test_build_port_edge_map_single_output,
        test_build_port_edge_map_out_of_range_slot,
        test_build_port_edge_map_multi_output,
        # DAG build
        test_build_dag,
        test_build_dag_with_missing_nodes,
    ]

    for tf in test_functions:
        try:
            tf()
        except Exception as e:
            global FAIL
            FAIL += 1
            log(f"  FAIL {tf.__name__} — {e}", "fail")

    total = PASS + FAIL
    log(f"\n{'='*50}", "hdr")
    log(f"Workflow engine tests: {PASS} passed, {FAIL} failed ({total} total)", "hdr")
    if FAIL == 0:
        log("All workflow engine tests passed!", "ok")
    else:
        log(f"{FAIL} test(s) FAILED", "fail")
    log(f"{'='*50}", "hdr")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())