from __future__ import annotations

import io
import tempfile
import textwrap
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from main import build_registry_from_plugins
from plugins.context import PluginContext
from plugins.loader import load_plugins


def _write(path: Path, content: str) -> None:
    path.write_text(textwrap.dedent(content), encoding="utf-8")


class PluginLoaderTests(unittest.TestCase):
    def test_builtin_plugins_priority_order(self) -> None:
        plugins = load_plugins(PluginContext(defaults={}), "plugins")

        self.assertEqual(
            [plugin.name for plugin in plugins],
            ["checkout", "paywall", "email", "input", "question", "chart", "info", "other"],
        )
        self.assertEqual(
            [plugin.priority for plugin in plugins],
            [1000, 900, 800, 700, 600, 500, 400, 0],
        )

    def test_sorts_by_priority_then_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _write(
                root / "zeta.py",
                """
                class P:
                    name = "zeta"
                    priority = 10

                    def can_handle(self, page):
                        return False

                    def execute(self, page):
                        return True


                def create_plugin(ctx):
                    return P()
                """,
            )
            _write(
                root / "alpha.py",
                """
                class P:
                    name = "alpha"
                    priority = 10

                    def can_handle(self, page):
                        return False

                    def execute(self, page):
                        return True


                def create_plugin(ctx):
                    return P()
                """,
            )
            _write(
                root / "omega.py",
                """
                class P:
                    name = "omega"
                    priority = 99

                    def can_handle(self, page):
                        return False

                    def execute(self, page):
                        return True


                def create_plugin(ctx):
                    return P()
                """,
            )

            plugins = load_plugins(PluginContext(defaults={}), root)
            self.assertEqual([plugin.name for plugin in plugins], ["omega", "alpha", "zeta"])

    def test_skips_invalid_plugins_and_duplicate_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _write(
                root / "a_dup.py",
                """
                class P:
                    name = "dup"
                    priority = 10
                    source = "a"

                    def can_handle(self, page):
                        return False

                    def execute(self, page):
                        return True


                def create_plugin(ctx):
                    return P()
                """,
            )
            _write(
                root / "z_dup.py",
                """
                class P:
                    name = "dup"
                    priority = 10
                    source = "z"

                    def can_handle(self, page):
                        return False

                    def execute(self, page):
                        return True


                def create_plugin(ctx):
                    return P()
                """,
            )
            _write(
                root / "no_factory.py",
                """
                VALUE = 1
                """,
            )
            _write(
                root / "broken_import.py",
                """
                raise RuntimeError("boom")
                """,
            )
            _write(
                root / "bad_contract.py",
                """
                class Broken:
                    name = "broken"
                    priority = 1

                    def can_handle(self, page):
                        return False


                def create_plugin(ctx):
                    return Broken()
                """,
            )

            buf = io.StringIO()
            with redirect_stdout(buf):
                plugins = load_plugins(PluginContext(defaults={}), root)

            self.assertEqual(len(plugins), 1)
            self.assertEqual(plugins[0].name, "dup")
            self.assertEqual(getattr(plugins[0], "source", ""), "a")

            warnings = buf.getvalue().lower()
            self.assertIn("missing create_plugin", warnings)
            self.assertIn("import failed", warnings)
            self.assertIn("duplicate plugin name", warnings)

    def test_custom_plugin_auto_connects_to_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _write(
                root / "my_custom.py",
                """
                class P:
                    name = "my_custom"
                    priority = 42

                    def can_handle(self, page):
                        return True

                    def execute(self, page):
                        return True


                def create_plugin(ctx):
                    return P()
                """,
            )

            registry = build_registry_from_plugins(PluginContext(defaults={}), plugins_dir=str(root))
            resolved = registry.resolve(page=object())

            self.assertEqual(resolved.name, "my_custom")


if __name__ == "__main__":
    unittest.main()
