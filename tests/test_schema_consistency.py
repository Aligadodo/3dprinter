"""test_schema_consistency.py — Verify frontend/backend data structure consistency.

Validates that:
1. All template node types exist in NODE_TYPES registry
2. Template port names match node type port definitions
3. NODE_TYPES keys match their NodeType.id fields
4. API /api/node-types returns all registered nodes
5. All required port names (used in templates/edges) are valid

Usage:
    python tests/test_schema_consistency.py
    python tests/test_schema_consistency.py --api    # also test live API
"""

import argparse
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web.node_types import NODE_TYPES, all_node_types, CATEGORIES, PortSpec, NodeType

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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
    log("\n── NODE_TYPES self-consistency ──", "hdr")
    for key, nt in NODE_TYPES.items():
        check(f"NODE_TYPES['{key}'].id == '{key}'", nt.id == key,
              f"got id='{nt.id}'")


def test_all_template_types_exist():
    """Verify every template node type exists in NODE_TYPES."""
    log("\n── Template type validity ──", "hdr")
    for tpl_name, tpl in TEMPLATES.items():
        for node in tpl["nodes"]:
            type_id = node["type"]
            # Strip wf_ prefix if present (frontend strips it before lookup)
            clean = type_id.replace("wf_", "", 1) if type_id.startswith("wf_") else type_id
            exists = clean in NODE_TYPES
            check(f"Template '{tpl_name}' node #{node['id']} type '{type_id}' exists",
                  exists,
                  f"'{clean}' not in NODE_TYPES keys: {sorted(NODE_TYPES.keys())}")


def test_template_port_names_match():
    """Verify template edge sourcePort/targetPort are real port names."""
    log("\n── Template port name validity ──", "hdr")
    for tpl_name, tpl in TEMPLATES.items():
        # Build node map
        node_map = {n["id"]: n for n in tpl["nodes"]}

        for edge in tpl["edges"]:
            src_node = node_map.get(edge["source"])
            tgt_node = node_map.get(edge["target"])

            if not src_node or not tgt_node:
                check(f"Template '{tpl_name}' edge {edge['source']}→{edge['target']}: nodes exist",
                      False, "source or target node not in template")
                continue

            # Check source port
            src_type = src_node["type"].replace("wf_", "", 1) if src_node["type"].startswith("wf_") else src_node["type"]
            src_nt = NODE_TYPES.get(src_type)
            if src_nt:
                src_port = edge["sourcePort"]
                if isinstance(src_port, str):
                    src_port_names = [p.name for p in src_nt.outputs]
                    check(f"Template '{tpl_name}': {src_type} has output port '{src_port}'",
                          src_port in src_port_names,
                          f"available: {src_port_names}")

            # Check target port
            tgt_type = tgt_node["type"].replace("wf_", "", 1) if tgt_node["type"].startswith("wf_") else tgt_node["type"]
            tgt_nt = NODE_TYPES.get(tgt_type)
            if tgt_nt:
                tgt_port = edge["targetPort"]
                if isinstance(tgt_port, str):
                    tgt_port_names = [p.name for p in tgt_nt.inputs]
                    check(f"Template '{tpl_name}': {tgt_type} has input port '{tgt_port}'",
                          tgt_port in tgt_port_names,
                          f"available: {tgt_port_names}")


def test_all_node_types_have_ports():
    """Every node type with inputs/outputs has valid port definitions."""
    log("\n── Node type port integrity ──", "hdr")
    for key, nt in NODE_TYPES.items():
        for p in nt.inputs:
            check(f"{key} input '{p.name}': has type", bool(p.type), f"type='{p.type}'")
            check(f"{key} input '{p.name}': has label", bool(p.label), f"label='{p.label}'")
        for p in nt.outputs:
            check(f"{key} output '{p.name}': has type", bool(p.type), f"type='{p.type}'")
            check(f"{key} output '{p.name}': has label", bool(p.label), f"label='{p.label}'")


