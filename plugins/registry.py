"""Registry that resolves the first matching plugin by priority."""

from __future__ import annotations

from typing import Protocol


class ScreenHandler(Protocol):
    """Minimal contract required by the registry."""

    name: str

    def can_handle(self, page) -> bool:
        """Return True when handler matches current page."""

    def execute(self, page) -> bool:
        """Execute action and return whether runner should continue."""


class StrategyRegistry:
    """Ordered collection of plugins resolved by priority."""

    def __init__(self) -> None:
        self._handlers: list[ScreenHandler] = []

    def register(self, handler: ScreenHandler) -> None:
        self._handlers.append(handler)

    def resolve(self, page) -> ScreenHandler:
        if not self._handlers:
            raise RuntimeError("StrategyRegistry is empty")

        for handler in self._handlers:
            try:
                if handler.can_handle(page):
                    return handler
            except Exception as exc:
                print(f"[registry] can_handle failed for '{handler.name}': {exc}")

        raise RuntimeError("No handler matched the page")
