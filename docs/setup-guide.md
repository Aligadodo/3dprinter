# 3D 打印管线 — 安装指南

## 适用环境

- Windows 10/11 (64-bit)
- NVIDIA GPU ≥ 6GB VRAM (推荐 RTX 3060+)
- 16GB+ 系统内存 (推荐 32GB+)

## 步骤 1: Python 环境

```powershell
# 推荐 Python 3.10–3.12
python --version

# 创建虚拟环境 (可选但推荐)
python -m venv .venv
.venv\Scripts\activate
```

## 步骤 2: PyTorch with CUDA

```powershell
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

验证：
```python
import torch
print(torch.cuda.is_available())  # True
print(torch.cuda.get_device_name(0))  # NVIDIA GeForce RTX ...
```

## 步骤 3: 网格处理依赖

```powershell
pip install trimesh pymeshfix pyvista
```

## 步骤 4: TripoSR 推理依赖

```powershell
pip install einops omegaconf transformers "rembg[gpu]" imageio Pillow scikit-image
```

注意：rembg 首次运行会下载 `u2net.onnx` (~176MB) 到 `~/.u2net/`。

## 步骤 5: 下载 TripoSR 模型

```powershell
# 如果 GitHub 可访问，直接从 HF 下载
python -c "
from huggingface_hub import hf_hub_download
import os
os.makedirs('models', exist_ok=True)
hf_hub_download('stabilityai/TripoSR', 'model.ckpt', local_dir='models')
hf_hub_download('stabilityai/TripoSR', 'config.yaml', local_dir='models')
"
```

如果 GitHub 不可访问，使用 HF 镜像：
```powershell
# 需要先配置 HF 镜像
set HF_ENDPOINT=https://hf-mirror.com
```

模型文件:
- `models/model.ckpt` — 1.6GB (权重)
- `models/config.yaml` — 1KB (模型配置，已包含在 repo 中)

## 步骤 6: 验证安装

```powershell
python scripts/image-to-3d.py path/to/test_image.jpg --resolution 128
```

预期输出:
```
{
  "output": "output/test_image_3d.glb",
  "engine": "triposr",
  "vertices": ...,
  "faces": ...,
  "watertight": true
}
```

## Hunyuan3D-2.1 (可选，备选引擎)

1. 从百度网盘/夸克网盘下载 WinPortable 整合包（链接见 `hunyuan3d/download-links.md`）
2. 解压到不含中文/空格的路径
3. 配置 scripts 目录下的推理脚本（开发中）

## Claude Code 集成

将 `skills/3d-print-SKILL.md` 复制到你的 Claude Code 项目 `.claude/skills/3d-print/SKILL.md`。

快捷指令:
- `/3d-print status` — 管线状态
- `/3d-print generate <image>` — 图片→3D
- `/3d-print repair <mesh>` — 网格修复
- `/3d-print full <image>` — 一键全流程

## 排错

### CUDA 不可用
```powershell
nvidia-smi  # 确认驱动已装
pip uninstall torch && pip install torch --index-url https://download.pytorch.org/whl/cu121
```

### rembg 报 "No onnxruntime backend found"
```powershell
pip install "rembg[gpu]"  # 不要只装 rembg
```

### Unicode 编码错误 (Windows)
```powershell
$env:PYTHONIOENCODING = "utf-8"
```
