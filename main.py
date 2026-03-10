"""Entry point for Quiz Funnel Runner."""

from __future__ import annotations

import time

from config import DEFAULTS, DEVICE_NAME, FUNNELS, HEADLESS, LOCALE, PLUGINS_DIR, RESULTS_DIR
from plugins.context import PluginContext
from plugins.loader import load_plugins
from screenshotter import Screenshotter
from plugins.registry import StrategyRegistry


def build_registry_from_plugins(ctx: PluginContext, plugins_dir: str = PLUGINS_DIR) -> StrategyRegistry:
    """Build StrategyRegistry from dynamically discovered plugins."""
    plugins = load_plugins(ctx, plugins_dir)
    if not plugins:
        raise RuntimeError(f"No valid plugins found in '{plugins_dir}'")

    registry = StrategyRegistry()
    for plugin in plugins:
        registry.register(plugin)

    order = ", ".join(f"{plugin.name}:{plugin.priority}" for plugin in plugins)
    print(f"[plugins] loaded {len(plugins)} plugin(s): {order}")
    return registry


def build_registry(plugins_dir: str = PLUGINS_DIR) -> StrategyRegistry:
    """Legacy alias kept for compatibility during migration."""
    return build_registry_from_plugins(PluginContext(defaults=DEFAULTS), plugins_dir=plugins_dir)


def main() -> int:
    # Keep heavy Playwright dependency lazy so utility imports (tests/tooling) work
    # even when Playwright is not installed in the current environment.
    from playwright.sync_api import sync_playwright

    from runner import run_funnel

    screenshotter = Screenshotter(RESULTS_DIR)
    screenshotter.ensure_base_dirs()

    plugin_ctx = PluginContext(defaults=DEFAULTS)
    registry = build_registry_from_plugins(plugin_ctx, plugins_dir=PLUGINS_DIR)

    results: list[dict] = []
    run_start = time.time()

    browser = None
    try:
        with sync_playwright() as playwright:
            if DEVICE_NAME not in playwright.devices:
                raise RuntimeError(f"Unknown Playwright device preset: '{DEVICE_NAME}'")

            browser = playwright.chromium.launch(headless=HEADLESS)
            device_config = {**playwright.devices[DEVICE_NAME], "locale": LOCALE}

            for idx, url in enumerate(FUNNELS, start=1):
                print(f"\n{'=' * 60}")
                print(f"[Funnel {idx}/{len(FUNNELS)}] {url}")
                print(f"{'=' * 60}")

                result = run_funnel(url, browser, device_config, registry, screenshotter)
                results.append(result)

                if result["error"]:
                    status = "ERROR"
                elif result["paywall_reached"]:
                    status = "OK"
                else:
                    status = "INCOMPLETE"
                print(
                    f"  => [{status}] steps={result['steps']}, "
                    f"reason={result['stop_reason']}, "
                    f"time={result['duration_sec']}s"
                )
                if result["error"]:
                    print(f"     error: {result['error']}")
                elif not result["paywall_reached"]:
                    print("     [!] paywall/checkout не достигнут")

            browser.close()

    except KeyboardInterrupt:
        print("\n\n[Interrupted] Shutting down gracefully...")
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass
        return 130

    total_time = round(time.time() - run_start, 1)
    passed = [r for r in results if r["paywall_reached"] and not r["error"]]
    incomplete = [r for r in results if not r["paywall_reached"] and not r["error"]]
    failed = [r for r in results if r["error"]]

    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    print(f"Funnels total  : {len(FUNNELS)}")
    print(f"Reached paywall: {len(passed)}")
    print(f"Incomplete     : {len(incomplete)}")
    print(f"Errors         : {len(failed)}")
    print(f"Total time     : {total_time}s")

    if incomplete:
        print("\nIncomplete funnels (paywall/checkout not reached):")
        for result in incomplete:
            print(f"  - {result['url']}")
            print(f"    stopped: {result['stop_reason']}")

    if failed:
        print("\nFailed funnels:")
        for result in failed:
            print(f"  - {result['url']}")
            print(f"    reason: {result['stop_reason']}")

    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
