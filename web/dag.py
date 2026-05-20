"""dag.py - Pure DAG computation functions for workflow engine.

All functions here are pure (no I/O, no async, no side effects) and can be
tested with only unit tests. This module is the algorithm layer;
workflow_executor.py handles execution, event emission, and I/O.
"""

import os
from collections import deque

from web import node_types as nt

# Extensions mapped to port types for output file matching
PORT_TYPE_EXTENSIONS = {
    "stl": [".stl"],
    "mesh": [".stl", ".obj", ".glb", ".3mf"],
    "image": [".png", ".jpg", ".jpeg", ".webp", ".bmp"],
    "json": [".json"],
    "file": [".stl", ".obj", ".glb", ".3mf", ".png", ".jpg", ".jpeg", ".json", ".txt"],
    "dir": None,
    "any": None,
}

# File extension sets for input validation against port types
_PORT_EXTENSIONS = {
    "image": {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff", ".tif"},
    "stl": {".stl"},
    "mesh": {".stl", ".obj", ".glb", ".gltf", ".3mf", ".ply"},
    "file": {".stl", ".obj", ".glb", ".gltf", ".3mf", ".ply",
             ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".json", ".txt"},
}


def validate_file_for_port(file_path: str, port_type: str):
    """Check if a file's extension matches the expected port type.

    Returns a warning string if mismatched, or None if compatible.
    """
    if not file_path or not port_type:
        return None
    if port_type in ("*", "any", "string", "dir"):
        return None
    ext = os.path.splitext(file_path)[1].lower()
    expected = _PORT_EXTENSIONS.get(port_type)
    if expected is None:
        return None  # Unknown port type — allow
    if ext not in expected:
        expected_list = sorted(expected)
        return (f"File '{os.path.basename(file_path)}' (extension {ext}) may not be "
                f"compatible with port type '{port_type}'. Expected: {expected_list}")
    return None


def normalize_edges(graph: dict) -> list[dict]:
    """Normalize edges from LiteGraph 'links' array or legacy 'edges' format.

    LiteGraph serializes: {"links": [[linkId, srcId, srcSlot, tgtId, tgtSlot, type], ...]}
    Returns:            [{"source": srcId, "source_port": srcSlot, "target": tgtId, "target_port": tgtSlot}, ...]
    """
    edges = graph.get("edges", [])
    if edges:
        return edges

    links = graph.get("links", [])
    if not links:
        return []

    normalized = []
    for link in links:
        if not isinstance(link, (list, tuple)) or len(link) < 5:
            continue
        normalized.append({
            "source": str(link[1]),
            "source_port": link[2],
            "target": str(link[3]),
            "target_port": link[4],
        })
    return normalized


def build_dag(node_map: dict, edges: list[dict]):
    """Build adjacency list and in-degree map from nodes + edges.

    Returns: (adj: dict[str, list[str]], in_degree: dict[str, int])
    """
    adj = {nid: [] for nid in node_map}
    in_degree = {nid: 0 for nid in node_map}
    for e in edges:
        src = str(e.get("source") or e.get("source_node"))
        tgt = str(e.get("target") or e.get("target_node"))
        if src in adj and tgt in in_degree:
            adj[src].append(tgt)
            in_degree[tgt] += 1
    return adj, in_degree


def enrich_ctx(nid, resolved_inputs, resolved_params, ctx, edge_map):
    """After node execution, write cascade metadata into ctx[nid].

    Preserves handler-computed _inputs and _params if already set.
    Only fills defaults when the handler didn't set them.
    """
    if str(nid) not in ctx:
        ctx[str(nid)] = {}

    node_ctx = ctx[str(nid)]
    # Don't overwrite metadata already set by the handler
    if "_inputs" not in node_ctx:
        node_ctx["_inputs"] = dict(resolved_inputs or {})
    if "_params" not in node_ctx:
        node_ctx["_params"] = dict(resolved_params or {})

    # Build upstream: merge all direct upstream node contexts
    upstream = {}
    for (tgt_id, tgt_port), (src_id, src_port) in edge_map.items():
        if tgt_id == str(nid):
            src_ctx = ctx.get(str(src_id), {})
            if isinstance(src_ctx, dict):
                upstream[str(src_id)] = dict(src_ctx)
            # Also pull in that source's own _upstream
            src_upstream = src_ctx.get("_upstream", {})
            if isinstance(src_upstream, dict):
                for uk, uv in src_upstream.items():
                    if uk not in upstream:
                        upstream[uk] = dict(uv) if isinstance(uv, dict) else uv

    node_ctx["_upstream"] = upstream


def topsort(node_map: dict, adj: dict, in_degree: dict) -> list[str] | None:
    """Kahn's topological sort. Returns None if graph contains a cycle."""
    deg = dict(in_degree)  # copy to avoid mutating caller's dict
    queue = deque([nid for nid, d in deg.items() if d == 0])
    order = []
    while queue:
        nid = queue.popleft()
        order.append(nid)
        for neighbor in adj.get(nid, []):
            deg[neighbor] -= 1
            if deg[neighbor] == 0:
                queue.append(neighbor)
    return order if len(order) == len(node_map) else None


def build_port_edge_map(node_map: dict, edges: list[dict]) -> dict:
    """Build edge_map: (target_nid, target_port_name) → (source_nid, source_port_name).

    Translates numeric slot indices to port names using node_types definitions.
    Returns: {("target_nid", "port_name"): ("source_nid", "port_name"), ...}
    """
    edge_map = {}
    for e in edges:
        src_nid = str(e.get("source") or e.get("source_node"))
        tgt_nid = str(e.get("target") or e.get("target_node"))
        src_slot = e.get("source_port", 0)
        tgt_slot = e.get("target_port", 0)

        if src_nid not in node_map or tgt_nid not in node_map:
            continue

        src_type = node_map[src_nid].get("type", "")
        tgt_type = node_map[tgt_nid].get("type", "")

        src_nt = nt.get_node_type(src_type)
        tgt_nt = nt.get_node_type(tgt_type)

        src_port_name = None
        if src_nt and isinstance(src_slot, int) and src_slot < len(src_nt.outputs):
            src_port_name = src_nt.outputs[src_slot].name
        elif isinstance(src_slot, str):
            src_port_name = src_slot

        tgt_port_name = None
        if tgt_nt and isinstance(tgt_slot, int) and tgt_slot < len(tgt_nt.inputs):
            tgt_port_name = tgt_nt.inputs[tgt_slot].name
        elif isinstance(tgt_slot, str):
            tgt_port_name = tgt_slot

        if src_port_name is not None and tgt_port_name is not None:
            edge_map[(tgt_nid, tgt_port_name)] = (src_nid, src_port_name)

    return edge_map


def build_upstream(nid: str, ctx: dict, edge_map: dict) -> dict:
    """Build a flat cascade index of all upstream values for a node.

    Returns dict with keys like:
      "1.text"        — upstream node's direct output
      "2.image"       — upstream node's direct output
      "2._params.size" — upstream node's resolved param
    """
    cascade = {}
    visited = set()

    # BFS upstream through edge_map
    queue = deque()
    for (tgt_id, tgt_port), (src_id, src_port) in edge_map.items():
        if tgt_id == str(nid) and src_id not in visited:
            visited.add(src_id)
            queue.append(str(src_id))

    while queue:
        src_id = queue.popleft()
        src_ctx = ctx.get(src_id, {})
        if not isinstance(src_ctx, dict):
            continue

        for key, val in src_ctx.items():
            if not key.startswith("_"):
                cascade[f"{src_id}.{key}"] = val

        params = src_ctx.get("_params", {})
        if isinstance(params, dict):
            for pk, pv in params.items():
                cascade[f"{src_id}._params.{pk}"] = pv

        inputs = src_ctx.get("_inputs", {})
        if isinstance(inputs, dict):
            for ik, iv in inputs.items():
                cascade[f"{src_id}._inputs.{ik}"] = iv

        for (tgt_id, tgt_port), (s_id, s_port) in edge_map.items():
            if tgt_id == src_id and s_id not in visited:
                visited.add(s_id)
                queue.append(str(s_id))

    return cascade


# ── Port type compatibility ────────────────────────────────────────────────

# Cross-type compatibility rules. Rules are checked in order; first match wins.
# Each rule: (src_type, tgt_type) — matches when actual src==rule_src AND actual tgt==rule_tgt.
# Rules are directional: src→tgt.
_PORT_COMPAT_RULES = [
    ("file",   "image"),
    ("file",   "stl"),
    ("file",   "mesh"),
    ("string", "image"),
    ("stl",    "mesh"),
    ("mesh",   "stl"),
    ("json",   "string"),
    ("json",   "json"),
    ("dir",    "any"),
]

_WILDCARD_TYPES = {"*", "any"}

def _port_types_compatible(src_type: str, tgt_type: str) -> bool:
    """Check if two port types are compatible."""
    if not src_type or not tgt_type:
        return True
    if src_type == tgt_type:
        return True
    # Explicit wildcard ports accept/produce anything
    if src_type in _WILDCARD_TYPES or tgt_type in _WILDCARD_TYPES:
        return True
    for rule_src, rule_tgt in _PORT_COMPAT_RULES:
        if rule_src == src_type and rule_tgt == tgt_type:
            return True
    return False


def validate_port_compatibility(node_map: dict, edges: list[dict]) -> list[str]:
    """Validate that all edges connect compatible port types.

    Returns a list of error messages (empty = all good).
    """
    errors = []
    for e in edges:
        src_nid = str(e.get("source") or e.get("source_node"))
        tgt_nid = str(e.get("target") or e.get("target_node"))
        src_slot = e.get("source_port", 0)
        tgt_slot = e.get("target_port", 0)

        src_node = node_map.get(src_nid, {})
        tgt_node = node_map.get(tgt_nid, {})

        src_type = src_node.get("type", "")
        tgt_type = tgt_node.get("type", "")

        src_nt = nt.get_node_type(src_type)
        tgt_nt = nt.get_node_type(tgt_type)

        src_port_type = None
        src_port_name = str(src_slot)
        if src_nt and isinstance(src_slot, int) and src_slot < len(src_nt.outputs):
            src_port_type = src_nt.outputs[src_slot].type
            src_port_name = src_nt.outputs[src_slot].name
        elif src_nt and isinstance(src_slot, str):
            for op in src_nt.outputs:
                if op.name == src_slot:
                    src_port_type = op.type
                    break
            src_port_name = src_slot

        tgt_port_type = None
        tgt_port_name = str(tgt_slot)
        if tgt_nt and isinstance(tgt_slot, int) and tgt_slot < len(tgt_nt.inputs):
            tgt_port_type = tgt_nt.inputs[tgt_slot].type
            tgt_port_name = tgt_nt.inputs[tgt_slot].name
        elif tgt_nt and isinstance(tgt_slot, str):
            for ip in tgt_nt.inputs:
                if ip.name == tgt_slot:
                    tgt_port_type = ip.type
                    break
            tgt_port_name = tgt_slot

        if src_port_type and tgt_port_type:
            if not _port_types_compatible(src_port_type, tgt_port_type):
                src_label = src_node.get("title") or src_type or src_nid
                tgt_label = tgt_node.get("title") or tgt_type or tgt_nid
                errors.append(
                    f"Port type mismatch: '{src_label}' (#{src_nid}) output "
                    f"'{src_port_name}' [{src_port_type}] → '{tgt_label}' (#{tgt_nid}) "
                    f"input '{tgt_port_name}' [{tgt_port_type}]"
                )

    return errors


def resolve_input(node_id: str, port_name: str, edge_map: dict, ctx: dict):
    """Resolve an input port value from upstream nodes or external inputs.

    Priority: runtime edge overrides > saved edges > external inputs.
    Returns: the resolved value or None.
    """
    nid = str(node_id)

    # 1. Runtime edge overrides
    node_inputs = ctx.get("_node_inputs", {})
    if nid in node_inputs and port_name in node_inputs[nid]:
        override = node_inputs[nid][port_name]
        src_node = str(override.get("source_node", ""))
        src_port = override.get("source_port", "")
        if src_node and src_port:
            src_ctx = ctx.get(src_node, {})
            val = src_ctx.get(src_port)
            if val is not None:
                return val

    # 2. Saved graph edges
    key = (nid, port_name)
    if key in edge_map:
        src_node, src_port = edge_map[key]
        src_ctx = ctx.get(src_node, {})
        val = src_ctx.get(src_port)
        if val is not None:
            return val

    # 3. External inputs
    ext = ctx.get("_inputs", {}).get(nid, {})
    return ext.get(port_name)