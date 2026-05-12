# 模型权重

此目录存放 AI 模型的权重文件。

## TripoSR (必装)

从 HuggingFace 下载:

```bash
python -c "
from huggingface_hub import hf_hub_download
hf_hub_download('stabilityai/TripoSR', 'model.ckpt', local_dir='.')
hf_hub_download('stabilityai/TripoSR', 'config.yaml', local_dir='.')
"
```

或在无法访问 HuggingFace 时使用镜像:

```bash
set HF_ENDPOINT=https://hf-mirror.com
python -c "..."
```

需要文件:
- `model.ckpt` (~1.6GB) — TripoSR 模型权重
- `config.yaml` (~1KB) — 模型架构配置（已包含在 config/ 目录）

## Hunyuan3D-2.1 (可选)

WinPortable 整合包自带模型权重，不需要单独下载到此目录。
