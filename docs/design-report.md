# 3D Print Pipeline 设计报告

## 一、项目概述

**3D Print Pipeline** 是一个端到端 AI 驱动的 3D 打印流水线系统：将参考图片转换为 Bambu Lab 打印机可用的 STL 文件。项目支持两种 AI 生成引擎（TripoSR 快速、Hunyuan3D-2.1 高质量），以及浮雕/夜灯生成、网格修复和正交视图渲染。

**目标硬件：** RTX 3060 Laptop 6GB VRAM / 64GB RAM / Windows 11  
**目标打印机：** Bambu Lab（4色 AMS），0.4mm 喷嘴，PLA/PETG

---

## 二、整体架构

```
输入图片
    │
    ├── TripoSR ──────────────► 网格(GLB)
    ├── Hunyuan3D-2.1 ────────► 网格(GLB)
    └── Relief/Lithophane ────► STL
              │
              ▼
         网格修复 (mesh-repair.py)
              │
    ┌─────────┼──────────┐
    ▼         ▼          ▼
   STL     视图 PNG    打印文件
```

---

## 三、目录结构

```
3dprint/
├── scripts/                  # CLI 脚本（核心执行单元）
│   ├── pipeline.py           # 端到端编排器
│   ├── image-to-3d.py        # TripoSR 生成
│   ├── hunyuan-to-3d.py     # Hunyuan3D-2.1 生成
│   ├── image-to-relief.py    # 浮雕/夜灯生成
│   ├── image-to-layered-relief.py  # 多层套色浮雕
│   ├── mesh-repair.py       # 防水修复
│   ├── mesh-to-views.py     # 六视图正交渲染
│   ├── mesh-simplify.py     # 网格减面
│   ├── mesh-smooth.py       # 网格平滑
│   ├── mesh-scale.py        # 网格缩放
│   └── text-to-image.py     # 文本→图片
│
├── config/                   # 配置文件
│   ├── config.yaml           # TripoSR 模型配置
│   ├── providers.yaml        # Text-to-Image 提供商配置
│   └── .env.example          # API 密钥模板
│
├── triposr/src/              # TripoSR 推理源码
│   └── tsr/                  # 核心包
│       ├── system.py         # 系统级接口
│       ├── models/
│       │   ├── isosurface.py # Marching Cubes 等值面
│       │   ├── nerf_renderer.py # NeRF 渲染器
│       │   └── tokenizers/   # DINO / Triplane tokenizer
│       └── models/transformer/ # Transformer 实现
│
├── models/                   # TripoSR 模型权重
│   └── model.ckpt            # ~1.6GB 权重文件
│
├── web/                      # Web 管理平台
│   ├── server.py             # FastAPI 应用入口
│   ├── scheduler.py          # 异步任务调度器 + GPU 锁
│   ├── models.py             # SQLite 数据层（tasks 表）
│   ├── workflow_models.py    # 工作流数据库模型
│   ├── workflow_engine.py    # DAG 工作流执行引擎
│   ├── node_types.py         # 25+ 节点类型注册表
│   ├── schemas.py            # 流水线类型定义
│   ├── providers.py          # Text-to-Image 提供商抽象层
│   ├── inline_nodes.py       # PIL 图像处理节点（引擎内联执行）
│   └── static/               # 前端 SPA
│       ├── css/              # 4 个 CSS 文件
│       ├── js/               # 模块化 JS（ES modules）
│       │   ├── api.js        # REST API 客户端
│       │   ├── router.js     # Hash 路由
│       │   ├── i18n.js       # 国际化
│       │   └── pages/        # 8 个页面模块
│       └── locales/          # zh.json / en.json
│
├── docs/                     # 文档
│   ├── index.html            # 完整使用指南
│   ├── dev-journey.html      # 开发历程
│   ├── iterations/           # 设计迭代快照（自动保存）
│   └── iterations/INDEX.md   # 迭代记录索引
│
├── output/                   # 生成文件
│   ├── tasks/                # 任务工作目录
│   ├── relief/                # 浮雕输出
│   ├── lithophane/           # 夜灯输出
│   ├── views/                # 六视图渲染结果
│   └── output/               # 直接输出
│
├── 混元3D2.1+.../             # Hunyuan3D ComfyUI 便携包
│   └── extracted/ComfyUI_windows_portable/
│       ├── python_embeded/   # 嵌入式 Python 3.12
│       └── ComfyUI/          # 模型 + custom_nodes
│
├── skills/                    # Claude Code Skills
├── tests/                     # 测试套件
│   ├── test_api.py           # API 集成测试
│   ├── test_scripts.py       # 脚本单元测试
│   └── test_workflow_engine.py # 工作流引擎测试
│
├── CLAUDE.md                 # Claude Code 协作指南
├── STANDARDS.md              # 项目规范清单
└── start-server.py           # Web 服务器启动器
```

