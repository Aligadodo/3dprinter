# 系统架构设计

## 概述

3D Print Pipeline 是一个基于 Web 的 3D 打印流水线系统，将图片/文字/网格转换为可打印的 3D 模型。系统采用 **FastAPI 后端 + 原生 JavaScript ES Module SPA 前端** 架构，支持 GPU 任务调度、实时进度推送、工作流 DAG 编排、AI 文生图和内联图像处理。

## 技术栈

| 层次 | 技术选型 | 说明 |
|------|----------|------|
| 后端框架 | **FastAPI + uvicorn** | 异步原生支持、SSE 流式传输、自动 API 文档 |
| 前端 | **原生 ES Module SPA** | 零构建步骤、hash 路由、动态 import() 按需加载 |
| 实时通信 | **SSE (Server-Sent Events)** | 单向服务器推送、浏览器自动重连、无需额外依赖 |
| 数据存储 | **SQLite + WAL 模式** | 零配置、文件级存储、支持并发读取（tasks.db + workflows.db） |
| GPU 调度 | **asyncio.Lock** | 单 GPU 序列化、CPU 任务并行执行 |
| 工作流画布 | **Litegraph.js 0.7.14** | 与 ComfyUI 同款库、拖拽式 DAG 编辑 |
| 文生图 | **火山引擎 / 智谱 / OpenAI / Stability** | 云端 API、Provider 抽象层、YAML + .env 配置 |
| 文档渲染 | **Python Markdown** | 服务端渲染 markdown 为 HTML |

## 目录结构

