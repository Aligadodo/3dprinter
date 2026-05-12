# Text-to-Image Integration

## Overview

The text-to-image feature calls cloud AI APIs to convert text descriptions into high-quality images, which can be used directly as input for downstream 3D pipeline tasks. The system supports 4 providers with flexible YAML-based enable/disable configuration.

## Supported Providers

### Volcengine Seedream (Doubao) ⭐ Default

- **Model**: doubao-seedream-5-0-260128
- **Supported sizes**: 2048×2048, 4096×4096
- **Default size**: 2048×2048
- **API base**: `https://ark.cn-beijing.volces.com/api/v3`
- **Status**: Enabled (default)

### Zhipu CogView (Free)

- **Model**: cogview-3-flash
- **Supported sizes**: 1024×1024, 768×1344, 1152×864
- **Default size**: 1024×1024
- **API base**: `https://open.bigmodel.cn/api/paas/v4`
- **Status**: Enabled (free fallback)

### OpenAI DALL-E 3

- **Model**: dall-e-3
- **Quality**: standard/hd
- **Supported sizes**: 1024×1024, 1792×1024, 1024×1792
- **Default size**: 1024×1024
- **API base**: `https://api.openai.com/v1`
- **Status**: Disabled by default

### Stability AI

- **Model**: stable-image-generate (Ultra)
- **Supported sizes**: 1024×1024
- **Default size**: 1024×1024
- **API base**: `https://api.stability.ai/v2beta`
- **Status**: Disabled by default

## Configuration

### YAML Provider Configuration

Provider configuration is stored in `config/providers.yaml`:

```yaml
providers:
  - id: volcengine
    name: Volcengine Seedream (Doubao)
    enabled: true
    api_key: ${VOLCENGINE_API_KEY}
    api_base: https://ark.cn-beijing.volces.com/api/v3
    model: doubao-seedream-5-0-260128
    default_size: "2048x2048"
    sizes: ["2048x2048", "4096x4096"]

  - id: zhipu
    name: Zhipu CogView (Free)
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

### Setting API Keys

Keys can be set in two ways (checked in priority order):

**Method 1: Environment Variables**
```bash
# Windows
set VOLCENGINE_API_KEY=your-key-here

# Linux/macOS
export VOLCENGINE_API_KEY="your-key-here"
```

**Method 2: .env File (Recommended)**
1. Copy `config/.env.example` to `config/.env`
2. Fill in your actual API keys:

```ini
VOLCENGINE_API_KEY=your-key-here
ZHIPU_API_KEY=your-key-here
OPENAI_API_KEY=
STABILITY_API_KEY=
```

Only providers with actual key values will appear in the frontend options. The `.env` file is gitignored and never committed.

## Usage

### Web UI

1. Open the "New Task" page
2. Expand the "Text to Image" panel
3. Enter a prompt (Chinese and English both supported)
4. Select AI provider and image size
5. Click "Generate Image"
6. After generation, click "Use as Input" to set the image as input for the current task
7. Select a pipeline type, configure parameters, and submit

### API

```bash
POST /api/text2img
Content-Type: application/json

{
  "prompt": "A cute orange tabby cat sitting on a windowsill",
  "provider": "volcengine",
  "size": "2048x2048"
}
```

Response:
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
# Use Volcengine (default)
python scripts/text-to-image.py "A majestic mountain landscape"

# Use Zhipu
python scripts/text-to-image.py "A cute cat" --provider zhipu --size 1024x1024

# Use OpenAI
python scripts/text-to-image.py "Sunset over the ocean" --provider openai --size 1792x1024
```

CLI options:
- `--provider`: volcengine (default) / zhipu / openai / stability
- `--size`: Size string (e.g. 2048x2048)
- `--output`: Custom output path

## Provider Architecture

All providers share a unified interface through the abstract base class in `web/providers.py`:

```python
# Base class
class BaseProvider:
    async def generate(prompt: str, size: str, **kwargs) -> ImageResult

# OpenAI-compatible base (shared by DALL-E, Seedream, CogView)
class OpenAICompatImageProvider(BaseProvider):
    _supports_b64: bool = True  # b64_json format support

# Concrete implementations
class OpenAIDALLEProvider(OpenAICompatImageProvider):      # extra quality param
class VolcanoSeedreamProvider(OpenAICompatImageProvider):   # watermark=False
class ZhipuCogViewProvider(OpenAICompatImageProvider):      # _supports_b64=False (url only)
class StabilityAIProvider(BaseProvider):                    # Non-OpenAI-compatible, standalone
```

### API Key Resolution Flow

1. `load_providers_config()` is called
2. `_load_dotenv()` loads keys from `config/.env` into `os.environ` (only sets vars not already present)
3. `_expand_env()` expands `${VAR}` placeholders in YAML using `os.path.expandvars()`
4. `is_key_configured()` checks that the key is real (excludes empty values and unresolved placeholders)

Adding a new provider requires only:
1. Add configuration in `config/providers.yaml`
2. Create a new Provider subclass
3. Register it in the `_PROVIDER_CLASSES` registry
4. Update `config/.env.example`

## Output Files

Generated images are saved in the `output/text2img/` directory with filename format:
- `volcengine_<8-char random ID>.png` (Volcengine)
- `zhipu_<8-char random ID>.png` (Zhipu)
- `openai_<8-char random ID>.png` (OpenAI)
- `stability_<8-char random ID>.png` (Stability AI)

Images can be used directly with any pipeline type that accepts image input (Relief, Lithophane, Layered Relief, TripoSR, Hunyuan3D).
