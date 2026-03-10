from __future__ import annotations

import unittest

from plugins.registry import StrategyRegistry


class _NeverPlugin:
    name = "never"

    def can_handle(self, page) -> bool:  # noqa: ARG002
        return False

    def execute(self, page) -> bool:  # noqa: ARG002
        return True


class _AlwaysPlugin:
    name = "always"

    def can_handle(self, page) -> bool:  # noqa: ARG002
        return True

    def execute(self, page) -> bool:  # noqa: ARG002
        return True


class StrategyRegistryTests(unittest.TestCase):
    def test_resolve_respects_priority_order(self) -> None:
        registry = StrategyRegistry()
        registry.register(_NeverPlugin())
        registry.register(_AlwaysPlugin())

        resolved = registry.resolve(page=object())
        self.assertEqual(resolved.name, "always")


if __name__ == "__main__":
    unittest.main()