```
3dprint/
├── web/                            # Web 应用
│   ├── server.py                   # FastAPI 应用入口、32+ REST/SSE 端点、StaticFiles 挂载
│   ├── scheduler.py                # 异步任务调度器、GPU 锁、子进程管理
│   ├── models.py                   # SQLite 数据库层、任务 CRUD
│   ├── schemas.py                  # 10 种流水线类型定义和参数 schema（中英双语）
│   ├── node_types.py               # 20 种工作流节点类型（4 类别）、参数元数据（中英双语）
│   ├── providers.py                # 文生图 Provider 抽象层（4 供应商）、.env 自动加载
│   ├── workflow_models.py          # 工作流数据库层（定义/实例/节点运行记录）
│   ├── workflow_engine.py          # DAG 执行引擎（Kahn 拓扑排序、Node-to-Task 映射）
│   ├── templates/
│   │   └── index.html              # 旧入口重定向页（向后兼容）
│   ├── static/                     # 模块化前端 SPA
│   │   ├── index.html              # 薄入口（~50 行）
│   │   ├── css/
│   │   │   ├── main.css            # 设计令牌 :root、reset、布局框架、响应式
│   │   │   ├── components.css      # 按钮/卡片/表单/badge/toast/modal/进度条
│   │   │   ├── workflow.css        # 工作流编辑器/运行器/节点面板/图片网格
│   │   │   └── pages.css           # 页面级布局（stats、type-grid、preview-grid）
│   │   ├── js/
│   │   │   ├── app.js              # 入口：i18n 初始化 → 路由注册 → 启动
│   │   │   ├── i18n.js             # locale JSON 加载器、t() 点号路径查找、setLang()
│   │   │   ├── api.js              # fetch 封装、SSE EventSource、文件缓存
│   │   │   ├── utils.js            # escHtml / formatTime / formatBytes / toast / 右键菜单
│   │   │   ├── router.js           # hash 路由 + 导航守卫 + 页面清理（_pageCleanup）
│   │   │   ├── pages/
│   │   │   │   ├── dashboard.js    # renderDashboard() — 统计卡、任务列表、5s 轮询
│   │   │   │   ├── new-task.js     # renderNewTask() — 类型选择、上传、文生图面板
│   │   │   │   ├── task-detail.js  # renderTaskDetail() — SSE 日志、输出画廊、操作按钮
│   │   │   │   ├── file-browse.js  # renderBrowse() — 文件网格画廊、右键菜单、文件过滤
│   │   │   │   ├── docs.js         # renderDocList() + renderDocViewer() — 文档浏览器
│   │   │   │   ├── workflows.js    # renderWorkflowList() — 工作流 CRUD、模板库
│   │   │   │   ├── wf-editor.js    # renderWorkflowEditor() — LiteGraph DAG 编辑器
│   │   │   │   └── wf-runner.js    # renderWorkflowRunner() — SSE DAG、节点 Tab、输出预览
│   │   │   └── components/
│   │   │       ├── node-detail.js  # renderNodeDetailPanel() — 编辑器/运行器共享
│   │   │       └── file-modal.js   # showFileModal() — 图片/STL/3D 预览覆盖层
│   │   └── locales/
│   │       ├── zh.json             # ~130 条中文翻译
│   │       └── en.json             # ~130 条英文翻译
│   └── docs/                       # 设计文档（本目录）
│       ├── DESIGN.md               # 设计文档（主文档）
│       ├── architecture.zh.md      # 架构设计（中文）
│       ├── architecture.en.md      # 架构设计（英文）
│       ├── pipelines.zh.md         # 流水线参考（中文）
│       ├── pipelines.en.md         # 流水线参考（英文）
│       ├── workflow.zh.md          # 工作流系统（中文）
│       ├── workflow.en.md          # 工作流系统（英文）
│       ├── text2img.zh.md          # 文生图集成（中文）
│       └── text2img.en.md          # 文生图集成（英文）
├── scripts/                        # Python 流水线脚本
│   ├── image-to-relief.py          # 图片 → 浮雕 / 夜灯
│   ├── image-to-layered-relief.py  # 图片 → 多层套色浮雕
│   ├── image-to-3d.py              # 图片 → TripoSR 快速 3D 模型
│   ├── hunyuan-to-3d.py            # 图片 → Hunyuan3D 高质量模型
│   ├── mesh-repair.py              # 网格修复 → 水密 STL
│   ├── mesh-to-views.py            # 3D 网格 → 六面正交视图
│   ├── mesh-simplify.py            # 网格减面（二次误差/聚类）
│   ├── mesh-smooth.py              # 网格平滑（Taubin）
│   ├── mesh-scale.py               # 网格缩放（比例/目标尺寸）
│   ├── text-to-image.py            # 文字 → AI 图片（4 供应商）
│   └── pipeline.py                 # 流水线基类
├── config/
│   ├── providers.yaml              # 文生图供应商配置（4 供应商、优先级）
│   └── .env.example                # API 密钥配置模板
└── output/                         # 输出文件目录
    ├── tasks/                      # 任务工作目录
    ├── relief/                     # 浮雕输出
    ├── text2img/                   # 文生图输出
    └── ...
```

## 数据流

### 单任务流程

```
用户上传文件 → POST /api/tasks → models.create_task()
    → scheduler.submit() → asyncio 子进程执行脚本
    → stdout 逐行解析进度事件 → SSE 推送到前端
    → 脚本输出 JSON 结果 → models.update_task_status()
    → 前端收到 complete 事件 → 渲染输出文件
```

### 工作流流程

```
用户编辑 DAG → 保存工作流定义 → POST /api/workflows/{id}/run
    → workflow_engine 拓扑排序（Kahn 算法）→ 按序执行每个节点
    → 每个节点提交一个子任务到 scheduler
    → 等待子任务完成 → 收集输出文件路径 → 传递给下游节点
    → 所有节点完成 → workflow_complete 事件
    → 前端 Runner 页面实时显示 DAG 状态色和节点进度
```

### 输入节点流程

```
用户配置 Text Input 或 File Input 节点
    → POST /api/workflows/{id}/inputs 设置输入值
    → POST /api/workflows/{id}/run 携带 inputs JSON
    → 引擎用输入值替换对应节点的默认值
```

## 任务生命周期

```
queued → running → completed
                 → failed（可重试）
                 → cancelled
```

## SSE 事件类型

| 事件 | 数据 | 触发时机 |
|------|------|----------|
| `status` | `{status, message}` | 任务状态变更（排队/开始运行） |
| `progress` | `{percent, message}` | 进度百分比更新 |
| `log` | `{line}` | 脚本 stdout 日志行 |
| `preview` | `{path, filename}` | 中间预览图生成 |
| `complete` | `{output, ...}` | 任务成功完成 |
| `error` | `{error, stage}` | 任务失败 |
| `cancelled` | `{message}` | 任务被取消 |
| `done` | `{}` | SSE 流结束标记 |

