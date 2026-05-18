"""test_schema_consistency.py — Verify frontend/backend data structure consistency.

Validates that:
1. All template node types exist in NODE_TYPES registry
2. Template port names match node type port definitions
3. NODE_TYPES keys match their NodeType.id fields
4. API /api/node-types returns all registered nodes
5. All required port names (used in templates/edges) are valid

Usage:
    pytest tests/test_schema_consistency.py -v
    pytest tests/test_schema_consistency.py -v --api   # also test live API
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from web.node_types import NODE_TYPES, CATEGORIES, PARAM_META, node_pipeline_map, node_input_port_map


# ═══════════════════════════════════════════════════════════
# Template Definitions (mirrors wf-editor.js _wfTemplate)
# ═══════════════════════════════════════════════════════════

TEMPLATES = {
    "basic": {
        "nodes": [
            {"id": 1, "type": "file_input", "title": "File", "pos": [100, 100]},
            {"id": 2, "type": "relief", "title": "Relief", "pos": [400, 100]},
        ],
        "edges": [
            {"source": 1, "target": 2, "sourcePort": "file", "targetPort": "image"},
        ],
    },
    "text2img": {
        "nodes": [
            {"id": 1, "type": "text_input", "title": "Text", "pos": [100, 100]},
            {"id": 2, "type": "text_to_image", "title": "Text→Image", "pos": [400, 100]},
            {"id": 3, "type": "relief", "title": "Relief", "pos": [700, 100]},
        ],
        "edges": [
            {"source": 1, "target": 2, "sourcePort": "text", "targetPort": "prompt"},
            {"source": 2, "target": 3, "sourcePort": "image", "targetPort": "image"},
        ],
    },
    "advanced": {
        "nodes": [
            {"id": 1, "type": "file_input", "title": "File", "pos": [100, 100]},
            {"id": 2, "type": "layered_relief", "title": "Layered", "pos": [400, 100]},
            {"id": 3, "type": "repair", "title": "Repair", "pos": [700, 100]},
        ],
        "edges": [
            {"source": 1, "target": 2, "sourcePort": "file", "targetPort": "image"},
            {"source": 2, "target": 3, "sourcePort": "stl", "targetPort": "mesh"},
        ],
    },
    "print-ready": {
        "nodes": [
            {"id": 1, "type": "file_input", "title": "File", "pos": [100, 100]},
            {"id": 2, "type": "triposr", "title": "3D Gen", "pos": [400, 100]},
            {"id": 3, "type": "model_prep", "title": "Prep", "pos": [700, 100]},
        ],
        "edges": [
            {"source": 1, "target": 2, "sourcePort": "file", "targetPort": "image"},
            {"source": 2, "target": 3, "sourcePort": "mesh", "targetPort": "mesh"},
        ],
    },
    "full": {
        "nodes": [
            {"id": 1, "type": "file_input", "title": "File", "pos": [100, 100]},
            {"id": 2, "type": "triposr", "title": "3D Gen", "pos": [400, 100]},
            {"id": 3, "type": "model_prep", "title": "Prep", "pos": [700, 100]},
            {"id": 4, "type": "views", "title": "Views", "pos": [1000, 100]},
        ],
        "edges": [
            {"source": 1, "target": 2, "sourcePort": "file", "targetPort": "image"},
            {"source": 2, "target": 3, "sourcePort": "mesh", "targetPort": "mesh"},
            {"source": 3, "target": 4, "sourcePort": "mesh", "targetPort": "mesh"},
        ],
    },
}


# ═══════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════

def test_node_type_ids_self_consistent():
    """Verify every NODE_TYPES key matches the NodeType.id."""
    for key, nt in NODE_TYPES.items():
        assert nt.id == key, f"NODE_TYPES['{key}'].id == '{nt.id}' (expected '{key}')"


def test_all_template_types_exist():
    """Verify every template node type exists in NODE_TYPES."""
    for tpl_name, tpl in TEMPLATES.items():
        for node in tpl["nodes"]:
            type_id = node["type"]
            clean = type_id.replace("wf_", "", 1) if type_id.startswith("wf_") else type_id
            assert clean in NODE_TYPES, (
                f"Template '{tpl_name}' node #{node['id']} type '{type_id}' "
                f"not in NODE_TYPES (cleaned: '{clean}')"
            )


def test_template_port_names_match():
    """Verify template edge sourcePort/targetPort are real port names."""
    for tpl_name, tpl in TEMPLATES.items():
        node_map = {n["id"]: n for n in tpl["nodes"]}

        for edge in tpl["edges"]:
            src_node = node_map.get(edge["source"])
            tgt_node = node_map.get(edge["target"])

            assert src_node is not None, f"Template '{tpl_name}': source node {edge['source']} not found"
            assert tgt_node is not None, f"Template '{tpl_name}': target node {edge['target']} not found"

            src_type = src_node["type"].replace("wf_", "", 1) if src_node["type"].startswith("wf_") else src_node["type"]
            tgt_type = tgt_node["type"].replace("wf_", "", 1) if tgt_node["type"].startswith("wf_") else tgt_node["type"]

            src_nt = NODE_TYPES.get(src_type)
            tgt_nt = NODE_TYPES.get(tgt_type)

            if src_nt:
                src_port = edge["sourcePort"]
                if isinstance(src_port, str):
                    src_port_names = [p.name for p in src_nt.outputs]
                    assert src_port in src_port_names, (
                        f"Template '{tpl_name}': {src_type} has no output port '{src_port}' "
                        f"(available: {src_port_names})"
                    )

            if tgt_nt:
                tgt_port = edge["targetPort"]
                if isinstance(tgt_port, str):
                    tgt_port_names = [p.name for p in tgt_nt.inputs]
                    assert tgt_port in tgt_port_names, (
                        f"Template '{tpl_name}': {tgt_type} has no input port '{tgt_port}' "
                        f"(available: {tgt_port_names})"
                    )


def test_all_node_types_have_ports():
    """Every node type with inputs/outputs has valid port definitions."""
    for key, nt in NODE_TYPES.items():
        for p in nt.inputs:
            assert bool(p.type), f"{key} input '{p.name}': missing type"
            assert bool(p.label), f"{key} input '{p.name}': missing label"
        for p in nt.outputs:
            assert bool(p.type), f"{key} output '{p.name}': missing type"
            assert bool(p.label), f"{key} output '{p.name}': missing label"


def test_no_duplicate_port_names():
    """No node type should have duplicate port names."""
    for key, nt in NODE_TYPES.items():
        input_names = [p.name for p in nt.inputs]
        dup_inputs = [n for n in input_names if input_names.count(n) > 1]
        assert len(set(dup_inputs)) == 0, f"{key}: duplicate input ports: {list(set(dup_inputs))}"

        output_names = [p.name for p in nt.outputs]
        dup_outputs = [n for n in output_names if output_names.count(n) > 1]
        assert len(set(dup_outputs)) == 0, f"{key}: duplicate output ports: {list(set(dup_outputs))}"


def test_all_required_node_types_registered():
    """Verify all node types referenced in templates + pipeline_map are registered."""
    template_types = set()
    for tpl in TEMPLATES.values():
        for n in tpl["nodes"]:
            t = n["type"].replace("wf_", "", 1) if n["type"].startswith("wf_") else n["type"]
            template_types.add(t)

    pipeline_types = set(node_pipeline_map().keys())

    all_expected = template_types | pipeline_types | {"file_input", "text_input", "output_file", "text_to_image"}
    for t in sorted(all_expected):
        assert t in NODE_TYPES, f"Type '{t}' missing from NODE_TYPES (not registered)"


def test_categories_valid():
    """All node types have a valid category."""
    valid_categories = set(CATEGORIES.keys())
    for key, nt in NODE_TYPES.items():
        assert nt.category in valid_categories, (
            f"{key}: category '{nt.category}' not in valid categories: {sorted(valid_categories)}"
        )


@pytest.mark.asyncio
async def test_api_node_types():
    """Verify /api/node-types returns all registered node types."""
    import httpx

    server_url = "http://127.0.0.1:8080"

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{server_url}/api/node-types")
    except Exception as e:
        pytest.skip(f"Cannot reach server at {server_url}: {e}")

    if r.status_code != 200:
        pytest.fail(f"API returned {r.status_code}")

    data = r.json()
    api_types = data.get("types", [])
    api_ids = {t["id"] for t in api_types}

    for key, nt in NODE_TYPES.items():
        assert key in api_ids, f"API missing type '{key}'"

    for tid in api_ids:
        assert tid in NODE_TYPES, f"API has extra type '{tid}' not in NODE_TYPES"


# ═══════════════════════════════════════════════════════════
# Phase 4: Mesh node verification
# ═══════════════════════════════════════════════════════════

def test_mesh_boolean_node_registered():
    """mesh_boolean is registered in NODE_TYPES."""
    assert "mesh_boolean" in NODE_TYPES


def test_mesh_stitch_node_registered():
    """mesh_stitch is registered in NODE_TYPES."""
    assert "mesh_stitch" in NODE_TYPES


def test_mesh_cut_node_registered():
    """mesh_cut is registered in NODE_TYPES."""
    assert "mesh_cut" in NODE_TYPES


def test_mesh_decorate_node_registered():
    """mesh_decorate is registered in NODE_TYPES."""
    assert "mesh_decorate" in NODE_TYPES


def test_mesh_transform_node_registered():
    """mesh_transform is registered in NODE_TYPES."""
    assert "mesh_transform" in NODE_TYPES


def test_mesh_select_node_registered():
    """mesh_select is registered in NODE_TYPES."""
    assert "mesh_select" in NODE_TYPES


def test_mesh_align_node_registered():
    """mesh_align is registered in NODE_TYPES."""
    assert "mesh_align" in NODE_TYPES


def test_mesh_boolean_bool_op_is_choice():
    """mesh_boolean's bool_op param is a choice type, not bare string."""
    nt = NODE_TYPES["mesh_boolean"]
    bool_op = nt.params.get("bool_op", {})
    assert bool_op.get("type") == "choice"
    assert "union" in bool_op.get("choices", [])
    assert "difference" in bool_op.get("choices", [])


