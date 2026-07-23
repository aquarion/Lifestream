"""Tests for the icon_export module.

The ``saintcoinach`` game data access is mocked, so these run without a game
installation or Pillow: they check the on-disk path layout and the standard +
hr1 export behaviour that the uploader depends on.
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# Add lib/python to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib", "python"))

# pylint: disable=wrong-import-position,import-error
import icon_export  # noqa: E402

# pylint: enable=wrong-import-position,import-error


class TestIconExporter(unittest.TestCase):
    """Test cases for the IconExporter class."""

    def setUp(self):
        """Create a temp icon directory and a mocked game installation."""
        self.tmp = tempfile.TemporaryDirectory()
        self.icon_directory = self.tmp.name
        self.game_version = "2024.08.21.0000.0000"

        # Patch GameData so no real install is needed.
        patcher = patch.object(icon_export, "GameData")
        self.addCleanup(patcher.stop)
        self.mock_game_data = patcher.start()

        self.game = MagicMock()
        self.game.game_version = self.game_version
        self.mock_game_data.return_value = self.game

    def tearDown(self):
        self.tmp.cleanup()

    def _fake_image_file(self):
        """A stand-in ImageFile whose get_image().save() writes a marker file."""
        image_file = MagicMock()

        def save(path):
            with open(path, "wb") as handle:
                handle.write(b"PNG")

        image_file.get_image.return_value.save.side_effect = save
        return image_file

    def test_output_root_uses_game_version(self):
        exporter = icon_export.IconExporter("/fake/install", self.icon_directory)
        self.assertEqual(
            exporter.output_root,
            os.path.join(self.icon_directory, self.game_version),
        )

    def test_export_icon_writes_standard_and_hr1(self):
        self.game.packs.try_get_file.return_value = self._fake_image_file()

        exporter = icon_export.IconExporter("/fake/install", self.icon_directory)
        count = exporter.export_icon(123456)

        self.assertEqual(count, 2)
        base = os.path.join(
            self.icon_directory, self.game_version, "ui", "icon", "123000"
        )
        self.assertTrue(os.path.isfile(os.path.join(base, "123456.png")))
        self.assertTrue(os.path.isfile(os.path.join(base, "123456_hr1.png")))

        # It requested exactly the expected SqPack paths.
        requested = {
            call.args[0] for call in self.game.packs.try_get_file.call_args_list
        }
        self.assertEqual(
            requested,
            {"ui/icon/123000/123456.tex", "ui/icon/123000/123456_hr1.tex"},
        )

    def test_missing_icon_is_skipped(self):
        self.game.packs.try_get_file.return_value = None

        exporter = icon_export.IconExporter("/fake/install", self.icon_directory)
        count = exporter.export_icon(999999)

        self.assertEqual(count, 0)

    def test_export_icons_dedupes_and_ignores_invalid(self):
        self.game.packs.try_get_file.return_value = self._fake_image_file()

        exporter = icon_export.IconExporter("/fake/install", self.icon_directory)
        # Duplicate 100, an invalid entry, a zero, and a valid distinct one.
        count = exporter.export_icons([100, 100, "nope", 0, 200])

        # Two distinct valid ids, two files each.
        self.assertEqual(count, 4)

    def test_folder_bucketing(self):
        self.game.packs.try_get_file.return_value = self._fake_image_file()

        exporter = icon_export.IconExporter("/fake/install", self.icon_directory)
        exporter.export_icon(61234)

        # 61234 -> bucket floor(61234/1000)*1000 = 61000
        base = os.path.join(
            self.icon_directory, self.game_version, "ui", "icon", "061000"
        )
        self.assertTrue(os.path.isfile(os.path.join(base, "061234.png")))


if __name__ == "__main__":
    unittest.main()
