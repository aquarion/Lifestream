"""Export FFXIV UI icons to PNG using the ``saintcoinach`` Python library.

This replaces the previous workflow that downloaded and ran
``SaintCoinach.Cmd.exe`` to export *every* UI icon. Only the icons requested
(by numeric ID) are exported here, in both the standard and high-resolution
(``hr1``) variants, into the on-disk layout the uploader expects::

    <icon_directory>/<game_version>/ui/icon/<folder>/<file>.png
    <icon_directory>/<game_version>/ui/icon/<folder>/<file>_hr1.png

``<game_version>`` comes from the game's ``ffxivgame.ver`` (e.g.
``2024.08.21.0000.0000``), matching the directory naming the original
SaintCoinach.Cmd used and that :meth:`SaintCoinach.find_icons_path` looks for.
"""

import logging
import os

from saintcoinach import GameData, Language

logger = logging.getLogger("icon_export")
logger.propagate = True


class IconExporter:
    """Export selected UI icons straight from a game installation."""

    def __init__(self, ffxiv_installation, icon_directory, language=Language.ENGLISH):
        self.game = GameData(ffxiv_installation, language)
        self.icon_directory = icon_directory
        self.game_version = self.game.game_version or "unknown"
        self.output_root = os.path.join(icon_directory, self.game_version)
        logger.info(
            "Exporting icons for game version %s into %s",
            self.game_version,
            self.output_root,
        )

    def export_icon(self, icon_id):
        """Export the standard and ``hr1`` variants of a single icon.

        Returns the number of image files written (0-2). Missing variants are
        skipped silently -- not every icon has a high-resolution version, and
        some IDs referenced by data may not exist as textures.
        """
        icon_id = int(icon_id)
        folder = f"{(icon_id // 1000) * 1000:06d}"
        name = f"{icon_id:06d}"

        exported = 0
        for suffix in ("", "_hr1"):
            sqpack_path = f"ui/icon/{folder}/{name}{suffix}.tex"
            dest = os.path.join(
                self.output_root, "ui", "icon", folder, f"{name}{suffix}.png"
            )

            # Already exported for this game version -- icons don't change
            # within a version, so a fresh version always lands in a new dir.
            if os.path.isfile(dest):
                exported += 1
                continue

            image_file = self.game.packs.try_get_file(sqpack_path)
            if image_file is None or not hasattr(image_file, "get_image"):
                continue

            os.makedirs(os.path.dirname(dest), exist_ok=True)
            try:
                image_file.get_image().save(dest)
                exported += 1
            except Exception as exc:  # noqa: BLE001 - tolerate per-icon failures
                logger.warning("Failed to export icon %s: %s", sqpack_path, exc)

        return exported

    def export_icons(self, icon_ids, progress=None):
        """Export a collection of icon IDs. Returns the number of files written."""
        total = 0
        seen = set()
        for icon_id in icon_ids:
            try:
                numeric = int(icon_id)
            except (TypeError, ValueError):
                continue
            if numeric <= 0 or numeric in seen:
                if progress is not None:
                    progress.update(1)
                continue
            seen.add(numeric)
            total += self.export_icon(numeric)
            if progress is not None:
                progress.update(1)
        return total

    def close(self):
        """Release the game installation's open file handles."""
        self.game.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
