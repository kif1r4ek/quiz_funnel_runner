from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from screenshotter import Screenshotter


class _FakePage:
    def screenshot(self, path: str, full_page: bool = True) -> None:  # noqa: ARG002
        Path(path).write_bytes(b"png")


class ScreenshotterTests(unittest.TestCase):
    def test_funnel_key_drops_query_and_normalizes(self) -> None:
        screenshotter = Screenshotter("results")
        key = screenshotter.funnel_key("https://coursiv.io/dynamic?prc_id=1069")
        self.assertEqual(key, "coursiv.io-dynamic")

    def test_save_step_naming_and_classified_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            screenshotter = Screenshotter(tmp_dir)
            page = _FakePage()

            funnel_key = screenshotter.funnel_key("https://quiz.fitme.expert/intro-111")
            filename = screenshotter.save_step(page, funnel_key, 3, "input")

            self.assertEqual(filename, "03_input.png")

            funnel_file = Path(tmp_dir) / funnel_key / "03_input.png"
            classified_file = (
                Path(tmp_dir)
                / "_classified"
                / "input"
                / f"{funnel_key}_03_input.png"
            )
            self.assertTrue(funnel_file.exists())
            self.assertTrue(classified_file.exists())


if __name__ == "__main__":
    unittest.main()
