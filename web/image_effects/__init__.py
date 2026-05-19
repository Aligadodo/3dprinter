"""image_effects — Extensible image effect/style transfer package.

Each effect is a subclass of BaseEffect registered in the global registry.
New effects can be added by creating a class and decorating with @register_effect.
"""
from __future__ import annotations

from web.image_effects.base import BaseEffect

_registry: dict[str, BaseEffect] = {}


def register_effect(cls):
    """Decorator to register an effect class in the global registry."""
    instance = cls()
    _registry[instance.name] = instance
    return cls


def get_effect(name: str) -> BaseEffect:
    """Look up an effect by its short name."""
    if name not in _registry:
        raise ValueError(f"Unknown effect: {name}. Available: {list(_registry.keys())}")
    return _registry[name]


def list_effects() -> list[str]:
    """Return all registered effect names."""
    return sorted(_registry.keys())


def apply_effect(name: str, img, strength: float = 0.8,
                 detail: int = 5, color_scheme: str = "warm"):
    """Apply a named effect to an image (convenience function)."""
    effect = get_effect(name)
    return effect.apply(img, strength=strength, detail=detail, color_scheme=color_scheme)


# Import effect modules to trigger @register_effect decorators
from web.image_effects import artistic, retro, color, distortion  # noqa: E402, F401
