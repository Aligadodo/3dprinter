# System Architecture

## Overview

The 3D Print Pipeline is a web-based 3D printing workflow system that converts images/text/meshes into printable 3D models. It uses a **FastAPI backend + vanilla JavaScript ES Module SPA frontend** architecture with GPU task scheduling, real-time progress streaming, workflow DAG orchestration, AI text-to-image, and inline image processing.

## Tech Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Backend | **FastAPI + uvicorn** | Async-native, SSE streaming, auto API docs |
| Frontend | **Vanilla ES Module SPA** | Zero build step, hash routing, dynamic import() on-demand loading |
| Real-time | **SSE (Server-Sent Events)** | Unidirectional server push, browser auto-reconnect |
| Storage | **SQLite + WAL mode** | Zero config, file-based, concurrent reads (tasks.db + workflows.db) |
| GPU Scheduling | **asyncio.Lock** | Single GPU serialization, CPU tasks run in parallel |
| Workflow Canvas | **Litegraph.js 0.7.14** | Same library as ComfyUI, drag-and-drop DAG editor |
| Text-to-Image | **Volcengine / Zhipu / OpenAI / Stability** | Cloud APIs, provider abstraction layer, YAML + .env config |
| Docs Rendering | **Python Markdown** | Server-side markdown → HTML rendering |

## Directory Structure

```
3dprint/
├── web/                            # Web application
│   ├── server.py                   # FastAPI entry point, 32+ REST/SSE endpoints, StaticFiles mount
│   ├── scheduler.py                # Async task scheduler, GPU lock, subprocess manager
│   ├── models.py                   # SQLite database layer, task CRUD
│   ├── schemas.py                  # 10 pipeline type definitions & bilingual parameter schemas
│   ├── node_types.py               # 20 workflow node types (4 categories), bilingual param metadata
│   ├── providers.py                # Text-to-Image provider abstraction (4 providers), .env auto-load
│   ├── workflow_models.py          # Workflow DB layer (definitions/instances/node runs)
│   ├── workflow_engine.py          # DAG execution engine (Kahn topological sort, node-task mapping)
│   ├── templates/
│   │   └── index.html              # Legacy redirect (backwards compatible)
│   ├── static/                     # Modular frontend SPA
│   │   ├── index.html              # Thin entry (~50 lines)
│   │   ├── css/
│   │   │   ├── main.css            # Design tokens :root, reset, layout framework, responsive
│   │   │   ├── components.css      # Buttons/cards/forms/badges/toasts/modals/progress
│   │   │   ├── workflow.css        # Workflow editor/runner/node panel/image grid
│   │   │   └── pages.css           # Page-level layouts (stats, type-grid, preview-grid)
│   │   ├── js/
│   │   │   ├── app.js              # Entry: i18n init → route registration → boot
│   │   │   ├── i18n.js             # Locale JSON loader, t() dot-path lookup, setLang()
│   │   │   ├── api.js              # Fetch wrapper, SSE EventSource, file cache
│   │   │   ├── utils.js            # escHtml / formatTime / formatBytes / toast / context menu
│   │   │   ├── router.js           # Hash router + navigation guard + page cleanup
│   │   │   ├── pages/
│   │   │   │   ├── dashboard.js    # renderDashboard() — stats cards, task list, 5s polling
│   │   │   │   ├── new-task.js     # renderNewTask() — type selector, upload, text2img panel
│   │   │   │   ├── task-detail.js  # renderTaskDetail() — SSE log, output gallery, actions
│   │   │   │   ├── file-browse.js  # renderBrowse() — file grid gallery, right-click menu
│   │   │   │   ├── docs.js         # renderDocList() + renderDocViewer() — doc browser
│   │   │   │   ├── workflows.js    # renderWorkflowList() — workflow CRUD, template gallery
│   │   │   │   ├── wf-editor.js    # renderWorkflowEditor() — LiteGraph DAG editor
│   │   │   │   └── wf-runner.js    # renderWorkflowRunner() — SSE DAG, node tabs, output preview
│   │   │   └── components/
│   │   │       ├── node-detail.js  # renderNodeDetailPanel() — shared editor/runner component
│   │   │       └── file-modal.js   # showFileModal() — image/STL/3D preview overlay
│   │   └── locales/
│   │       ├── zh.json             # ~130 Chinese keys
│   │       └── en.json             # ~130 English keys
│   └── docs/                       # Design documentation (this directory)
│       ├── DESIGN.md               # Main design document
│       ├── architecture.zh.md      # Architecture (Chinese)
│       ├── architecture.en.md      # Architecture (English)
│       ├── pipelines.zh.md         # Pipeline reference (Chinese)
│       ├── pipelines.en.md         # Pipeline reference (English)
│       ├── workflow.zh.md          # Workflow system (Chinese)
│       ├── workflow.en.md          # Workflow system (English)
│       ├── text2img.zh.md          # Text-to-Image integration (Chinese)
│       └── text2img.en.md          # Text-to-Image integration (English)
├── scripts/                        # Python pipeline scripts
│   ├── image-to-relief.py          # Image → Bas-relief / Lithophane
│   ├── image-to-layered-relief.py  # Image → Multi-color layered relief
│   ├── image-to-3d.py              # Image → TripoSR fast 3D model
│   ├── hunyuan-to-3d.py            # Image → Hunyuan3D high-quality model
│   ├── mesh-repair.py              # Mesh repair → watertight STL
│   ├── mesh-to-views.py            # 3D mesh → 6 orthographic views
│   ├── mesh-simplify.py            # Mesh decimation (quadric/cluster)
│   ├── mesh-smooth.py              # Mesh smoothing (Taubin)
│   ├── mesh-scale.py               # Mesh scaling (factor/target size)
│   ├── text-to-image.py            # Text → AI image (4 providers)
│   └── pipeline.py                 # Pipeline base class
├── config/
│   ├── providers.yaml              # Text-to-Image provider config (4 providers, priority)
│   └── .env.example                # API key configuration template
└── output/                         # Output files directory
    ├── tasks/                      # Task working directories
    ├── relief/                     # Relief outputs
    ├── text2img/                   # Text-to-image outputs
    └── ...
```

