"""test_workflow_engine.py - Unit tests for workflow engine logic.

Tests the DAG execution engine in isolation (no server, no database).

Usage:
    pytest tests/test_workflow_engine.py -v
    pytest tests/test_workflow_engine.py -v -k topsort
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from web.workflow_engine import WorkflowEngine


# ═══════════════════════════════════════════════════════════
# Topological Sort Tests
# ═══════════════════════════════════════════════════════════

def test_topsort_linear():
    """Linear chain 1→2→3 maintains order."""
    engine = WorkflowEngine()
    node_map = {str(i): {"id": i, "type": "test"} for i in [1, 2, 3]}
    adj = {"1": ["2"], "2": ["3"], "3": []}
    in_degree = {"1": 0, "2": 1, "3": 1}

    result = engine._topsort(node_map, adj, in_degree)

    assert result is not None
    assert result == ["1", "2", "3"]


def test_topsort_parallel():
    """Parallel branches 1,2 → 3 → 4: 1 and 2 before 3, 3 before 4."""
    engine = WorkflowEngine()
    node_map = {str(i): {"id": i, "type": "test"} for i in [1, 2, 3, 4]}
    adj = {"1": ["3"], "2": ["3"], "3": ["4"], "4": []}
    in_degree = {"1": 0, "2": 0, "3": 2, "4": 1}

    result = engine._topsort(node_map, adj, in_degree)

    assert result is not None
    assert len(result) == 4
    assert result.index("1") < result.index("3")
    assert result.index("2") < result.index("3")
    assert result.index("3") < result.index("4")


def test_topsort_disconnected():
    """Disconnected nodes are both included."""
    engine = WorkflowEngine()
    node_map = {str(i): {"id": i, "type": "test"} for i in [1, 2]}
    adj = {"1": [], "2": []}
    in_degree = {"1": 0, "2": 0}

    result = engine._topsort(node_map, adj, in_degree)

    assert result is not None
    assert len(result) == 2


def test_topsort_cycle():
    """Cycle detection: 1→2→3→1 returns None."""
    engine = WorkflowEngine()
    node_map = {str(i): {"id": i, "type": "test"} for i in [1, 2, 3]}
    adj = {"1": ["2"], "2": ["3"], "3": ["1"]}
    in_degree = {"1": 1, "2": 1, "3": 1}

    result = engine._topsort(node_map, adj, in_degree)

    assert result is None


def test_topsort_empty():
    """Empty graph returns empty list."""
    engine = WorkflowEngine()
    result = engine._topsort({}, {}, {})
    assert result == []


# ═══════════════════════════════════════════════════════════
# Edge Normalization Tests
# ═══════════════════════════════════════════════════════════

def test_normalize_edges_litegraph():
    """LiteGraph [[id,src,srcSlot,tgt,tgtSlot,type],...] format."""
    engine = WorkflowEngine()
    graph = {
        "links": [
            [0, 1, 0, 2, 0, "image"],
            [1, 2, 0, 3, 0, "stl"],
        ]
    }
    edges = engine._normalize_edges(graph)

    assert len(edges) == 2
    assert edges[0]["source"] == "1"
    assert edges[0]["target"] == "2"
    assert isinstance(edges[0]["source_port"], int)


def test_normalize_edges_legacy():
    """Legacy [{source, source_port, target, target_port}] format."""
    engine = WorkflowEngine()
    graph = {
        "edges": [
            {"source": "1", "source_port": 0, "target": "2", "target_port": 0},
        ]
    }
    edges = engine._normalize_edges(graph)

    assert len(edges) == 1
    assert edges[0]["source"] == "1"


def test_normalize_edges_empty():
    """Empty links/no links returns empty list."""
    engine = WorkflowEngine()
    assert engine._normalize_edges({}) == []
    assert engine._normalize_edges({"nodes": []}) == []


# ═══════════════════════════════════════════════════════════
# Port Edge Map Tests
# ═══════════════════════════════════════════════════════════

def test_build_port_edge_map_single_output():
    """Single output node maps to target correctly."""
    engine = WorkflowEngine()
    node_map = {
        "1": {"id": 1, "type": "text_to_image"},
        "2": {"id": 2, "type": "relief"},
    }
    edges = [{"source": "1", "source_port": 0, "target": "2", "target_port": 0}]

    edge_map = engine._build_port_edge_map(node_map, edges)

    assert ("2", "image") in edge_map
    src_nid, src_port = edge_map[("2", "image")]
    assert src_nid == "1"
    assert src_port == "image"


def test_build_port_edge_map_out_of_range_slot():
    """Out-of-range slot is skipped."""
    engine = WorkflowEngine()
    node_map = {
        "1": {"id": 1, "type": "text_to_image"},
        "2": {"id": 2, "type": "relief"},
    }
    edges = [{"source": "1", "source_port": 99, "target": "2", "target_port": 0}]

    edge_map = engine._build_port_edge_map(node_map, edges)

    assert all(k[0] != "2" or k[1] != "image" for k in edge_map.keys())


def test_build_port_edge_map_multi_output():
    """Multi-output chain: text_to_image → relief → output_file."""
    engine = WorkflowEngine()
    node_map = {
        "1": {"id": 1, "type": "text_to_image"},
        "2": {"id": 2, "type": "relief"},
        "3": {"id": 3, "type": "output_file"},
    }
    edges = [
        {"source": "1", "source_port": 0, "target": "2", "target_port": 0},
        {"source": "2", "source_port": 0, "target": "3", "target_port": 0},
    ]

    edge_map = engine._build_port_edge_map(node_map, edges)

    assert edge_map.get(("2", "image")) == ("1", "image")
    assert edge_map.get(("3", "file")) == ("2", "stl")


# ═══════════════════════════════════════════════════════════
# DAG Build Tests
# ═══════════════════════════════════════════════════════════

def test_build_dag():
    """DAG construction: 1→2→3 chain."""
    engine = WorkflowEngine()
    node_map = {str(i): {"id": i, "type": "test"} for i in [1, 2, 3]}
    edges = [{"source": "1", "target": "2"}, {"source": "2", "target": "3"}]

    adj, in_degree = engine._build_dag(node_map, edges)

    assert "2" in adj.get("1", [])
    assert "3" in adj.get("2", [])
    assert len(adj.get("3", [])) == 0
    assert in_degree["1"] == 0
    assert in_degree["2"] == 1
    assert in_degree["3"] == 1


def test_build_dag_with_missing_nodes():
    """Edges to missing nodes are ignored."""
    engine = WorkflowEngine()
    node_map = {"1": {"id": 1, "type": "test"}}
    edges = [{"source": "1", "target": "999"}]

    adj, in_degree = engine._build_dag(node_map, edges)

    assert "999" not in adj.get("1", [])