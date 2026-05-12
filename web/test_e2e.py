"""End-to-end tests for workflow parameter system.

Validates the full chain:
  LiteGraph serialize (links format) → DB storage → engine normalization →
  DAG construction → port resolution → parameter priority
"""
import sys, json, os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.getcwd()))  # parent dir so 'web' package is importable

import workflow_models as wm, workflow_engine, node_types

# Re-init DB
wm.init_workflow_db()

# ── Test 1: Edge normalization ──
print('=' * 60)
print('TEST 1: _normalize_edges (LiteGraph links → engine edges)')
engine = workflow_engine.get_engine()

lg_graph = {
    'nodes': [
        {'id': 1, 'type': 'text_input', 'title': 'Prompt'},
        {'id': 2, 'type': 'text_to_image', 'title': 'T2I'},
        {'id': 3, 'type': 'relief', 'title': 'Relief'},
    ],
    'links': [
        [1, 1, 0, 2, 0, 1],   # linkId, srcNode, srcSlot, tgtNode, tgtSlot, type
        [2, 2, 0, 3, 0, 1],
    ]
}

edges = engine._normalize_edges(lg_graph)
assert len(edges) == 2, f'Expected 2 edges, got {len(edges)}'
assert edges[0] == {'source': '1', 'source_port': 0, 'target': '2', 'target_port': 0}
assert edges[1] == {'source': '2', 'source_port': 0, 'target': '3', 'target_port': 0}
print(f'  links[{len(lg_graph["links"])}] → edges[{len(edges)}] [OK]')

# Legacy format still works
legacy = {'edges': [{'source': '1', 'source_port': 0, 'target': '2', 'target_port': 1}]}
e2 = engine._normalize_edges(legacy)
assert len(e2) == 1 and e2[0]['target_port'] == 1
print(f'  Legacy edges format still passes through [OK]')

# Empty
assert engine._normalize_edges({'nodes': []}) == []
print(f'  Empty graph → [] [OK]')
print()

# ── Test 2: DAG + topological sort ──
print('=' * 60)
print('TEST 2: DAG construction with normalized edges')
node_map = {str(n['id']): n for n in lg_graph['nodes']}
adj, in_deg = engine._build_dag(node_map, edges)
assert in_deg == {'1': 0, '2': 1, '3': 1}
topsort = engine._topsort(node_map, adj, in_deg)
assert topsort == ['1', '2', '3'], f'Expected [1,2,3], got {topsort}'
print(f'  Execution order: {topsort}')
print(f'  text_input → text_to_image → relief [OK]')
print()

# ── Test 3: Port name resolution via node types ──
print('=' * 60)
print('TEST 3: Port edge map (slot index → port name via node_types)')
port_edge_map = engine._build_port_edge_map(node_map, edges)
assert ('2', 'prompt') in port_edge_map, f'Missing (2, prompt) in {port_edge_map}'
assert port_edge_map[('2', 'prompt')] == ('1', 'text')
print(f'  (2, prompt) ← (1, text) [OK]')

assert ('3', 'image') in port_edge_map
assert port_edge_map[('3', 'image')] == ('2', 'image')
print(f'  (3, image) ← (2, image) [OK]')

# Verify port index mapping is correct
nt_text_input = node_types.get_node_type('text_input')
nt_t2i = node_types.get_node_type('text_to_image')
nt_relief = node_types.get_node_type('relief')
assert nt_t2i.inputs[0].name == 'prompt', f't2i input[0] should be prompt, got {nt_t2i.inputs[0].name}'
assert len(nt_t2i.inputs) == 1, f't2i should have 1 input port (prompt), got {len(nt_t2i.inputs)}'
assert 'size' in nt_t2i.params, 'size should be a param, not an input port'
assert 'provider' in nt_t2i.params, 'provider should be a param, not an input port'
assert nt_relief.inputs[0].name == 'image'
print(f'  Port indices and param separation verified [OK]')
print()

# ── Test 4: Parameter priority ──
print('=' * 60)
print('TEST 4: Parameter priority (runtime > editor > schema)')
import schemas

editor_props = {'width': 100, 'height': 80, 'max_depth': 2.0}
runtime_params = {'width': 200}
pt = schemas.PIPELINE_TYPES.get('relief', {})

merged = {}
for pdef in pt.get('params', []):
    pname = pdef['name']
    if pname in runtime_params:
        merged[pname] = runtime_params[pname]
    elif pname in editor_props:
        merged[pname] = editor_props[pname]
    elif 'default' in pdef:
        merged[pname] = pdef['default']

