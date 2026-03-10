"""Plugin contract for screen handlers."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ScreenPlugin(Protocol):
    """Runtime contract for dynamically loaded screen plugins."""

    name: str
    priority: int

    def can_handle(self, page) -> bool:
        """Return True when this plugin matches current page."""

    def execute(self, page) -> bool:
        """Execute action and return whether runner should continue."""