## GPU 调度

- GPU 任务（TripoSR、Hunyuan3D）共享一个 `asyncio.Lock`
- 同一时间只有一个 GPU 任务运行，防止显存溢出
- CPU 任务（浮雕、夜灯、修复、简化、平滑、缩放等）不经过 GPU 锁，可并行执行
- 队列中的 GPU 任务会显示等待状态

## API 端点总览

### 任务相关
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/tasks` | 任务列表（支持 status/limit/offset 参数） |
| POST | `/api/tasks` | 创建任务（multipart: pipeline_type + params + file） |
| GET | `/api/tasks/{id}` | 任务详情 + 输出文件列表 |
| GET | `/api/tasks/{id}/workflow` | 获取任务所属工作流上下文 |
| DELETE | `/api/tasks/{id}` | 删除任务 + 级联清理输出文件 |
| POST | `/api/tasks/{id}/cancel` | 取消运行中的任务 |
| POST | `/api/tasks/{id}/retry` | 重试失败/已取消任务 |
| GET | `/api/tasks/{id}/stream` | SSE 进度推送流 |

### 文件相关
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/files/{path}` | 提供输出文件（路径遍历保护） |
| POST | `/api/open-path` | 在系统文件管理器中打开路径 |

### 流水线与文生图
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/pipeline-types` | 10 种流水线类型及参数 schema |
| GET | `/api/text2img/providers` | 文生图供应商列表（不含密钥） |
| POST | `/api/text2img` | 文字 → 图片生成 |
| GET | `/api/node-types` | 20 种工作流节点类型及端口/参数定义 |

### 工作流
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/workflows` | 工作流定义列表 |
| POST | `/api/workflows` | 创建/克隆工作流定义 |
| GET | `/api/workflows/{id}` | 工作流定义详情 |
| PUT | `/api/workflows/{id}` | 更新工作流定义 |
| DELETE | `/api/workflows/{id}` | 删除工作流定义 |
| GET | `/api/workflows/{id}/inputs` | 获取工作流输入节点配置 |
| POST | `/api/workflows/{id}/run` | 执行工作流（创建实例） |
| GET | `/api/workflows/instances` | 工作流实例列表 |
| GET | `/api/workflows/instances/{id}` | 实例详情 + 节点运行记录 |
| GET | `/api/workflows/instances/{id}/stream` | SSE 工作流进度推送 |
| POST | `/api/workflows/instances/{id}/cancel` | 取消运行中的工作流 |
| POST | `/api/workflows/instances/{id}/replay` | 重放已完成/失败的工作流 |
| GET | `/api/workflows/instances/{id}/download` | 下载工作流输出为 ZIP |

### 文档
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/docs` | 文档列表 |
| GET | `/api/docs/{doc_id}` | 渲染 markdown 文档为 HTML |

## 关键设计决策

1. **零脚本修改** — Web 服务器通过子进程调用脚本，与 CLI 方式完全一致
2. **文件路径传递** — 工作流节点之间传递文件路径而非二进制数据
3. **SQLite 而非文件 JSON** — 支持并发安全访问、可查询、无需自定义序列化
4. **SSE 而非 WebSocket** — 协议更简单、单向推送足够、浏览器原生支持自动重连
5. **Provider 抽象** — 文生图供应商可插拔，添加新 API 无需改动工作流逻辑
6. **工作流层在任务层之上** — 工作流编排任务，任务仍通过现有调度器执行
7. **ES Module 动态导入** — 每个页面模块按需加载，首页仅加载路由框架
8. **窗口级页面清理** — `window._pageCleanup` 机制确保页面切换时释放 LiteGraph 循环和 SSE 连接
9. **中英双语内置** — 每个 schema 字段、节点参数、locale key 均包含中英双语
10. **YAML + .env 双配置** — 供应商定义在 YAML，密钥通过 .env 文件或环境变量注入
