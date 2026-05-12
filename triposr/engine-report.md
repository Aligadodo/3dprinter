# TripoSR 引擎分析报告

## 基本信息

| 项目 | 内容 |
|------|------|
| 名称 | TripoSR |
| 开发者 | Stability AI × Tripo AI |
| 开源协议 | MIT |
| 论文 | [arXiv:2403.02151](https://arxiv.org/abs/2403.02151) |
| 模型页 | huggingface.co/stabilityai/TripoSR |
| Demo | huggingface.co/spaces/stabilityai/TripoSR |
| 代码仓库 | github.com/VAST-AI-Research/TripoSR |
| 发布时间 | 2024-03 |

## 技术架构

```
TripoSR = DINO ViT Encoder + Transformer Decoder + NeRF Renderer
```

### 编码器: DINO ViT-B/16

- 来源: `facebook/dino-vitb16` (HuggingFace)
- 参数量: ~86M
- 输出: 768-dim token embeddings
- 输入: 512×512 RGB (预处理后)

### Transformer 主干

- 类型: Transformer1D (decoder-only)
- 层数: 16
- 注意力头: 16
- 头维度: 64
- 交叉注意力到图像 tokens
- 参数量: ~100M

### Triplane Tokenizer

- 可学习参数: 3 × 1024 × 32 × 32 (~3.1M)
- 输出格式: triplane (3 planes × 32²)
- 上采样: ConvTranspose2d → 40 channels × 64²

### NeRF 渲染器

- 解码器: 9 层 MLP (64 neurons, SiLU)
- 采样: 128 samples/ray
- 半径: 0.87
- 颜色输出: sigmoid (3 channels)
- 密度输出: exp(density - 1.0)

### Marching Cubes

- 默认分辨率: 256³ grid
- 密度阈值: 25.0
- 实现: skimage.measure.marching_cubes (已替换 torchmcubes)

## 性能基准

实测环境: RTX 3060 Laptop GPU (6GB), 64GB RAM, Python 3.12, PyTorch 2.5.1

| 指标 | 值 |
|------|-----|
| 模型加载 | ~20s (1.6GB → GPU) |
| 推理 (图像编码 + 生成) | ~1.5s |
| Marching Cubes (256³) | ~0.3s |
| **总生成时间** | **~22s** (含加载) |
| VRAM 峰值 | ~3.5 GB |
| RAM 占用 | ~2 GB |

## 输出质量

### 优势
- 极快的推理速度 (2-3s)
- 低 VRAM 需求 (~2.5GB)
- 开源 MIT 协议
- 顶点色输出 (带纹理外观)
- 直接从 HF Hub 加载

### 局限
- 单视图输入 → 背面缺乏细节
- 没有分离的 UV 纹理 (仅顶点色)
- 对复杂几何 (细杆、镂空) 容易出瑕疵
- 预处理步骤 (rembg) 对背景复杂的图片效果不稳定
- 网格面数偏高 (~10K–200K faces)

### 适用场景
- 快速原型 (几秒出结果)
- 简单形状 (玩具、装饰品)
- 主体突出、背景干净的图片
- VRAM 受限环境 (4-6GB)

## Windows 适配修改

### 1. torchmcubes → skimage

原始代码使用 `torchmcubes` (仅 Linux+Python 3.10 wheel):
```python
from torchmcubes import marching_cubes
```
改为：
```python
from skimage.measure import marching_cubes
def _marching_cubes(level, isovalue):
    verts, faces, _, _ = marching_cubes(level.cpu().numpy(), isovalue)
    return torch.from_numpy(verts.copy()).to(level.device), \
           torch.from_numpy(faces.copy()).long().to(level.device)
```

### 2. 已确认不需要的文件

HF Space 中 `camera.pyc` 和 `dino.pyc` 是 Python 3.10 字节码，无法在 3.12 运行。
经验证：这两个文件未被当前 config.yaml 引用的任何模块导入，是不需要的遗留文件。

### 3. DINO ViT 模型

`DINOSingleImageTokenizer` 直接使用 HuggingFace `transformers.ViTModel` 加载，
不需本地 DINO 代码。

## 依赖关系

```
tsr/system.py
├── tsr/utils.py
│   ├── rembg (背景去除)
│   ├── PIL.Image
│   ├── torch/numpy
│   └── omegaconf
├── tsr/models/
│   ├── isosurface.py (Marching Cubes)
│   ├── nerf_renderer.py (NeRF 渲染)
│   ├── network_utils.py (TriplaneUpsample + NeRFMLP)
│   ├── tokenizers/
│   │   ├── image.py (DINO ViT Encoder)
│   │   └── triplane.py (Triplane1D Tokenizer)
│   └── transformer/
│       ├── transformer_1d.py
│       ├── attention.py
│       └── basic_transformer_block.py
└── model.ckpt + config.yaml (stabilityai/TripoSR)
```

## 下载说明

模型权重可从 HuggingFace 下载：

```python
from huggingface_hub import hf_hub_download

# 仅需两个文件
hf_hub_download('stabilityai/TripoSR', 'model.ckpt', local_dir='models')
hf_hub_download('stabilityai/TripoSR', 'config.yaml', local_dir='models')
```

总大小: ~1.6GB。国内用户可使用 HF 镜像 `HF_ENDPOINT=https://hf-mirror.com`。

推理代码已包含在 `triposr/src/` 目录中（从 HuggingFace Space 下载）。
