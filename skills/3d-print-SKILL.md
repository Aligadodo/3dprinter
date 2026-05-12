---
name: 3d-print
description: 3D打印工作流 — 从参考图片生成3D模型，修复网格，准备Bambu打印机文件。用户输入 /3d-print 查看管线状态。
user-invocable: true
argument-hint: "[action] [args]"
allowed-tools:
  - Read
  - Write
  - Bash
  - Glob
---

# 3D 打印工作流

你是 3D 打印管线管理模块，负责从参考图片到 Bambu 打印机文件的全流程。

## 管线架构

```
📸 参考图片
         │
    ┌────▼────────────────────────────┐
    │  STAGE 1: Image → 3D            │
    │  TripoSR (stabilityai/TripoSR)  │
    │  脚本: scripts/3d-print/        │
    │        image-to-3d.py           │
    │  输出: .glb (带顶点色3D模型)     │
    └────┬────────────────────────────┘
         │
    ┌────▼────────────────────────────┐
    │  STAGE 2: Mesh Repair           │
    │  Trimesh + PyMeshFix            │
    │  脚本: scripts/3d-print/        │
    │        mesh-repair.py           │
    │  输出: watertight .stl          │
    └────┬────────────────────────────┘
         │
    ┌────▼────────────────────────────┐
    │  STAGE 3: Slice (手动)          │
    │  OrcaSlicer CLI                 │
    │  → .gcode.3mf                   │
    └────┬────────────────────────────┘
         │
    ┌────▼────────────────────────────┐
    │  STAGE 4: Print (手动)          │
    │  Bambu Studio / MCP Server      │
    │  → 发送到打印机                  │
    └─────────────────────────────────┘
```

## 引擎

**TripoSR** (stabilityai/TripoSR) — Stability AI 和 Tripo AI 合作开发的开源 3D 重建模型。

- 输入：单张 RGB 图片（任意分辨率）
- 输出：带顶点色的三角网格 (.glb/.obj)
- 模型大小：~1.6GB（首次运行自动下载到 HF 缓存）
- VRAM 需求：~2.5GB（推理时）
- 生成速度：~2-3 秒/张图（RTX 3060）

预处理步骤（默认启用）：
1. rembg 背景去除
2. 前景居中 + 缩放
3. 灰色背景填充

## 系统依赖

必装：
- **PyTorch** with CUDA (`pip install torch --index-url https://download.pytorch.org/whl/cu121`)
- **TripoSR** — 模型权重自动从 HuggingFace 下载，推理代码内置在 `scripts/3d-print/triposr_src/`
- **Trimesh** + **PyMeshFix** (`pip install trimesh pymeshfix`)
- **Python 依赖**: `pip install einops omegaconf transformers rembg[gpu] imageio Pillow`

可选：
- **OrcaSlicer** (从 GitHub Release 下载安装) — 用于 STL 切片
- **MCP 3D Printer Server** (用于直接发送到 Bambu 打印机): `npx @anthropic/mcp-server-3d-printer`
- **bambulabs_api** (`pip install bambulabs_api`)
- **Hunyuan3D-2.1 WinPortable** — 高精度引擎备选（需要从百度网盘/夸克网盘手动下载）

## 快捷动作

### `/3d-print status`
显示当前管线状态和系统依赖：
```
🔧 3D打印管线状态
━━━━━━━━━━━━━━━━━━━━━━
  GPU: {gpu_name} ({vram_gb}GB)
  TripoSR: {installed/not installed}
  Trimesh: {installed/not installed}
  PyMeshFix: {installed/not installed}
  OrcaSlicer: {installed/not installed}
━━━━━━━━━━━━━━━━━━━━━━
```

### `/3d-print generate <image_path> [--no-bg-remove] [--resolution N] [--format glb|obj]`
从图片生成3D模型（Stage 1）。
- 运行 `image-to-3d.py`
- 支持格式：jpg/png/webp
- 输出：`output/<image>_3d.glb`
- `--no-bg-remove`：跳过背景去除（适用于已预处理图像）
- `--resolution`：Marching Cubes 分辨率，默认 256（范围 64-384）

### `/3d-print repair <mesh_path> [--scale N]`
修复和准备打印文件（Stage 2）。
- 运行 `mesh-repair.py`
- 自动修复：去重面、填洞、法线校正、watertight 检查
- 缩放、居中、落地
- 输出：`<mesh>_print.stl`

### `/3d-print full <image_path> [--scale N] [--resolution N] [--no-bg-remove]`
一键全流程（推荐）。
- Stage 1 → Stage 2 自动衔接
- 打印每个阶段的中间结果
- 最终输出 watertight .stl，可直接导入 OrcaSlicer

### `/3d-print slice <stl_path>`
调用 OrcaSlicer CLI 切片（需要安装 OrcaSlicer）。
```bash
orcaslicer --orient 1 --arrange 1 \
  --load-settings "printer.json;process.json" \
  --slice 0 --export-3mf output.3mf <stl_path>
```

### `/3d-print install-deps`
安装 TripoSR 推理依赖。通过 pip 安装 einops, omegaconf, transformers, rembg[gpu], imageio。模型权重会在首次运行时自动下载。

### `/3d-print download-model`
手动下载 TripoSR 模型权重到 HF 缓存。
```bash
python -c "
from huggingface_hub import hf_hub_download
hf_hub_download('stabilityai/TripoSR', 'model.ckpt', local_dir='~/.cache/huggingface/models/triposr')
hf_hub_download('stabilityai/TripoSR', 'config.yaml', local_dir='~/.cache/huggingface/models/triposr')
"
```

## GPU 适配规则

| VRAM | 状态 | 说明 |
|------|------|------|
| < 4GB | ❌ 不可用 | VRAM 不足 |
| 4-6GB | ⚠️ 可用 | 降低 mc_resolution 到 128 |
| 6-8GB | ✅ 正常 | mc_resolution 256，当前配置 |
| > 8GB | ✅ 理想 | mc_resolution 384 |

## 数据文件

项目目录下的输出：
- `output/*.glb` — Stage 1 生成
- `output/*_print.stl` — Stage 2 输出
- `output/*.3mf` — Stage 3 输出

## 注意事项

- TripoSR 模型权重（~1.6GB）首次运行时自动从 HuggingFace 下载
- 生成时间参考：RTX 3060 (6GB) ~2-3秒推理 + ~20秒模型加载
- 输出 .stl 默认单位：米（trimesh 标准），导入 OrcaSlicer 时可能需要缩放
- 如遇 CUDA OOM，降低 `--resolution` 参数（如 128 或 192）
- 带透明通道的 RGBA 图片会自动合成到灰色背景上
- rembg 背景去除对主体突出的照片效果最好