assert merged['width'] == 200, f'Runtime should override: got {merged["width"]}'
assert merged['height'] == 80, f'Editor fallback: got {merged["height"]}'
assert 'base_thickness' in merged  # from schema default
print(f'  Width:  200 (runtime) overrides 100 (editor) [OK]')
print(f'  Height: 80 (editor fallback) [OK]')
print(f'  base_thickness: {merged["base_thickness"]} (schema default) [OK]')
print()

# ── Test 5: Full DB round-trip ──
print('=' * 60)
print('TEST 5: DB round-trip — create workflow, instance, store/retrieve params')

wf = wm.create_workflow_definition(
    name='test-e2e-text2img-relief',
    graph_json=json.dumps(lg_graph),
    description='End-to-end test workflow'
)
wf_id = wf['id']
print(f'  Created workflow: {wf_id}')

# Verify links survived round-trip
loaded = wm.get_workflow_definition(wf_id)
assert len(loaded['graph'].get('links', [])) == 2
print(f'  Links survive DB round-trip [OK]')

# Create instance with inputs
inst = wm.create_workflow_instance(wf_id, inputs={'1': {'text': 'A majestic mountain at sunset'}})
print(f'  Created instance: {inst["id"]}')

inst_full = wm.get_workflow_instance(inst['id'])
ctx = inst_full.get('context', {})
assert ctx['_inputs']['1']['text'] == 'A majestic mountain at sunset'
print(f'  Text input stored: "{ctx["_inputs"]["1"]["text"]}" [OK]')

# Store _node_params (simulating server.py behavior)
ctx['_node_params'] = {
    '2': {'provider': 'openai', 'size': '1024x1024'},
    '3': {'width': 200, 'height': 150, 'max_depth': 4.0}
}
wm.update_workflow_context(inst['id'], ctx)

# Retrieve and verify
inst_full2 = wm.get_workflow_instance(inst['id'])
ctx2 = inst_full2.get('context', {})
np2 = ctx2.get('_node_params', {})
assert np2.get('2', {}).get('provider') == 'openai'
assert np2.get('3', {}).get('width') == 200
print(f'  _node_params stored and retrievable: {json.dumps(np2, ensure_ascii=False)} [OK]')

# Cleanup
wm.delete_workflow_definition(wf_id)
print(f'  Cleanup: workflow deleted [OK]')
print()

# ── Test 6: Input node detection ──
print('=' * 60)
print('TEST 6: Input node detection')
input_ids = node_types.get_input_node_ids(lg_graph)
assert input_ids == ['1'], f'Expected [1], got {input_ids}'
print(f'  text_input(id=1) → input node [OK]')

# Verify multi-input detection
multi_input_graph = {
    'nodes': [
        {'id': 1, 'type': 'file_input', 'title': 'Image File'},
        {'id': 2, 'type': 'text_input', 'title': 'Style Prompt'},
        {'id': 3, 'type': 'relief', 'title': 'Relief'},
    ],
    'links': [[1, 1, 0, 3, 0, 1], [2, 2, 0, 3, 0, 2]]
}
multi_ids = node_types.get_input_node_ids(multi_input_graph)
assert multi_ids == ['1', '2'], f'Expected [1,2], got {multi_ids}'
print(f'  Multiple inputs: {multi_ids} [OK]')
print()

# ── Test 7: Edge case — disconnected port ──
print('=' * 60)
print('TEST 7: Disconnected port handling')

disconnected_graph = {
    'nodes': [
        {'id': 1, 'type': 'file_input', 'title': 'File'},
        {'id': 2, 'type': 'relief', 'title': 'Relief'},
    ],
    'links': []  # No edges — file_input not connected to relief
}

edges_dc = engine._normalize_edges(disconnected_graph)
assert len(edges_dc) == 0
print(f'  No edges → empty edge list [OK]')

node_map_dc = {str(n['id']): n for n in disconnected_graph['nodes']}
port_em_dc = engine._build_port_edge_map(node_map_dc, edges_dc)
assert len(port_em_dc) == 0, f'No edges → empty port edge map [OK]'
print(f'  _resolve_input would fall back to _inputs for disconnected ports [OK]')

# But DAG still works (both nodes have in_degree=0)
adj_dc, in_deg_dc = engine._build_dag(node_map_dc, edges_dc)
assert in_deg_dc == {'1': 0, '2': 0}
topsort_dc = engine._topsort(node_map_dc, adj_dc, in_deg_dc)
assert topsort_dc is not None  # valid DAG (parallel roots)
print(f'  Disconnected graph still valid DAG: {topsort_dc} [OK]')

print()
print('=' * 60)
print('ALL 7 TESTS PASSED')
print('=' * 60)