## Data Flow

### Single Task Flow

```
User uploads file → POST /api/tasks → models.create_task()
    → scheduler.submit() → asyncio subprocess executes script
    → stdout parsed line-by-line for progress events → SSE pushed to frontend
    → Script outputs JSON result → models.update_task_status()
    → Frontend receives "complete" event → renders output files
```

### Workflow Flow

```
User edits DAG → Save workflow definition → POST /api/workflows/{id}/run
    → workflow_engine topological sort (Kahn's algorithm) → execute each node in order
    → Each node submits a sub-task to scheduler
    → Wait for sub-task completion → collect output file paths → pass to downstream nodes
    → All nodes complete → workflow_complete event
    → Frontend Runner page shows real-time DAG status colors and node progress
```

### Input Node Flow

```
User configures Text Input or File Input node
    → POST /api/workflows/{id}/inputs to set input values
    → POST /api/workflows/{id}/run carries inputs JSON
    → Engine replaces default values with user-provided inputs
```

## Task Lifecycle

```
queued → running → completed
                 → failed (retryable)
                 → cancelled
```

## SSE Event Types

| Event | Data | Trigger |
|-------|------|---------|
| `status` | `{status, message}` | Status change (queued/running) |
| `progress` | `{percent, message}` | Progress percentage update |
| `log` | `{line}` | Script stdout log line |
| `preview` | `{path, filename}` | Intermediate preview image |
| `complete` | `{output, ...}` | Task completed successfully |
| `error` | `{error, stage}` | Task failed |
| `cancelled` | `{message}` | Task cancelled |
| `done` | `{}` | SSE stream end marker |

## GPU Scheduling

- GPU tasks (TripoSR, Hunyuan3D) share a single `asyncio.Lock`
- Only one GPU task runs at a time, preventing VRAM OOM
- CPU tasks (relief, lithophane, repair, simplify, smooth, scale, etc.) bypass GPU lock, run in parallel
- Queued GPU tasks show waiting status in the UI

## API Endpoints

### Tasks
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/tasks` | List tasks (status/limit/offset params) |
| POST | `/api/tasks` | Create task (multipart: pipeline_type + params + file) |
| GET | `/api/tasks/{id}` | Task detail + output files |
| GET | `/api/tasks/{id}/workflow` | Get parent workflow context |
| DELETE | `/api/tasks/{id}` | Delete task + cascade cleanup |
| POST | `/api/tasks/{id}/cancel` | Cancel running task |
| POST | `/api/tasks/{id}/retry` | Retry failed/cancelled task |
| GET | `/api/tasks/{id}/stream` | SSE progress stream |

### Files
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/files/{path}` | Serve output files (path traversal protected) |
| POST | `/api/open-path` | Open path in OS file manager |

### Pipelines & Text-to-Image
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/pipeline-types` | All 10 pipeline types with parameter schemas |
| GET | `/api/text2img/providers` | Text-to-image provider list (no keys exposed) |
| POST | `/api/text2img` | Generate image from text prompt |
| GET | `/api/node-types` | All 20 workflow node types with port/param specs |

### Workflows
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/workflows` | List workflow definitions |
| POST | `/api/workflows` | Create/clone workflow definition |
| GET | `/api/workflows/{id}` | Workflow definition detail |
| PUT | `/api/workflows/{id}` | Update workflow definition |
| DELETE | `/api/workflows/{id}` | Delete workflow definition |
| GET | `/api/workflows/{id}/inputs` | Get input node configuration |
| POST | `/api/workflows/{id}/run` | Execute workflow (creates instance) |
| GET | `/api/workflows/instances` | List workflow instances |
| GET | `/api/workflows/instances/{id}` | Instance detail + node run records |
| GET | `/api/workflows/instances/{id}/stream` | SSE workflow progress |
| POST | `/api/workflows/instances/{id}/cancel` | Cancel running workflow |
| POST | `/api/workflows/instances/{id}/replay` | Replay completed/failed workflow |
| GET | `/api/workflows/instances/{id}/download` | Download workflow output as ZIP |

### Documentation
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/docs` | List documentation files |
| GET | `/api/docs/{doc_id}` | Render markdown doc as HTML |

## Key Design Decisions

1. **Zero script modifications** — Web server calls scripts via subprocess, identical to CLI usage
2. **File path passing** — Workflow nodes pass file paths between them, not binary data
3. **SQLite over file JSON** — Concurrent-safe, queryable, no custom serialization
4. **SSE over WebSocket** — Simpler protocol, unidirectional push is sufficient, browser auto-reconnect
5. **Provider abstraction** — Text-to-image providers are pluggable; adding new APIs needs no workflow logic changes
6. **Workflow layer above task layer** — Workflows orchestrate tasks; tasks still run through existing scheduler
7. **ES Module dynamic import** — Each page module loads on demand; initial load is just the router framework
8. **Window-level page cleanup** — `window._pageCleanup` ensures LiteGraph loops and SSE connections are released on page navigation
9. **Bilingual by design** — Every schema field, node parameter, and locale key carries both Chinese and English
10. **YAML + .env dual config** — Provider definitions in YAML, keys injected via .env file or environment variables
