from __future__ import annotations

import unittest

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright
except ModuleNotFoundError:
    PlaywrightError = RuntimeError
    sync_playwright = None

from main import build_registry_from_plugins
from plugins.context import PluginContext


class PlaywrightSmokeTests(unittest.TestCase):
    def test_strategy_resolution_offline(self) -> None:
        if sync_playwright is None:
            self.skipTest("Playwright Python package is not installed")

        registry = build_registry_from_plugins(PluginContext(defaults={}))

        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
            except PlaywrightError as exc:
                self.skipTest(f"Playwright browser launch unavailable in current sandbox: {exc}")
                return

            context = browser.new_context()
            page = context.new_page()

            page.set_content(
                """
                <main>
                  <h1>How active are you?</h1>
                  <button class='option'>Low</button>
                  <button class='option'>High</button>
                </main>
                """
            )
            self.assertEqual(registry.resolve(page).name, "question")

            page.set_content(
                """
                <main>
                  <label>Email</label>
                  <input type='email' placeholder='Enter email'>
                  <button>Continue</button>
                </main>
                """
            )
            self.assertEqual(registry.resolve(page).name, "email")

            page.set_content(
                """
                <main>
                  <div class='pricing-card'>Best plan</div>
                  <p>$29.99 per month</p>
                </main>
                """
            )
            self.assertEqual(registry.resolve(page).name, "paywall")

            context.close()
            browser.close()


if __name__ == "__main__":
    unittest.main()
