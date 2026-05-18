"""test_dag.py — Unit tests for dag.py pure functions.

Covers all Critical bug fixes from code review:
- topsort mutation side effect (1.3)
- resolve_input duplicate definition (1.1)
- enrich_ctx overwriting handler metadata (1.7)
- build_upstream O(n²) list.pop(0) (not in review, found during fix)

Usage:
    pytest tests/test_dag.py -v
    pytest tests/test_dag.py -v -k topsort
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from web.dag import (
    topsort,
    resolve_input,
    build_upstream,
    enrich_ctx,
    build_dag,
    build_port_edge_map,
    normalize_edges,
    validate_file_for_port,
)


# ═══════════════════════════════════════════════════════════
# topsort()
# ═══════════════════════════════════════════════════════════

class TestTopsort:
    def test_linear(self):
        """Linear chain 1→2→3 maintains order."""
        node_map = {"1": {}, "2": {}, "3": {}}
        adj = {"1": ["2"], "2": ["3"], "3": []}
        in_degree = {"1": 0, "2": 1, "3": 1}
        result = topsort(node_map, adj, in_degree)
        assert result == ["1", "2", "3"]

    def test_parallel(self):
        """Parallel branches: 1,2 → 3 → 4."""
        node_map = {str(i): {} for i in [1, 2, 3, 4]}
        adj = {"1": ["3"], "2": ["3"], "3": ["4"], "4": []}
        in_degree = {"1": 0, "2": 0, "3": 2, "4": 1}
        result = topsort(node_map, adj, in_degree)
        assert result is not None
        assert len(result) == 4
        assert result.index("1") < result.index("3")
        assert result.index("2") < result.index("3")
        assert result.index("3") < result.index("4")

    def test_disconnected(self):
        """Disconnected nodes are all included."""
        node_map = {"1": {}, "2": {}}
        adj = {"1": [], "2": []}
        in_degree = {"1": 0, "2": 0}
        result = topsort(node_map, adj, in_degree)
        assert result is not None
        assert len(result) == 2
        assert "1" in result and "2" in result

    def test_cycle(self):
        """Cycle 1→2→3→1 returns None."""
        node_map = {"1": {}, "2": {}, "3": {}}
        adj = {"1": ["2"], "2": ["3"], "3": ["1"]}
        in_degree = {"1": 1, "2": 1, "3": 1}
        result = topsort(node_map, adj, in_degree)
        assert result is None

    def test_empty(self):
        """Empty graph returns empty list."""
        result = topsort({}, {}, {})
        assert result == []

    def test_single_node(self):
        """Single node with no edges."""
        node_map = {"1": {}}
        adj = {"1": []}
        in_degree = {"1": 0}
        result = topsort(node_map, adj, in_degree)
        assert result == ["1"]

    def test_does_not_mutate_in_degree(self):
        """CRITICAL: topsort must NOT mutate the caller's in_degree dict."""
        node_map = {"1": {}, "2": {}, "3": {}}
        adj = {"1": ["2"], "2": ["3"], "3": []}
        in_degree = {"1": 0, "2": 1, "3": 1}
        original = dict(in_degree)
        topsort(node_map, adj, in_degree)
        assert in_degree == original, f"in_degree was mutated: {in_degree} != {original}"

    def test_diamond(self):
        """Diamond shape: 1→2,3; 2,3→4."""
        node_map = {str(i): {} for i in [1, 2, 3, 4]}
        adj = {"1": ["2", "3"], "2": ["4"], "3": ["4"], "4": []}
        in_degree = {"1": 0, "2": 1, "3": 1, "4": 2}
        result = topsort(node_map, adj, in_degree)
        assert result is not None
        assert len(result) == 4
        assert result.index("1") < result.index("2")
        assert result.index("1") < result.index("3")
        assert result.index("2") < result.index("4")
        assert result.index("3") < result.index("4")


# ═══════════════════════════════════════════════════════════
# build_dag()
# ═══════════════════════════════════════════════════════════

