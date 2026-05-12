# Web Task Management UI — Design Document

## Overview

A web-based task management interface for the 3D print pipeline. Users submit images/meshes, monitor task progress in real-time, manage tasks (cancel/retry/delete), compose workflow DAGs with a drag-and-drop editor, and browse output files — all from a browser.

## Architecture

```
Browser (SPA)  ←── SSE (progress) ──→  FastAPI Server  ←── subprocess ──→  CLI Scripts
               ─── REST (CRUD) ──→                      ─── files ───→  Output Dir
                                       ↕ SQLite (tasks.db, workflows.db)
        ↕ Text-to-Image APIs (Volcengine / Zhipu / OpenAI / Stability)
```

### Layer Map

| Layer | File | Role |
|-------|------|------|
| API Gateway | `web/server.py` | FastAPI app, REST + SSE endpoints, file serving, CORS, docs |
| Task Scheduler | `web/scheduler.py` | Async task queue, GPU lock (`asyncio.Lock`), subprocess lifecycle |
| Data Store | `web/models.py` | SQLite schema (tasks.db), CRUD operations, file linking |
| Pipeline Defs | `web/schemas.py` | 10 pipeline types with bilingual parameter schemas |
| Node Registry | `web/node_types.py` | 20 workflow node types, 4 categories, bilingual param metadata |
| Provider Layer | `web/providers.py` | Text-to-image provider abstraction (4 providers, YAML + .env config) |
| Workflow Data | `web/workflow_models.py` | Workflow definitions, instances, node run records (workflows.db) |
| Workflow Engine | `web/workflow_engine.py` | DAG execution via Kahn's algorithm, node orchestration |
| Frontend (Static) | `web/static/` | Modular ES module SPA, 4 CSS files, 11 JS modules, 2 locale JSONs |
| Templates | `web/templates/index.html` | Legacy redirect — points to `/static/index.html` |

## Frontend Architecture

### Modular Structure

```
web/static/
├── index.html                 # Thin entry (~50 lines), <script type="module" src="js/app.js">
├── css/
│   ├── main.css               # Design tokens (:root), reset, layout, sidebar, responsive
│   ├── components.css         # Buttons, cards, forms, badges, toasts, modals, progress
│   ├── workflow.css           # DAG editor, runner layout, node detail panel, image grid
│   └── pages.css              # Page-level layouts (stats, type-grid, preview-grid)
├── js/
│   ├── app.js                 # Entry: init i18n → register routes → boot
│   ├── i18n.js                # Locale loader, t() dot-path lookup, setLang()
│   ├── api.js                 # Fetch wrapper, SSE helper, file cache
│   ├── utils.js               # escHtml, formatTime, formatBytes, toast, context menu
│   ├── router.js              # Hash router + navigation guard + page cleanup
│   ├── pages/
│   │   ├── dashboard.js       # renderDashboard() — stats cards, task list, 5s polling
│   │   ├── new-task.js        # renderNewTask() — type selector, upload, text-to-image panel
│   │   ├── task-detail.js     # renderTaskDetail() — SSE log, output gallery, actions
│   │   ├── file-browse.js     # renderBrowse() — grid gallery, right-click menu
│   │   ├── docs.js            # renderDocList() + renderDocViewer() — markdown docs browser
│   │   ├── workflows.js       # renderWorkflowList() — workflow CRUD, template gallery
│   │   ├── wf-editor.js       # renderWorkflowEditor() — LiteGraph DAG editor, save, run
│   │   └── wf-runner.js       # renderWorkflowRunner() — SSE DAG, node tabs, output viewer
│   └── components/
│       ├── node-detail.js     # renderNodeDetailPanel() — shared between editor & runner
│       └── file-modal.js      # showFileModal() — image/STL/3D preview overlay
└── locales/
    ├── zh.json                # ~130 Chinese keys
    └── en.json                # ~130 English keys
```

### i18n System

- Locale JSON files loaded on demand via `fetch()`
- `t(key, fallback?)` — dot-path lookup (e.g., `t('dash.recent')` → "最近任务")
- Fallback chain: current language → English (en.json) → key itself
- `setLang(l)` — reloads locale, re-renders current page without full SPA reboot
- Language preference persisted in `localStorage`

