from __future__ import annotations

import unittest

from plugins.context import PluginContext
from plugins.paywall import create_plugin


class _FakeElement:
    def __init__(self, visible: bool = True) -> None:
        self._visible = visible

    def is_visible(self, timeout: int = 0) -> bool:  # noqa: ARG002
        return self._visible


class _FakeLocator:
    def __init__(self, count: int, visible: bool = True) -> None:
        self._count = count
        self._visible = visible

    def count(self) -> int:
        return self._count

    def nth(self, idx: int) -> _FakeElement:  # noqa: ARG002
        return _FakeElement(self._visible)


class _FakePage:
    def __init__(self, class_hits: int, body_text: str) -> None:
        self._class_hits = class_hits
        self._body_text = body_text

    def locator(self, selector: str) -> _FakeLocator:  # noqa: ARG002
        return _FakeLocator(self._class_hits)

    def inner_text(self, selector: str) -> str:  # noqa: ARG002
        return self._body_text


class PaywallPluginTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plugin = create_plugin(PluginContext(defaults={}))

    def test_detects_paywall(self) -> None:
        page = _FakePage(
            class_hits=3,
            body_text="Choose your plan: $19.99 per month. Free trial available.",
        )
        self.assertTrue(self.plugin.can_handle(page))

    def test_avoids_false_positive(self) -> None:
        page = _FakePage(class_hits=0, body_text="Tell us your age and goals")
        self.assertFalse(self.plugin.can_handle(page))


if __name__ == "__main__":
    unittest.main()