class TestBuildDag:
    def test_linear(self):
        """Linear chain 1→2→3."""
        node_map = {"1": {}, "2": {}, "3": {}}
        edges = [{"source": "1", "target": "2"}, {"source": "2", "target": "3"}]
        adj, in_degree = build_dag(node_map, edges)
        assert adj["1"] == ["2"]
        assert adj["2"] == ["3"]
        assert adj["3"] == []
        assert in_degree["1"] == 0
        assert in_degree["2"] == 1
        assert in_degree["3"] == 1

    def test_parallel(self):
        """Two sources feeding one target."""
        node_map = {"1": {}, "2": {}, "3": {}}
        edges = [{"source": "1", "target": "3"}, {"source": "2", "target": "3"}]
        adj, in_degree = build_dag(node_map, edges)
        assert "3" in adj["1"]
        assert "3" in adj["2"]
        assert in_degree["3"] == 2

    def test_missing_nodes_ignored(self):
        """Edges referencing non-existent nodes are skipped."""
        node_map = {"1": {}}
        edges = [{"source": "1", "target": "999"}]
        adj, in_degree = build_dag(node_map, edges)
        assert "999" not in adj.get("1", [])

    def test_empty(self):
        """Empty node_map and edges returns empty structures."""
        adj, in_degree = build_dag({}, [])
        assert adj == {}
        assert in_degree == {}

    def test_no_edges(self):
        """Nodes with no edges: each node has empty adj and in_degree 0."""
        node_map = {"1": {}, "2": {}}
        adj, in_degree = build_dag(node_map, [])
        assert adj == {"1": [], "2": []}
        assert in_degree == {"1": 0, "2": 0}

    def test_source_node_alias(self):
        """Edge with source_node/target_node keys instead of source/target."""
        node_map = {"1": {}, "2": {}}
        edges = [{"source_node": "1", "target_node": "2"}]
        adj, in_degree = build_dag(node_map, edges)
        assert in_degree["2"] == 1

    def test_numeric_ids(self):
        """Numeric node IDs are stringified correctly."""
        node_map = {"1": {}, "2": {}}
        edges = [{"source": 1, "target": 2}]
        adj, in_degree = build_dag(node_map, edges)
        assert "2" in adj.get("1", [])


# ═══════════════════════════════════════════════════════════
# build_upstream()
# ═══════════════════════════════════════════════════════════

class TestBuildUpstream:
    def test_linear_chain(self):
        """Node 3 has upstream from 1 and 2."""
        ctx = {
            "1": {"image": "/img/a.png", "_params": {"size": "1024"}, "_inputs": {"file": "/f.png"}},
            "2": {"stl": "/mesh/b.stl", "_params": {"width": 160}},
        }
        edge_map = {
            ("2", "image"): ("1", "image"),
            ("3", "file"): ("2", "stl"),
        }
        cascade = build_upstream("3", ctx, edge_map)
        assert "1.image" in cascade
        assert cascade["1.image"] == "/img/a.png"
        assert "1._params.size" in cascade
        assert cascade["1._params.size"] == "1024"
        assert "1._inputs.file" in cascade
        assert "2.stl" in cascade
        assert cascade["2.stl"] == "/mesh/b.stl"
        assert "2._params.width" in cascade

    def test_root_node_no_upstream(self):
        """Root node with no incoming edges returns empty cascade."""
        ctx = {"1": {"image": "/a.png"}}
        edge_map = {("2", "image"): ("1", "image")}
        cascade = build_upstream("1", ctx, edge_map)
        assert cascade == {}

    def test_empty_ctx(self):
        """Node with upstream edges but empty ctx doesn't crash."""
        ctx = {}
        edge_map = {("2", "image"): ("1", "image")}
        cascade = build_upstream("2", ctx, edge_map)
        assert cascade == {}

    def test_non_dict_ctx_skipped(self):
        """Non-dict ctx values are skipped."""
        ctx = {"1": "not_a_dict"}
        edge_map = {("2", "image"): ("1", "image")}
        cascade = build_upstream("2", ctx, edge_map)
        assert cascade == {}


# ═══════════════════════════════════════════════════════════
# enrich_ctx()
# ═══════════════════════════════════════════════════════════

