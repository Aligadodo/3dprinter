# Workflow System Guide

## Overview

The workflow system allows you to chain multiple pipeline stages into a **Directed Acyclic Graph (DAG)** for end-to-end automated processing. Each node represents a processing step, and connections between nodes pass file paths.

Typical workflow: `Text → Image → Relief → Mesh Repair → Output`

## Node Types

The system provides **20 node types** in 4 categories:

### Input

| Node | Input | Output | Description |
|------|-------|--------|-------------|
| File Input | — | file | Upload a file as workflow input |
| Text Input | — | text | Text input (e.g. prompt) for downstream nodes |

### Generate

| Node | Input | Output | Description |
|------|-------|--------|-------------|
| Text → Image | prompt, size, provider | image | Call AI API to generate image (4 providers) |

### Process

#### Image → 3D

| Node | Input | Output | Description |
|------|-------|--------|-------------|
| Relief | image | stl, color_preview | CPU task, image to bas-relief |
| Lithophane | image | stl, color_preview | CPU task, image to lithophane |
| Layered Relief | image | stl, 3mf, color_map, color_preview | CPU task, multi-color relief |
| TripoSR | image | mesh, preview | GPU task, fast AI 3D modeling |
| Hunyuan3D | image | mesh, preview | GPU task, high-quality AI 3D |

#### Mesh Processing

| Node | Input | Output | Description |
|------|-------|--------|-------------|
| Views | mesh | grid, views_dir | CPU task, render 6 ortho views |
| Repair | mesh | repaired_mesh | CPU task, repair & waterproof mesh |
| Simplify | mesh | mesh | CPU task, decimate to reduce file size |
| Smooth | mesh | mesh | CPU task, Taubin smoothing to reduce noise |
| Scale | mesh | mesh | CPU task, scale by factor or target size |

#### Image Processing (inline PIL nodes, no subprocess)

| Node | Input | Output | Description |
|------|-------|--------|-------------|
| Resize | image | image | Resize image, 5 fit modes |
| Grayscale | image | image | Convert to grayscale, 6 methods |
| Crop | image | image | Crop image, preset aspect ratios |
| Adjust | image | image | Brightness/contrast/saturation/sharpness |
| Convert | image | image | Convert format (PNG/JPEG/WebP etc.) |
| Remove BG | image | image, mask | AI background removal, optional color replacement |

### Output

| Node | Input | Output | Description |
|------|-------|--------|-------------|
| Output | file | — | Mark workflow output files (downloadable as ZIP) |

## Using the Editor

### Opening the Editor

Navigate to the "Workflow Editor" page, or select an existing workflow from the workflow list.

### Adding Nodes

Drag nodes from the left panel onto the canvas. Nodes are grouped by category:
- **Input**: File Input, Text Input
- **Generate**: Text → Image
- **Process**: Relief, Lithophane, Layered Relief, TripoSR, Hunyuan3D, Views, Repair, Simplify, Smooth, Scale, Resize, Grayscale, Crop, Adjust, Convert, Remove BG
- **Output**: Output

### Connecting Nodes

Drag from a node's **output port** (right-side dot) to another node's **input port** (left-side dot). The connection line represents data flow. Port types must match (image→image, mesh→mesh).

### Configuring Parameters

Click a node to view and modify its parameters. Each node has sensible defaults that can be adjusted as needed. All parameters are labeled in both Chinese and English.

### Built-in Templates

The editor provides 4 preset templates:

1. **Basic**: `Text→Image→Relief` — Simplest text-to-3D flow
2. **Advanced**: `Text→Image→Layered Relief→Repair` — Full flow with multi-color and repair
3. **Full**: `Text→Image→3D→Views` — AI high-quality modeling with six-view output
4. **Image Processing**: `File Input→Resize→Remove BG→Convert` — Pure image processing chain

## Execution Flow

1. Click **Save** to persist the workflow definition
2. Click **Run** → a dialog opens for optional input configuration
3. The system creates a new workflow instance
4. The engine performs topological sort (Kahn's algorithm) on the DAG to determine execution order
5. Parallel branches execute concurrently; serial dependencies wait in order
6. Real-time progress displayed in the Runner page during execution:
   - Left: Node tabs (click to view different node outputs)
   - Center: Node detail panel (input/output files, parameters, logs)
   - Right/Top: Real-time DAG status graph
7. Results displayed when all nodes complete; ZIP download available

## Runner Interface

The Runner page uses a partitioned layout:

```
┌──────────┬──────────────────────────────────┐
│ Node Tab │  DAG Status Graph                 │
│ ─────── │  (Gray=Pending / Blue=Running /   │
│ ✓Relief   │   Green=Done / Red=Failed)       │
│ ▶Repair   │                                  │
│   Views   ├──────────────────────────────────┤
│          │  Node Detail Panel                 │
│          │  Output preview (image/STL/3D)    │
│          │  Parameters / Log / Sub-task link  │
└──────────┴──────────────────────────────────┘
```

## DAG Execution Rules

- Uses **Kahn's algorithm** for topological sorting
- Nodes with no dependencies (in-degree 0) can execute in parallel
- Nodes pass data via **file paths** (not binary data)
- After an upstream node completes, downstream nodes automatically receive its output file paths
- If any node fails, the workflow is marked as failed and subsequent nodes stop
- Inline nodes (image processing) execute in-process via PIL, without going through the subprocess scheduler

## Monitoring & Debugging

- Running workflows show a real-time DAG view with node status colors:
  - Gray = Pending
  - Blue = Running
  - Green = Completed
  - Red = Failed
- Click a node tab to view that node's output files and details
- Click images to enlarge; click STL files to download
- Running workflows can be cancelled at any time
- Failed workflows can be replayed with the Replay button

## Best Practices

1. **Start small** — Test simple 2-3 node flows before building complex DAGs
2. **Use templates** — Start from preset templates and adjust to your needs
3. **Mind GPU nodes** — GPU nodes execute serially; plan accordingly to avoid bottlenecks
4. **Add Repair nodes** — Add a repair step before final output to ensure print quality
5. **Use Output nodes** — Mark which files are the workflow's final outputs
6. **Leverage image nodes** — Remove BG, Resize, etc. execute in-engine and don't consume task queue slots
7. **Match port types** — image→image, mesh→mesh connections only; type mismatch prevents linking