### Page Cleanup

Pages using long-lived resources (LiteGraph animation loops, SSE connections) register `window._pageCleanup`. The router calls it before loading a new page to prevent stale timers and connections.

## Design Decisions

### 1. Vanilla JS ES Modules over Bundlers

Zero build step, no npm dependency, native browser `import`/`export`. Each page module lazy-loaded via dynamic `import()` — the user only downloads JS for pages they visit. The SPA uses hash-based routing (`#/dashboard`, `#/new`, etc.).

### 2. SSE over WebSocket

Progress updates are unidirectional (server → client). SSE is simpler: native browser `EventSource` with auto-reconnect, no extra Python dependency. The server sends named events (`status`, `log`, `progress`, `complete`, `error`) and a keepalive ping every 30s.

### 3. SQLite over JSON Files

Concurrent access safety (WAL mode), queryable by status/date, no custom serialization. Two databases: `tasks.db` for task records and output files, `workflows.db` for workflow definitions, instances, and node run records.

### 4. asyncio.Lock for GPU Scheduling

Only one GPU task runs at a time (TripoSR, Hunyuan3D). CPU tasks (relief, lithophane, views, repair, simplify, smooth, scale) bypass the lock and run concurrently.

### 5. Subprocess Integration (Zero Script Changes)

Existing scripts are called via `asyncio.create_subprocess_exec()` with the same arguments as CLI usage. Stdout is streamed line-by-line for real-time log display. The final JSON result is extracted from stdout using `json.JSONDecoder.raw_decode()` from the last `{` position.

### 6. File Path Strategy

Uploaded files go to `output/` (project root), so the scripts' built-in path logic places outputs in `output/relief/`, `output/text2img/`, etc. The database stores absolute paths; the API returns relative URLs (`/api/files/output/relief/xxx.png`). File serving resolves relative paths against `PROJECT_ROOT`.

### 7. Workflow Layer on Top of Task Layer

Workflows orchestrate pipeline stages — each node execution submits a sub-task to the existing scheduler. Nodes pass file paths between each other (not binary data). The workflow engine uses Kahn's algorithm for topological DAG sorting.

## Data Model

### tasks table

| Column | Type | Purpose |
|--------|------|---------|
| id | TEXT PK | 12-char hex UUID |
| pipeline_type | TEXT | One of 10 pipeline types |
| status | TEXT | queued → running → completed/failed/cancelled |
| params_json | TEXT | JSON dict of pipeline parameters |
| input_file | TEXT | Absolute path to uploaded input file |
| result_json | TEXT | Full JSON result from the script (nullable) |
| created_at | REAL | Unix timestamp |
| updated_at | REAL | Unix timestamp |

### output_files table

| Column | Type | Purpose |
|--------|------|---------|
| id | INTEGER PK | Auto-increment |
| task_id | TEXT FK | References tasks(id) ON DELETE CASCADE |
| file_type | TEXT | File extension (`.stl`, `.png`, `.obj`) |
| path | TEXT | Absolute path on disk |
| created_at | REAL | Unix timestamp |

## API Design

### Task Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/tasks` | List tasks (`?status=`, `?limit=`, `?offset=`) |
| POST | `/api/tasks` | Create task (multipart: pipeline_type, params, file) |
| GET | `/api/tasks/{id}` | Task detail with output files |
| GET | `/api/tasks/{id}/workflow` | Get parent workflow context for a task |
| DELETE | `/api/tasks/{id}` | Delete task + cleanup files |
| POST | `/api/tasks/{id}/cancel` | Cancel running task |
| POST | `/api/tasks/{id}/retry` | Retry failed/cancelled task |
| GET | `/api/tasks/{id}/stream` | SSE progress stream |

### File Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/files/{path}` | Serve output files (images, STL, etc.) |
| POST | `/api/open-path` | Open a file path in the OS file manager |

