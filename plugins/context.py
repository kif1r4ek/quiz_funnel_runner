"""Plugin context passed into create_plugin(ctx)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PluginContext:
    """Shared dependencies for plugin factories."""

    defaults: dict[str, str] = field(default_factory=dict)
