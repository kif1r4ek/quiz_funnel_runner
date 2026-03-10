"""Dynamic plugin loading for screen handlers."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from plugins.base import ScreenPlugin
from plugins.context import PluginContext

_SERVICE_MODULES = {"__init__", "base", "loader", "context", "registry"}


def _warn(message: str) -> None:
    print(f"[plugin-loader] warning: {message}")


def _import_module(path: Path):
    module_name = f"qfr_plugin_{path.stem}_{abs(hash(path.resolve()))}"
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    if spec is None or spec.loader is None:
        raise ImportError("cannot build import spec")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _validate_plugin(plugin: object, filename: str) -> bool:
    name = getattr(plugin, "name", None)
    if not isinstance(name, str) or not name.strip():
        _warn(f"{filename}: invalid plugin.name={name!r}")
        return False

    priority = getattr(plugin, "priority", None)
    if isinstance(priority, bool) or not isinstance(priority, int):
        _warn(f"{filename}: invalid plugin.priority={priority!r}")
        return False

    can_handle = getattr(plugin, "can_handle", None)
    execute = getattr(plugin, "execute", None)
    if not callable(can_handle) or not callable(execute):
        _warn(f"{filename}: plugin must define callable can_handle(page) and execute(page)")
        return False

    return True


def _load_one(path: Path, ctx: PluginContext) -> ScreenPlugin | None:
    try:
        module = _import_module(path)
    except Exception as exc:
        _warn(f"{path.name}: import failed: {exc}")
        return None

    factory = getattr(module, "create_plugin", None)
    if not callable(factory):
        _warn(f"{path.name}: missing create_plugin(ctx)")
        return None

    try:
        plugin = factory(ctx)
    except Exception as exc:
        _warn(f"{path.name}: create_plugin failed: {exc}")
        return None

    if not _validate_plugin(plugin, path.name):
        return None

    return plugin


def load_plugins(ctx: PluginContext, plugins_dir: str | Path) -> list[ScreenPlugin]:
    """Load all valid plugins from top-level *.py files in *plugins_dir*."""

    root = Path(plugins_dir)
    if not root.exists():
        _warn(f"plugins dir does not exist: {root}")
        return []
    if not root.is_dir():
        _warn(f"plugins path is not a directory: {root}")
        return []

    loaded: list[tuple[ScreenPlugin, str]] = []
    for path in sorted(root.glob("*.py")):
        if path.stem in _SERVICE_MODULES:
            continue
        plugin = _load_one(path, ctx)
        if plugin is not None:
            loaded.append((plugin, path.name))

    loaded.sort(key=lambda item: (-item[0].priority, item[0].name, item[1]))

    deduped: list[ScreenPlugin] = []
    seen_names: set[str] = set()
    for plugin, filename in loaded:
        if plugin.name in seen_names:
            _warn(f"{filename}: duplicate plugin name '{plugin.name}' skipped")
            continue
        seen_names.add(plugin.name)
        deduped.append(plugin)

    return deduped
