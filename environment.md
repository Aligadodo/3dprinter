# 已验证环境配置

## 硬件

| 组件 | 型号/规格 |
|------|----------|
| GPU | NVIDIA GeForce RTX 3060 Laptop GPU |
| VRAM | 6 GB GDDR6 |
| RAM | 64 GB DDR4 |
| CPU | (检测自 laptop) |
| OS | Windows 11 Home China 10.0.26200 |
| 硬盘 | SSD |

## 软件

| 软件 | 版本 | 来源 |
|------|------|------|
| Python | 3.12 | python.org |
| PyTorch | 2.5.1+cu121 | pytorch.org |
| CUDA | 13.0 (Driver) | NVIDIA |
| cuDNN | (bundled with PyTorch) | — |
| Trimesh | 4.12.2 | pip |
| PyMeshFix | 0.18.1 | pip |
| PyVista | 0.48.1 | pip |
| einops | 0.8.2 | pip |
| omegaconf | 2.3.0 | pip |
| transformers | 5.8.0 | pip |
| rembg | 2.0.75 (onnxruntime-gpu 1.26.0) | pip |
| imageio | 2.37.3 | pip |
| numpy | 2.4.4 | pip |
| scipy | 1.17.1 | pip |
| scikit-image | 0.26.0 | pip |
| Pillow | (latest) | pip |

## TripoSR 模型

| 项目 | 值 |
|------|-----|
| 模型 | stabilityai/TripoSR |
| 权重 | model.ckpt (1,677,246,742 bytes) |
| 配置 | config.yaml |
| 下载源 | hf-mirror.com (HuggingFace 镜像) |
| 本地缓存 | ~/.cache/huggingface/models/triposr/ |
| VRAM 占用 | ~2.5 GB (推理) |
| 推理速度 | ~2s (mc_resolution=256) |
| 模型加载 | ~20s (1.6GB → GPU) |

## 网络

- GitHub (github.com) — 被屏蔽 (443 超时)
- HuggingFace (huggingface.co) — 需要镜像 (hf-mirror.com)
- PyTorch (download.pytorch.org) — 正常
- pip 镜像 — https://pypi.tuna.tsinghua.edu.cn/simple

## Python 编码

Windows 默认 GBK，所有脚本需要设置：

```python
# 在脚本开头
import os, sys
os.environ["PYTHONIOENCODING"] = "utf-8"

# open() 时显式指定
open(path, encoding='utf-8')
```

或运行时：`export PYTHONIOENCODING=utf-8`

## 已知限制

1. TripoSR `torchmcubes` 不支持 Windows → 已修改 `isosurface.py` 使用 `skimage.measure.marching_cubes`
2. `pymeshfix.repair()` 不接受 `verbose` 参数 (v0.18.1) → 已移除
3. `trimesh.Trimesh` 无 `remove_duplicate_faces()` / `remove_degenerate_faces()` → 改用 `update_faces(mask)`
4. HF 缓存不支持 symlink (Windows 未开开发者模式) → 设置 `HF_HUB_DISABLE_SYMLINKS_WARNING=1`
5. HuggingFace Space 的 `camera.pyc` 和 `dino.pyc` 是 Py3.10 字节码 → 确认不需要，已排除

## 验证记录

- 2026-05-10: TripoSR 端到端管线测试通过 (test_input.png → test_input_3d.glb → test_input_3d_print.stl)
  - 输入: 512x512 RGB
  - 输出: 9,824 顶点 / 19,644 面, 1007×753×388 mm, watertight, 57.4 cm³