class TestEnrichCtx:
    def test_basic(self):
        """Sets _inputs, _params, and _upstream on ctx[nid]."""
        ctx = {"1": {"image": "/a.png"}}
        edge_map = {("2", "image"): ("1", "image")}
        enrich_ctx("2", {"image": "/a.png"}, {"width": 160}, ctx, edge_map)
        assert "2" in ctx
        assert ctx["2"]["_inputs"] == {"image": "/a.png"}
        assert ctx["2"]["_params"] == {"width": 160}
        assert "_upstream" in ctx["2"]
        assert "1" in ctx["2"]["_upstream"]

    def test_preserves_handler_outputs(self):
        """CRITICAL: handler-set metadata is NOT overwritten."""
        ctx = {"1": {"image": "/a.png"}, "2": {"mesh": "/out.glb", "_inputs": {"image": "/real.png"}, "_params": {"provider": "openai"}}}
        edge_map = {}
        enrich_ctx("2", {}, {}, ctx, edge_map)
        # Handler already set _inputs and _params — they must be preserved
        assert ctx["2"]["_inputs"] == {"image": "/real.png"}
        assert ctx["2"]["_params"] == {"provider": "openai"}
        # Outputs set by handler remain
        assert ctx["2"]["mesh"] == "/out.glb"

    def test_no_overwrite_inputs(self):
        """_inputs only set once — first writer wins."""
        ctx = {"2": {"_inputs": {"image": "/handler_set.png"}}}
        edge_map = {}
        enrich_ctx("2", {"image": "/default.png"}, {}, ctx, edge_map)
        assert ctx["2"]["_inputs"] == {"image": "/handler_set.png"}

    def test_no_overwrite_params(self):
        """_params only set once — first writer wins."""
        ctx = {"2": {"_params": {"provider": "volcengine"}}}
        edge_map = {}
        enrich_ctx("2", {}, {"provider": "openai"}, ctx, edge_map)
        assert ctx["2"]["_params"] == {"provider": "volcengine"}

    def test_empty_resolved(self):
        """Empty resolved_inputs/resolved_params don't crash."""
        ctx = {}
        edge_map = {}
        enrich_ctx("1", None, None, ctx, edge_map)
        assert ctx["1"]["_inputs"] == {}
        assert ctx["1"]["_params"] == {}

    def test_upstream_cascade(self):
        """_upstream includes transitive upstream contexts."""
        ctx = {
            "1": {"image": "/a.png"},
            "2": {"stl": "/b.stl", "_upstream": {"1": {"image": "/a.png"}}},
        }
        edge_map = {
            ("2", "image"): ("1", "image"),
            ("3", "file"): ("2", "stl"),
        }
        enrich_ctx("3", {}, {}, ctx, edge_map)
        upstream = ctx["3"]["_upstream"]
        assert "2" in upstream
        assert "1" in upstream  # transitive


# ═══════════════════════════════════════════════════════════
# resolve_input()
# ═══════════════════════════════════════════════════════════

class TestResolveInput:
    def test_from_edge_map(self):
        """Resolve via saved graph edge_map."""
        ctx = {"1": {"image": "/img/a.png"}}
        edge_map = {("2", "image"): ("1", "image")}
        result = resolve_input("2", "image", edge_map, ctx)
        assert result == "/img/a.png"

    def test_from_external_inputs(self):
        """Fallback to _inputs when edge_map has no match."""
        ctx = {"_inputs": {"2": {"image": "/ext/b.png"}}}
        edge_map = {}
        result = resolve_input("2", "image", edge_map, ctx)
        assert result == "/ext/b.png"

    def test_edge_map_priority_over_external(self):
        """Edge map takes priority over external inputs."""
        ctx = {
            "1": {"image": "/edge/a.png"},
            "_inputs": {"2": {"image": "/ext/b.png"}},
        }
        edge_map = {("2", "image"): ("1", "image")}
        result = resolve_input("2", "image", edge_map, ctx)
        assert result == "/edge/a.png"

    def test_runtime_override_priority(self):
        """Runtime _node_inputs override takes highest priority."""
        ctx = {
            "3": {"image": "/override/c.png"},
            "1": {"image": "/edge/a.png"},
            "_node_inputs": {"2": {"image": {"source_node": "3", "source_port": "image"}}},
        }
        edge_map = {("2", "image"): ("1", "image")}
        result = resolve_input("2", "image", edge_map, ctx)
        assert result == "/override/c.png"

    def test_not_found(self):
        """No match returns None."""
        ctx = {}
        edge_map = {}
        result = resolve_input("1", "image", edge_map, ctx)
        assert result is None

    def test_edge_map_other_node_not_leak(self):
        """Edge for a different node doesn't leak."""
        ctx = {"1": {"image": "/a.png"}}
        edge_map = {("3", "image"): ("1", "image")}
        result = resolve_input("2", "image", edge_map, ctx)
        assert result is None


# ═══════════════════════════════════════════════════════════
# build_port_edge_map()
# ═══════════════════════════════════════════════════════════