---

## 四、脚本模块详解

### 4.1 `pipeline.py` — 端到端编排器

**职责：** 按顺序调用各阶段脚本，构成完整流水线。

**数据流：**
1. **生成阶段** → 调用 `image-to-3d.py`（TripoSR）或 `hunyuan-to-3d.py`（Hunyuan3D）
2. **修复阶段** → 调用 `mesh-repair.py` 输出防水 STL
3. **视图阶段（可选）** → 调用 `mesh-to-views.py` 生成六视图

**输出格式：** JSON，含各阶段结果和最终输出路径

---

### 4.2 `image-to-3d.py` — TripoSR 生成

**职责：** 单张图片 → 3D 网格（~2秒）。

**关键流程：**
- 背景去除（rembg）→ 前背景合成到灰底 → 推理 → Marching Cubes 提取网格 → 导出 GLB/OBJ

**输出 JSON keys：** `output`, `vertices`, `faces`, `watertight`, `dimensions_mm`, `engine: "triposr"`

---

### 4.3 `hunyuan-to-3d.py` — Hunyuan3D-2.1 生成

**职责：** 高质量图片 → 3D 网格（~67-287秒/step）。

**关键流程：**
- 配置 ComfyUI 便携环境路径 → monkey-patch 处理中文路径 → 加载 DiT + VAE → Flow Matching 生成 latents → ShapeVAE 解码为网格 → 后处理（FloaterRemover + DegenerateFaceRemover）

**输出 JSON keys：** `output`, `vertices`, `faces`, `watertight`, `dimensions_mm`, `engine: "hunyuan3d-2.1"`

**注意：** VRAM 需求 6.86GB，6GB 显卡会溢出到共享内存导致热节流。

---

### 4.4 `image-to-relief.py` — 浮雕/夜灯生成

**职责：** 2D 图片 → 3D 可打印浮雕或夜灯 STL。

**两种模式：**

| 模式 | 厚度 | 受光方式 | 用途 |
|------|------|----------|------|
| Relief | 0.5mm 底 + 0-3mm 起伏 | 正面反射 | 墙面装饰 |
| Lithophane | 0.6-2.6mm | 背面透光 | 背光相框 |

**关键处理：**
- 高斯滤波分离基础形状和细节 → 合并后归一化高度
- 支持 4 色 K-means 量化（AMS 多色打印）
- 网格结构：顶面（高度位移面）+ 背面（平板）+ 四侧壁 → 天然防水

---

### 4.5 `mesh-repair.py` — 网格修复

**职责：** 将 AI 生成网格修复为防水、3D 打印可用的 STL/3MF。

**修复步骤：**
1. 加载网格（处理 Scene 格式取最大体）
2. `unique_faces()` + `nondegenerate_faces()` 清洗
3. `pymeshfix.MeshFix().repair()` 深度修复
4. 回退：trimesh `fill_holes()` + `fix_normals()` + `merge_vertices()`
5. 居中、落地（z-min=0）、缩放

---

### 4.6 `mesh-to-views.py` — 正交视图渲染

**职责：** 渲染 6 个正交视图（前/后/左/右/上/下）供视觉检查。

**实现：** pyrender OffscreenRenderer + 正交相机 + 两个方向光

---

## 五、Web 平台架构

### 5.1 核心模块关系

```
server.py (FastAPI)
    │
    ├── scheduler.py ──────► asyncio subprocess ──► scripts/*.py
    │       └── gpu_lock（确保同时只有一个 GPU 任务运行）
    │
    ├── models.py ◄───────────────────────────────► tasks.db (SQLite)
    │       └── tasks 表 + output_files 表
    │
    ├── workflow_models.py ◄────────────────────► tasks.db
    │       └── workflow_definitions / instances / node_runs 表
    │
    ├── workflow_engine.py ◄──► scheduler.py
    │       ├── node_types.py（节点类型注册表）
    │       ├── providers.py（Text-to-Image）
    │       └── inline_nodes.py（PIL 内联节点）
    │
    └── providers.py ────────────────────────────► 外部 AI API
```