def test_no_duplicate_port_names():
    """No node type should have duplicate port names."""
    log("\n── Duplicate port name check ──", "hdr")
    for key, nt in NODE_TYPES.items():
        input_names = [p.name for p in nt.inputs]
        dup_inputs = [n for n in input_names if input_names.count(n) > 1]
        check(f"{key}: no duplicate input port names",
              len(set(dup_inputs)) == 0,
              f"duplicates: {list(set(dup_inputs))}")

        output_names = [p.name for p in nt.outputs]
        dup_outputs = [n for n in output_names if output_names.count(n) > 1]
        check(f"{key}: no duplicate output port names",
              len(set(dup_outputs)) == 0,
              f"duplicates: {list(set(dup_outputs))}")


def test_all_required_node_types_registered():
    """Verify all node types referenced in templates + pipeline_map are registered."""
    log("\n── Complete node type coverage ──", "hdr")
    from web.node_types import node_pipeline_map

    # All template node types
    template_types = set()
    for tpl in TEMPLATES.values():
        for n in tpl["nodes"]:
            t = n["type"].replace("wf_", "", 1) if n["type"].startswith("wf_") else n["type"]
            template_types.add(t)

    # All pipeline-mapped types
    pipeline_types = set(node_pipeline_map().keys())

    all_expected = template_types | pipeline_types | {"file_input", "text_input", "output_file", "text_to_image"}
    for t in sorted(all_expected):
        check(f"Type '{t}' is registered", t in NODE_TYPES,
              f"missing from NODE_TYPES")


def test_categories_valid():
    """All node types have a valid category."""
    log("\n── Category validity ──", "hdr")
    valid_categories = set(CATEGORIES.keys())
    for key, nt in NODE_TYPES.items():
        check(f"{key}: category '{nt.category}' is valid",
              nt.category in valid_categories,
              f"valid: {sorted(valid_categories)}")


def test_api_node_types(server_url="http://127.0.0.1:8080"):
    """Verify /api/node-types returns all registered node types."""
    log("\n── API /api/node-types consistency ──", "hdr")
    try:
        import httpx
    except ImportError:
        log("  SKIP — httpx not installed", "skip")
        return

    try:
        r = httpx.get(f"{server_url}/api/node-types", timeout=5)
    except Exception as e:
        log(f"  SKIP — cannot reach server at {server_url}: {e}", "skip")
        return

    if r.status_code != 200:
        log(f"  FAIL — API returned {r.status_code}", "fail")
        return

    data = r.json()
    api_types = data.get("types", [])
    api_ids = {t["id"] for t in api_types}

    for key, nt in NODE_TYPES.items():
        check(f"API returns type '{key}'", key in api_ids,
              f"missing from API response")

    # Check no extra types in API that aren't in NODE_TYPES
    for tid in api_ids:
        check(f"API type '{tid}' exists in NODE_TYPES", tid in NODE_TYPES,
              f"extra type in API only")


# ═══════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════

def main():
    global PASS, FAIL

    parser = argparse.ArgumentParser(description="3D Print Pipeline — Schema Consistency Tests")
    parser.add_argument("--api", action="store_true", help="Also test against live API server")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    log("3D Print Pipeline — Schema Consistency Tests", "hdr")

    test_functions = [
        test_node_type_ids_self_consistent,
        test_all_template_types_exist,
        test_template_port_names_match,
        test_all_node_types_have_ports,
        test_no_duplicate_port_names,
        test_all_required_node_types_registered,
        test_categories_valid,
    ]

    for tf in test_functions:
        try:
            tf()
        except Exception as e:
            FAIL += 1
            log(f"  FAIL {tf.__name__} — exception: {e}", "fail")
            if args.verbose:
                import traceback
                traceback.print_exc()

    if args.api:
        try:
            test_api_node_types()
        except Exception as e:
            FAIL += 1
            log(f"  FAIL test_api_node_types — {e}", "fail")

    total = PASS + FAIL
    log(f"\n{'='*50}", "hdr")
    log(f"Schema consistency tests: {PASS} passed, {FAIL} failed ({total} total)", "hdr")
    if FAIL == 0:
        log("All schema consistency tests passed!", "ok")
    else:
        log(f"{FAIL} test(s) FAILED", "fail")
    log(f"{'='*50}", "hdr")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