class TestBuildPortEdgeMap:
    def test_single_edge(self):
        """Single edge maps correctly with slot→name translation."""
        node_map = {
            "1": {"id": 1, "type": "text_to_image"},
            "2": {"id": 2, "type": "relief"},
        }
        edges = [{"source": "1", "source_port": 0, "target": "2", "target_port": 0}]
        edge_map = build_port_edge_map(node_map, edges)
        assert ("2", "image") in edge_map
        src_nid, src_port = edge_map[("2", "image")]
        assert src_nid == "1"
        assert src_port == "image"

    def test_out_of_range_slot_skipped(self):
        """Slot index beyond port list is skipped."""
        node_map = {
            "1": {"id": 1, "type": "text_to_image"},
            "2": {"id": 2, "type": "relief"},
        }
        edges = [{"source": "1", "source_port": 99, "target": "2", "target_port": 0}]
        edge_map = build_port_edge_map(node_map, edges)
        assert edge_map == {}

    def test_string_ports(self):
        """String port names pass through without translation."""
        node_map = {
            "1": {"id": 1, "type": "file_input"},
            "2": {"id": 2, "type": "relief"},
        }
        edges = [{"source": "1", "source_port": "file", "target": "2", "target_port": "image"}]
        edge_map = build_port_edge_map(node_map, edges)
        assert edge_map.get(("2", "image")) == ("1", "file")

    def test_missing_nodes_skipped(self):
        """Edges with missing source/target nodes are skipped."""
        node_map = {"1": {"id": 1, "type": "text_to_image"}}
        edges = [{"source": "1", "source_port": 0, "target": "999", "target_port": 0}]
        edge_map = build_port_edge_map(node_map, edges)
        assert edge_map == {}

    def test_empty(self):
        """Empty edges returns empty dict."""
        node_map = {"1": {"id": 1, "type": "text_to_image"}}
        edge_map = build_port_edge_map(node_map, [])
        assert edge_map == {}


# ═══════════════════════════════════════════════════════════
# normalize_edges()
# ═══════════════════════════════════════════════════════════

class TestNormalizeEdges:
    def test_litegraph_format(self):
        """LiteGraph links array format."""
        graph = {
            "links": [
                [0, 1, 0, 2, 0, "image"],
                [1, 2, 0, 3, 0, "stl"],
            ]
        }
        edges = normalize_edges(graph)
        assert len(edges) == 2
        assert edges[0]["source"] == "1"
        assert edges[0]["target"] == "2"
        assert edges[0]["source_port"] == 0

    def test_legacy_format(self):
        """Legacy edges dict format takes priority."""
        graph = {
            "edges": [{"source": "1", "source_port": 0, "target": "2", "target_port": 0}],
            "links": [[0, 3, 0, 4, 0, "image"]],
        }
        edges = normalize_edges(graph)
        assert len(edges) == 1
        assert edges[0]["source"] == "1"

    def test_empty(self):
        """No edges or links returns empty list."""
        assert normalize_edges({}) == []
        assert normalize_edges({"nodes": []}) == []

    def test_short_link_skipped(self):
        """Links with fewer than 5 elements are skipped."""
        graph = {"links": [[0, 1, 0]]}  # only 3 elements
        edges = normalize_edges(graph)
        assert edges == []


# ═══════════════════════════════════════════════════════════
# validate_file_for_port()
# ═══════════════════════════════════════════════════════════

class TestValidateFileForPort:
    def test_image_port_png(self):
        """PNG file matches image port."""
        assert validate_file_for_port("/path/to/file.png", "image") is None

    def test_image_port_stl_mismatch(self):
        """STL file doesn't match image port."""
        warning = validate_file_for_port("/path/to/file.stl", "image")
        assert warning is not None
        assert "may not be compatible" in warning.lower()

    def test_mesh_port_glb(self):
        """GLB file matches mesh port."""
        assert validate_file_for_port("/path/to/model.glb", "mesh") is None

    def test_wildcard_port(self):
        """Wildcard port type accepts anything."""
        assert validate_file_for_port("/path/to/any.ext", "*") is None
        assert validate_file_for_port("/path/to/any.ext", "any") is None

    def test_string_port(self):
        """String port type accepts anything."""
        assert validate_file_for_port("/path/to/any.txt", "string") is None

    def test_unknown_port_type(self):
        """Unknown port type is allowed (no restriction)."""
        assert validate_file_for_port("/path/to/file.xyz", "unknown_type") is None

    def test_empty_file_path(self):
        """Empty file path returns None."""
        assert validate_file_for_port("", "image") is None
        assert validate_file_for_port(None, "image") is None

    def test_empty_port_type(self):
        """Empty port type returns None."""
        assert validate_file_for_port("/path/to/file.png", "") is None