### Pipeline & Providers

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/pipeline-types` | All 10 pipeline types with parameter schemas |
| GET | `/api/text2img/providers` | Available text-to-image providers (no keys exposed) |
| POST | `/api/text2img` | Generate image from text prompt |
| GET | `/api/node-types` | All 20 workflow node types with port/param specs |

### Workflow Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/workflows` | List workflow definitions |
| POST | `/api/workflows` | Create workflow definition |
| GET | `/api/workflows/{id}` | Get workflow definition detail |
| PUT | `/api/workflows/{id}` | Update workflow definition |
| DELETE | `/api/workflows/{id}` | Delete workflow definition |
| GET | `/api/workflows/{id}/inputs` | Get workflow input node config |
| POST | `/api/workflows/{id}/run` | Execute workflow (creates instance) |
| GET | `/api/workflows/instances` | List workflow instances |
| GET | `/api/workflows/instances/{id}` | Instance detail + node runs |
| GET | `/api/workflows/instances/{id}/stream` | SSE workflow progress |
| POST | `/api/workflows/instances/{id}/cancel` | Cancel running workflow |
| POST | `/api/workflows/instances/{id}/replay` | Re-run a completed/failed workflow |
| GET | `/api/workflows/instances/{id}/download` | Download workflow output as ZIP |

### Documentation

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/docs` | List available documentation files |
| GET | `/api/docs/{doc_id}` | Render markdown doc as HTML |

### SSE Events

```
event: status     data: {"status": "running", "message": "Starting..."}
event: log        data: {"line": "Height map computed in 0.3s"}
event: progress   data: {"stage": "generating", "percent": 45}
event: preview    data: {"path": "...", "filename": "preview.png"}
event: complete   data: {"stl": "...", "vertices": 150000, ...}
event: error      data: {"error": "...", "stage": "repair"}
event: cancelled  data: {"message": "Task cancelled by user"}
```

## Frontend Pages

| Hash Route | Page | Description |
|------------|------|-------------|
| `#/dashboard` | Dashboard | Queue stats, recent tasks, workflow badges, 5s polling |
| `#/new` | New Task | Pipeline type grid, file upload, text-to-image panel, param form |
| `#/task/<id>` | Task Detail | SSE live log, output gallery, action buttons, sub-task breadcrumb |
| `#/browse` | Browse | File gallery grid, right-click menu, pipeline type filter |
| `#/docs` | Docs List | Markdown documentation browser |
| `#/docs/<id>` | Doc Viewer | Rendered markdown with table of contents |
| `#/workflows` | Workflow List | CRUD list, template gallery, instance history |
| `#/workflows/editor[/<id>]` | Editor | LiteGraph DAG canvas, node palette, save/run |
| `#/workflows/runner/<inst_id>` | Runner | Split layout: tabs + node detail + SSE DAG + output preview |

## Pipeline Types (10 total)

| # | Type | Input | GPU | Script |
|---|------|-------|-----|--------|
| 1 | relief | Image | No | image-to-relief.py |
| 2 | lithophane | Image | No | image-to-relief.py |
| 3 | layered_relief | Image | No | image-to-layered-relief.py |
| 4 | triposr | Image | Yes | image-to-3d.py |
| 5 | hunyuan | Image | Yes | hunyuan-to-3d.py |
| 6 | mesh_simplify | Mesh | No | mesh-simplify.py |
| 7 | mesh_smooth | Mesh | No | mesh-smooth.py |
| 8 | mesh_scale | Mesh | No | mesh-scale.py |
| 9 | views | Mesh | No | mesh-to-views.py |
| 10 | repair | Mesh | No | mesh-repair.py |

## Text-to-Image Providers (4 total)

| Provider | Model | Status | Sizes |
|----------|-------|--------|-------|
| Volcengine Seedream | doubao-seedream-5-0-260128 | Default | 2048×2048, 4096×4096 |
| Zhipu CogView | cogview-3-flash | Enabled (free) | 1024×1024, 768×1344, 1152×864 |
| OpenAI DALL-E 3 | dall-e-3 | Disabled | 1024×1024, 1792×1024, 1024×1792 |
| Stability AI | stable-image-generate | Disabled | 1024×1024 |

API keys configured via `config/.env` (auto-loaded) or environment variables. Priority: env var > .env file.

## Security Notes

- File serving restricted to `PROJECT_ROOT` subtree (path traversal blocked)
- No authentication (single-user LAN tool)
- CORS allows all origins for LAN access
- Database uses WAL mode for concurrent read safety
