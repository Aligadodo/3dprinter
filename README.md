# 3D Print Pipeline — AI 图片转 3D 打印流水线

从参考图片到 3D 打印机就绪 STL 文件的端到端管线。双 AI 引擎（TripoSR 快速 + Hunyuan3D-2.1 高质量），支持浮雕/夜灯生成、网格修复、六视图渲染，配套 Web 管理平台。

## 快速开始

### Web 管理平台（推荐）

**Windows** — 双击 `start-server.py` 或在终端运行：
```powershell
python start-server.py              # 默认 127.0.0.1:8080
python start-server.py --port 9090  # 指定端口
python start-server.py --lan        # LAN 访问
```

**Linux/macOS** —
```bash
python start-server.py              # 默认 127.0.0.1:8080
python start-server.py --port 9090
python start-server.py --lan
```

浏览器打开 [http://127.0.0.1:8080](http://127.0.0.1:8080)，通过 Web 界面提交任务、实时监控进度、管理输出文件、编辑工作流。

### CLI 命令

```bash
# 快速预览 (TripoSR, ~30s)
python scripts/pipeline.py photo.jpg

# 高质量 (Hunyuan3D-2.1)
python scripts/pipeline.py photo.jpg --engine hunyuan --steps 15

# 浮雕生成
python scripts/image-to-relief.py photo.jpg --width 160 --height 120 --colors 4

# 背光夜灯
python scripts/image-to-relief.py photo.jpg --lithophane

# 网格修复
python scripts/mesh-repair.py model.glb --output stl

# 六视图渲染
python scripts/mesh-to-views.py model.glb
```

## 功能矩阵

### 图片 → 3D（AI 生成）

| 引擎 | 速度 | 显存 | 纹理 | 许可 |
|------|------|------|------|------|
| **TripoSR** | ~2s | 3.5 GB | 顶点色 | MIT |
| **Hunyuan3D-2.1** | 10-60min | 6.9 GB | 几何（纹理 WIP） | 腾讯非商用 |

### 图片 → 浮雕 / 夜灯

| 模式 | 厚度 | 观察方式 | 用途 |
|------|------|----------|------|
| 浮雕 | 0.5mm 底 + 0-3mm 起伏 | 正面（反射光） | 墙面装饰 |
| 夜灯 | 0.6-2.6mm 渐变 | 背面（透射光） | 背光相框 |

- 支持 4 色量化（Bambu AMS 多色打印）
- 导出彩色 OBJ + STL
- 自动网格减面（30 万面以内）

### 后处理

| 工具 | 功能 |
|------|------|
| `mesh-repair.py` | Watertight 修复 + 去重 + 填洞 + 减面 |
| `mesh-to-views.py` | 6 正交视图（前/后/左/右/上/下）|
| `pipeline.py` | 全流程编排，`--engine` 切换引擎 |

## 目录结构

```
3dprint/
├── scripts/             # CLI 脚本
│   ├── image-to-3d.py       # TripoSR: 图片 → 3D 网格
│   ├── hunyuan-to-3d.py     # Hunyuan3D-2.1: 高质量生成
│   ├── image-to-relief.py   # 浮雕 / 夜灯 STL 生成
│   ├── mesh-repair.py       # Watertight 修复 → 打印 STL
│   ├── mesh-to-views.py     # 六视图正交渲染
│   └── pipeline.py          # 端到端编排器
├── web/                 # Web 管理平台
│   ├── server.py            # FastAPI 应用入口
│   ├── scheduler.py         # 异步任务调度 + GPU 锁
│   ├── models.py            # SQLite 数据层
│   ├── schemas.py           # 流水线参数定义
│   ├── workflow_engine.py   # 工作流执行引擎
│   ├── node_types.py        # 节点类型定义（25+ 节点）
│   ├── static/              # 模块化前端 SPA
│   │   ├── index.html       # 薄入口（~50行）
│   │   ├── css/             # 4 文件：main/components/workflow/pages
│   │   ├── js/              # ES modules：router/api/i18n/utils
│   │   │   ├── pages/       # 8 页面模块（懒加载）
│   │   │   └── components/  # 共享组件
│   │   └── locales/         # 中/英 JSON 翻译文件
│   ├── docs/                # 内置文档（中英双语）
│   └── DESIGN.md            # 架构设计文档
├── models/              # TripoSR 模型权重
├── output/              # 生成输出
│   ├── relief/          # 浮雕 STL + 彩色 OBJ
│   ├── lithophane/      # 夜灯 STL
│   └── views/           # 六视图 PNG
├── docs/
│   └── index.html       # 完整使用指南（暗色主题，侧栏导航）
├── start-server.py      # Web 平台启动器
├── start-server.bat
├── CLAUDE.md            # Claude Code 协作指南
└── README.md            # 本文件
```

## 环境要求

- **GPU**: NVIDIA RTX 3060+ (≥6GB VRAM)
- **RAM**: 32GB+（Hunyuan3D 需 32GB+）
- **OS**: Windows 11 / Linux / macOS
- **Python**: 3.12
- **CUDA**: 12.1+

## 依赖安装

```bash
# 核心
pip install numpy trimesh Pillow

# TripoSR
pip install torch torchvision "rembg[gpu]" huggingface_hub omegaconf

# 浮雕/夜灯
pip install scipy scikit-learn fast_simplification

# 修复 + 视图
pip install pymeshfix pyrender "pyglet<2"

# Web UI
pip install fastapi uvicorn python-multipart
```

## 文档

- [完整使用指南](docs/index.html) — 所有脚本的详细参数和示例
- [开发历程](docs/dev-journey.html) — 项目从 0 到 1 的完整开发故事
- [Web 平台设计文档](docs/web-design.md) — 架构、API、数据模型、设计决策
- [管线架构文档](docs/pipeline-architecture.md) — 4 阶段流水线详解
- [环境配置](docs/environment.md) — 硬件/软件/网络环境验证记录
- [安装指南](docs/setup-guide.md) — 从零开始配置管线
- [项目分析报告](docs/project-analysis-report.md) — Bug 分析 + 修复记录
- [项目标准清单](STANDARDS.md) — 业务目标、技术规范、质量 Checklist

## 目标打印机

Bambu Lab（4 色 AMS），0.4mm 喷嘴，PLA/PETG。