### 5.2 各模块职责

| 模块 | 职责 |
|------|------|
| `server.py` | HTTP 入口、Task CRUD、工作流 CRUD、SSE 流、文件服务 |
| `scheduler.py` | 异步任务提交/subprocess 执行、GPU 锁管理、进度 SSE 推送 |
| `models.py` | SQLite tasks/output_files 表的 CRUD |
| `workflow_models.py` | SQLite workflow 定义/实例/节点运行 表的 CRUD |
| `workflow_engine.py` | DAG 拓扑排序、节点执行（inline/pipeline/file/text2img）、replay |
| `node_types.py` | 25+ 节点类型定义（PortSpec 输入输出 + 参数 + 颜色分类） |
| `schemas.py` | 10 种流水线类型定义（relief/lithophane/triposr/hunyuan 等） |
| `providers.py` | 4 种 AI 图片生成提供商的抽象接口 |
| `inline_nodes.py` | PIL 图像处理节点（6 种，引擎内联执行不启动子进程） |

### 5.3 前端 SPA 结构

**路由：** Hash-based SPA（`#/dashboard`, `#/workflow/new`, `#/workflow/instance/{id}` 等）

**主要页面：**
- **Dashboard** — 统计徽章 + 任务列表（5秒自动刷新 + SSE 连接）
- **New Task** — 流水线选择 + 文件上传 + 参数表单 + Text-to-Image 面板
- **Workflow Editor** — LiteGraph DAG 编辑器（调色板拖拽、节点 Tooltip、保存/执行）
- **Workflow Runner** — 实时 DAG 视图 + 进度条 + 节点详情 Tab + Replay 按钮
- **Task Detail** — 任务详情 + 输出文件下载

**CSS 架构：** 4 个模块化文件（main.css 全局基础 / components.css 组件库 / pages.css 页面 / workflow.css 工作流编辑器）

---

## 六、流水线类型

| 类型 | 引擎 | GPU | 输入 | 说明 |
|------|------|-----|------|------|
| `relief` | CPU | ✗ | 图片 | 正面反射浮雕 |
| `lithophane` | CPU | ✗ | 图片 | 背面透光夜灯 |
| `layered_relief` | CPU | ✗ | 图片 | 多层套色浮雕 |
| `triposr` | GPU (~3.5GB) | ✓ | 图片 | 快速 AI 生成 |
| `hunyuan` | GPU (~6.9GB) | ✓ | 图片 | 高质量 AI 生成 |
| `mesh_simplify` | CPU | ✗ | 网格 | 减面 |
| `mesh_smooth` | CPU | ✗ | 网格 | Taubin 平滑 |
| `mesh_scale` | CPU | ✗ | 网格 | 缩放 |
| `views` | CPU | ✗ | 网格 | 六视图渲染 |
| `repair` | CPU | ✗ | 网格 | 防水修复 |

---

## 七、关键设计点

1. **GPU 锁机制**（`scheduler.py`）：`asyncio.Lock` 确保同时只有一个 GPU 任务执行，防止 6GB 显存超载。

2. **输出路径嵌套避免**（`image-to-3d.py`/`hunyuan-to-3d.py`）：输入在 `output/` 目录时不重复嵌套 `output/output/`。

3. **Hunyuan3D 中文路径 monkey-patch**（`hunyuan-to-3d.py`）：补丁 `get_obj_from_str` 解决中文目录名导致 Python import 失败的问题。

4. **FlowMatchingPipeline 返回 latents**（`hunyuan-to-3d.py`）：需要手动调用 VAE 的 `latents2mesh`，非直接返回网格。

5. **工作流引擎的 replay 机制**（`workflow_engine.py`）：从指定节点重放，保留上游 context，支持增量调试。

6. **迭代快照自动保存**：`.claude/hooks/save-iteration.ps1` 通过 hook 比较 plan 文件 hash，仅在内容变化时保存快照到 `docs/iterations/`。