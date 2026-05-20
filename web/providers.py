"""providers.py - Text-to-Image provider abstraction layer."""

import os
import re
import yaml
import base64
import httpx
import time
import uuid

from dataclasses import dataclass, field

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")
PROVIDERS_CONFIG = os.path.join(CONFIG_DIR, "providers.yaml")
DOTENV_PATH = os.path.join(CONFIG_DIR, ".env")
_config_cache = None
_config_mtime = 0
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output", "text2img")


def _load_dotenv(path: str) -> None:
    """Load KEY=VALUE pairs from a .env file into os.environ (only if not already set)."""
    if not os.path.isfile(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def _expand_env(value: str) -> str:
    """Expand ${VAR} and $VAR in string values."""
    if not isinstance(value, str):
        return value
    return os.path.expandvars(value)


def is_key_configured(api_key: str) -> bool:
    """Check if API key is actually set (not empty, not an unresolved placeholder)."""
    if not api_key or not api_key.strip():
        return False
    # Still contains unresolved ${...} placeholder
    if re.search(r'\$\{[^}]+\}', api_key):
        return False
    return True


def load_providers_config() -> list[dict]:
    global _config_cache, _config_mtime
    # Use mtime-based cache to avoid re-reading YAML on every call
    try:
        mtime = os.path.getmtime(PROVIDERS_CONFIG)
    except OSError:
        mtime = 0
    if _config_cache and _config_mtime == mtime:
        return _config_cache

    _load_dotenv(DOTENV_PATH)
    if not os.path.exists(PROVIDERS_CONFIG):
        providers = []
    else:
        with open(PROVIDERS_CONFIG, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        providers = raw.get("providers", [])
        for p in providers:
            p["api_key"] = _expand_env(p.get("api_key", ""))
    _config_cache = providers
    _config_mtime = mtime
    return providers


@dataclass
class ImageResult:
    provider: str
    width: int
    height: int
    image_path: str
    revised_prompt: str = ""
    elapsed_ms: float = 0


class BaseProvider:
    def __init__(self, config: dict):
        self.config = config
        self.api_key = config.get("api_key", "")
        self.api_base = config.get("api_base", "")
        self.model = config.get("model", "")
        self.default_size = config.get("default_size", "1024x1024")

    def _parse_size(self, size: str) -> tuple[int, int]:
        """Parse size string like '1024x1024' to (w, h)."""
        parts = size.split("x")
        return int(parts[0]), int(parts[1])

    async def generate(self, prompt: str, size: str = "", **kwargs) -> ImageResult:
        raise NotImplementedError


# ─── OpenAI-compatible base (works with DALL-E, Seedream, CogView) ───

class OpenAICompatImageProvider(BaseProvider):
    """Generic provider for OpenAI-compatible images/generations endpoints.

    Handles both b64_json and url response formats.
    Subclasses override _build_body / _supports_b64 to customize.
    """

    _supports_b64: bool = True

    def _build_body(self, body: dict) -> None:
        """Hook for subclasses to add extra body params."""
        pass

    async def generate(self, prompt: str, size: str = "", **kwargs) -> ImageResult:
        size = size or self.default_size
        w, h = self._parse_size(size)

        body = {
            "model": self.model,
            "prompt": prompt,
            "n": 1,
            "size": size,
        }
        if self._supports_b64:
            body["response_format"] = "b64_json"
        self._build_body(body)

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self.api_base}/images/generations",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            if resp.is_error:
                detail = ""
                try:
                    err_data = resp.json()
                    detail = err_data.get("error", {}).get("message", "")
                except Exception:
                    pass
                msg = f"API error {resp.status_code}: {detail or resp.text[:300]}"
                raise RuntimeError(msg)
            data = resp.json()

        return await self._parse_response(data, w, h)

    async def _parse_response(self, data: dict, w: int, h: int) -> ImageResult:
        item = data["data"][0]

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        fname = f"{self.config['id']}_{uuid.uuid4().hex[:8]}.png"
        path = os.path.join(OUTPUT_DIR, fname)

        if "b64_json" in item:
            with open(path, "wb") as f:
                f.write(base64.b64decode(item["b64_json"]))
        elif "url" in item:
            async with httpx.AsyncClient(timeout=60.0) as client:
                img_resp = await client.get(item["url"])
                img_resp.raise_for_status()
                with open(path, "wb") as f:
                    f.write(img_resp.content)
        else:
            raise RuntimeError(f"No b64_json or url in response: {list(item.keys())}")

        return ImageResult(
            provider=self.config["id"],
            width=w,
            height=h,
            image_path=path,
        )


# ─── OpenAI DALL-E ───

class OpenAIDALLEProvider(OpenAICompatImageProvider):
    def _build_body(self, body: dict) -> None:
        body["quality"] = self.config.get("quality", "standard")


# ─── Volcano Engine Seedream (火山引擎·豆包) ───

class VolcanoSeedreamProvider(OpenAICompatImageProvider):
    def _build_body(self, body: dict) -> None:
        body["watermark"] = False


# ─── Zhipu CogView (智谱AI) ───

class ZhipuCogViewProvider(OpenAICompatImageProvider):
    _supports_b64: bool = False  # CogView only returns url

    def _build_body(self, body: dict) -> None:
        quality = self.config.get("quality", "")
        if quality:
            body["quality"] = quality


# ─── Stability AI (non-OpenAI-compatible, kept separate) ───

class StabilityAIProvider(BaseProvider):
    async def generate(self, prompt: str, size: str = "", **kwargs) -> ImageResult:
        size = size or self.default_size
        w, h = self._parse_size(size)

        async with httpx.AsyncClient(timeout=120.0) as client:
            form = {
                "prompt": prompt,
                "output_format": "png",
            }
            resp = await client.post(
                f"{self.api_base}/stable-image/generate/ultra",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Accept": "application/json",
                },
                files={"none": ""},
                data=form,
            )
            resp.raise_for_status()
            data = resp.json()

        b64 = data.get("image", "")
        if not b64:
            raise RuntimeError(f"Stability API returned no image: {data}")

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        fname = f"stability_{uuid.uuid4().hex[:8]}.png"
        path = os.path.join(OUTPUT_DIR, fname)
        with open(path, "wb") as f:
            f.write(base64.b64decode(b64))

        return ImageResult(
            provider="stability",
            width=w,
            height=h,
            image_path=path,
        )


# ─── Provider registry ───

_PROVIDER_CLASSES = {
    "openai": OpenAIDALLEProvider,
    "volcengine": VolcanoSeedreamProvider,
    "zhipu": ZhipuCogViewProvider,
    "stability": StabilityAIProvider,
}


def get_provider(provider_id: str) -> BaseProvider | None:
    configs = load_providers_config()
    for cfg in configs:
        if cfg["id"] == provider_id and cfg.get("enabled", True):
            if not is_key_configured(cfg.get("api_key", "")):
                return None
            cls = _PROVIDER_CLASSES.get(provider_id)
            if cls:
                return cls(cfg)
    return None


def list_providers() -> list[dict]:
    """Return list of available providers with public info (no API keys)."""
    configs = load_providers_config()
    result = []
    for cfg in configs:
        key = cfg.get("api_key", "")
        key_ok = is_key_configured(key)
        enabled = cfg.get("enabled", True)
        result.append({
            "id": cfg["id"],
            "name": cfg["name"],
            "enabled": enabled,
            "api_key_set": key_ok,
            "available": enabled and key_ok,
            "default_size": cfg.get("default_size", "1024x1024"),
            "sizes": cfg.get("sizes", ["1024x1024"]),
        })
    return result