def test_mesh_stitch_params_are_typed():
    """mesh_stitch params have proper type definitions."""
    nt = NODE_TYPES["mesh_stitch"]
    stitch_smooth = nt.params.get("stitch_smooth", {})
    assert stitch_smooth.get("type") == "int"
    assert stitch_smooth.get("min") == 0
    stitch_lambda = nt.params.get("stitch_lambda", {})
    assert stitch_lambda.get("type") == "float"


def test_mesh_cut_params_are_typed():
    """mesh_cut params have proper type definitions."""
    nt = NODE_TYPES["mesh_cut"]
    cut_fill = nt.params.get("cut_fill", {})
    assert cut_fill.get("type") == "bool"
    cut_plane_co = nt.params.get("cut_plane_co", {})
    assert cut_plane_co.get("type") == "string"


def test_param_meta_qualified_key_mesh_simplify_method():
    """PARAM_META has qualified key 'mesh_simplify:method' with correct label."""
    meta = PARAM_META.get("mesh_simplify:method", {})
    assert meta.get("label") == "Method"
    assert "label_zh" in meta


def test_param_meta_qualified_key_image_grayscale_method():
    """PARAM_META has qualified key 'image_grayscale:method' with correct label."""
    meta = PARAM_META.get("image_grayscale:method", {})
    assert meta.get("label") == "Method"
    assert "label_zh" in meta


def test_param_meta_qualified_keys_distinct_from_bare():
    """The bare 'method' key is NOT the mesh_simplify or image_grayscale version."""
    # The qualified keys are separate entries from any bare 'method' key
    bare_method = PARAM_META.get("method", {})
    qualified = PARAM_META.get("mesh_simplify:method", {})
    # They should be different dicts (not same object)
    if bare_method:
        assert bare_method is not qualified


def test_node_input_port_map_includes_mesh_nodes():
    """node_input_port_map() includes all new mesh node types."""
    port_map = node_input_port_map()
    mesh_nodes = {
        "mesh_boolean": "mesh_a",
        "mesh_stitch": "mesh",
        "mesh_cut": "mesh",
        "mesh_align": "mesh_a",
        "mesh_decorate": "mesh",
        "mesh_transform": "mesh",
        "mesh_select": "mesh",
        "mesh_simplify": "mesh",
        "mesh_smooth": "mesh",
        "mesh_scale": "mesh",
    }
    for node_type, expected_port in mesh_nodes.items():
        assert node_type in port_map, f"node_input_port_map() missing '{node_type}'"
        assert port_map[node_type] == expected_port, (
            f"'{node_type}' primary port: expected '{expected_port}', got '{port_map[node_type]}'"
        )