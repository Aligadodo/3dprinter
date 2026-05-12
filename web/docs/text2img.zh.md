# 文生图集成说明

## 概述

文生图功能通过调用云端 AI API，将文字描述转换为高质量图片，可直接用作后续 3D 流水线的输入。系统支持 4 家供应商，可通过 YAML 配置文件灵活启用/禁用。

## 支持的供应商

### 火山引擎 Seedream（豆包） ⭐ 首选

- **模型**: doubao-seedream-5-0-260128
- **支持尺寸**: 2048×2048, 4096×4096
- **默认尺寸**: 2048×2048
- **API 基础**: `https://ark.cn-beijing.volces.com/api/v3`
- **状态**: 默认已启用

### 智谱AI CogView（免费）

- **模型**: cogview-3-flash
- **支持尺寸**: 1024×1024, 768×1344, 1152×864
- **默认尺寸**: 1024×1024
- **API 基础**: `https://open.bigmodel.cn/api/paas/v4`
- **状态**: 默认已启用（免费备选）

### OpenAI DALL-E 3

- **模型**: dall-e-3
- **质量**: standard/hd
- **支持尺寸**: 1024×1024, 1792×1024, 1024×1792
- **默认尺寸**: 1024×1024
- **API 基础**: `https://api.openai.com/v1`
- **状态**: 默认未启用

### Stability AI

- **模型**: stable-image-generate (Ultra)
- **支持尺寸**: 1024×1024
- **默认尺寸**: 1024×1024
- **API 基础**: `https://api.stability.ai/v2beta`
- **状态**: 默认未启用

## 配置

### YAML 供应商配置

供应商配置存储在 `config/providers.yaml`：

```yaml
providers:
  - id: volcengine
    name: 火山引擎 Seedream (豆包)
    enabled: true
    api_key: ${VOLCENGINE_API_KEY}
    api_base: https://ark.cn-beijing.volces.com/api/v3
    model: doubao-seedream-5-0-260128
    default_size: "2048x2048"
    sizes: ["2048x2048", "4096x4096"]

  - id: zhipu
    name: 智谱AI CogView (免费)
    enabled: true
    api_key: ${ZHIPU_API_KEY}
    api_base: https://open.bigmodel.cn/api/paas/v4
    model: cogview-3-flash
    default_size: "1024x1024"
    sizes: ["1024x1024", "768x1344", "1152x864"]

  - id: openai
    name: OpenAI DALL-E 3
    enabled: false
    api_key: ${OPENAI_API_KEY}
    api_base: https://api.openai.com/v1
    model: dall-e-3
    default_size: "1024x1024"
    sizes: ["1024x1024", "1792x1024", "1024x1792"]

  - id: stability
    name: Stability AI
    enabled: false
    api_key: ${STABILITY_API_KEY}
    api_base: https://api.stability.ai/v2beta
    model: stable-image-generate
    default_size: "1024x1024"
    sizes: ["1024x1024"]
```

### 设置 API 密钥

密钥有两种配置方式（按优先级检查）：

**方式一：环境变量**
```bash
# Windows
set VOLCENGINE_API_KEY=your-key-here

# Linux/macOS
export VOLCENGINE_API_KEY="your-key-here"
```

**方式二：.env 文件（推荐）**
1. 复制 `config/.env.example` 为 `config/.env`
2. 填入实际的 API 密钥：

```ini
VOLCENGINE_API_KEY=your-key-here
ZHIPU_API_KEY=your-key-here
OPENAI_API_KEY=
STABILITY_API_KEY=
```

只有填写了实际密钥的供应商才会出现在前端选项中。`.env` 文件已加入 `.gitignore`，不会被提交到仓库。

## 使用方式

### Web UI

1. 打开「新建任务」页面
2. 展开「文生图」面板
3. 输入提示词（支持中文和英文）
4. 选择 AI 供应商和图片尺寸
5. 点击「生成图片」
6. 生成完成后，点击「用作输入」将图片设为当前任务的输入文件
7. 选择流水线类型，设置参数，提交任务

### API

```bash
POST /api/text2img
Content-Type: application/json

{
  "prompt": "一只橘猫在窗台上晒太阳",
  "provider": "volcengine",
  "size": "2048x2048"
}
```

响应：
```json
{
  "image_path": "D:/projects/3dprint/output/text2img/volcengine_a1b2c3d4.png",
  "provider": "volcengine",
  "width": 2048,
  "height": 2048,
  "revised_prompt": "..."
}
```

### CLI

```bash
# 使用火山引擎（默认）
python scripts/text-to-image.py "A majestic mountain landscape"

# 使用智谱AI
python scripts/text-to-image.py "一只可爱的猫咪" --provider zhipu --size 1024x1024

# 使用 OpenAI
python scripts/text-to-image.py "Sunset over the ocean" --provider openai --size 1792x1024
```

CLI 选项：
- `--provider`: volcengine（默认）/ zhipu / openai / stability
- `--size`: 尺寸字符串（如 2048x2048）
- `--output`: 自定义输出路径

## Provider 架构

所有供应商通过 `web/providers.py` 中的抽象基类统一接口：

```python
# 基类
class BaseProvider:
    async def generate(prompt: str, size: str, **kwargs) -> ImageResult

# OpenAI 兼容基类（DALL-E、Seedream、CogView 共用）
class OpenAICompatImageProvider(BaseProvider):
    _supports_b64: bool = True  # b64_json format support

# 具体实现
class OpenAIDALLEProvider(OpenAICompatImageProvider):      # 额外 quality 参数
class VolcanoSeedreamProvider(OpenAICompatImageProvider):   # watermark=False
class ZhipuCogViewProvider(OpenAICompatImageProvider):      # _supports_b64=False (url only)
class StabilityAIProvider(BaseProvider):                    # 非 OpenAI 兼容，独立实现
```

### API 密钥解析流程

1. `load_providers_config()` 被调用
2. `_load_dotenv()` 从 `config/.env` 加载密钥到 `os.environ`（仅设置尚未存在的变量）
3. `_expand_env()` 用 `os.path.expandvars()` 展开 YAML 中的 `${VAR}` 占位符
4. `is_key_configured()` 检查密钥是否真实有效（排除空值和未解析占位符）

添加新供应商只需：
1. 在 `config/providers.yaml` 中添加配置
2. 创建新的 Provider 子类
3. 在 `_PROVIDER_CLASSES` 注册表中注册
4. 更新 `config/.env.example`

## 输出文件

生成的图片保存在 `output/text2img/` 目录下，文件名格式：
- `volcengine_<8位随机ID>.png`（火山引擎）
- `zhipu_<8位随机ID>.png`（智谱AI）
- `openai_<8位随机ID>.png`（OpenAI）
- `stability_<8位随机ID>.png`（Stability AI）

图片可直接用于任何接受图片输入的流水线类型（浮雕、夜灯、套色浮雕、TripoSR、Hunyuan3D）。
