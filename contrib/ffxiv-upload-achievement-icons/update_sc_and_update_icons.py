#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Update the local FFXIV icon cache, then upload achievement icons.

Python replacement for ``update_sc_and_update_icons.ps1``. Instead of
downloading and running ``SaintCoinach.Cmd.exe``, it uses the ``saintcoinach``
Python library to export icons directly from the game installation, so the
whole workflow is cross-platform and needs no .NET runtime.

Steps:

1. Read ``ffxiv_config.ini``.
2. Build/refresh the achievement database and collect the icon IDs it uses.
3. Export just those icons (standard + ``hr1``) into
   ``<icon_directory>/<game_version>/ui/icon/...``.
4. Prune older ``<game_version>`` icon caches, keeping the current one.
5. Upload the icons via ``update_achievement_images.upload_icons``, reusing
   the same database connection instead of re-running that module as a
   separate process.
"""

import argparse
import configparser
import logging
import os
import re
import shutil
import site

basedir = os.path.dirname(os.path.abspath(__file__))
site.addsitedir(os.path.join(basedir, "lib", "python"))

# pylint: disable=wrong-import-position
import update_achievement_images as uploader  # noqa: E402
from icon_export import IconExporter  # noqa: E402
from SaintCoinach import SaintCoinach  # noqa: E402

# pylint: enable=wrong-import-position

logger = logging.getLogger("update_sc_and_update_icons")
logger.propagate = True

CONFIG_FILE = os.path.join(basedir, "ffxiv_config.ini")
VERSION_DIR_RE = re.compile(r"^\d{4}\.\d{2}\.\d{2}\.\d{4}\.\d{4}$")


def load_config():
    """Load ffxiv_config.ini and validate the keys this script needs."""
    config = configparser.ConfigParser()
    if not config.read(CONFIG_FILE):
        raise SystemExit(f"Config file not found: {CONFIG_FILE}")

    required = [
        ("local", "ffxiv_installation"),
        ("local", "icon_directory"),
        ("local", "data_directory"),
    ]
    for section, key in required:
        if not config.has_option(section, key):
            raise SystemExit(f"Missing required config key: {section}.{key}")

    ffxiv_installation = config.get("local", "ffxiv_installation")
    if not os.path.isdir(ffxiv_installation):
        raise SystemExit(
            f"FFXIV installation path does not exist: {ffxiv_installation}"
        )

    return config


def build_client(config):
    """Create a SaintCoinach client with a freshly-refreshed achievement database."""
    data_dir = config.get("local", "data_directory")
    os.makedirs(data_dir, exist_ok=True)

    database_path = os.path.join(data_dir, "saintcoinach_achievements.db")
    schema_file_path = os.path.join(basedir, "etc", "achievements_schema.sql")

    client = SaintCoinach(database_path, config)
    client.set_log_level(logger.level)
    client.update_achievement_database(schema_file_path=schema_file_path)
    return client


def collect_icon_ids(client):
    """Return the set of icon IDs used by achievements in the database."""
    icon_ids = []
    for achievement in client.list_achievements():
        icon = achievement["Icon"]
        if icon:
            icon_ids.append(icon)
    logger.info("Found %d achievement icons to export", len(icon_ids))
    return icon_ids


def prune_old_versions(icon_directory, keep_version):
    """Delete ``<icon_directory>/<version>`` caches other than ``keep_version``."""
    if not os.path.isdir(icon_directory):
        return
    for entry in os.listdir(icon_directory):
        path = os.path.join(icon_directory, entry)
        if not os.path.isdir(path):
            continue
        if not VERSION_DIR_RE.match(entry):
            continue
        if entry == keep_version:
            continue
        logger.info("Deleting old icon cache: %s", path)
        shutil.rmtree(path, ignore_errors=True)


def export_icons(config, icon_ids, use_tqdm):
    """Export the requested icons from the game installation."""
    ffxiv_installation = config.get("local", "ffxiv_installation")
    icon_directory = config.get("local", "icon_directory")

    with IconExporter(ffxiv_installation, icon_directory) as exporter:
        progress = None
        if use_tqdm:
            try:
                from tqdm import tqdm

                progress = tqdm(total=len(icon_ids), desc="Icons", unit=" icon")
            except ImportError:
                progress = None

        written = exporter.export_icons(icon_ids, progress=progress)

        if progress is not None:
            progress.close()

        prune_old_versions(icon_directory, exporter.game_version)

    print(f"Exported {written} icon files")


def main():
    """Entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument(
        "--disable-tqdm", action="store_true", help="Disable progress bars"
    )
    parser.add_argument(
        "--skip-export",
        action="store_true",
        help="Skip icon export and only run the uploader",
    )
    parser.add_argument(
        "--skip-upload",
        action="store_true",
        help="Export icons but do not run the uploader",
    )
    args = parser.parse_args()

    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    logger.addHandler(handler)
    if args.debug:
        logger.setLevel(logging.DEBUG)
    elif args.verbose:
        logger.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.WARNING)

    config = load_config()
    client = build_client(config)

    if not args.skip_export:
        icon_ids = collect_icon_ids(client)
        export_icons(config, icon_ids, use_tqdm=not args.disable_tqdm)

    if not args.skip_upload:
        uploader.configure_logging(args.debug, args.verbose)
        upload_count = uploader.upload_icons(
            config, client, use_tqdm=not args.disable_tqdm
        )
        print(f"Uploaded {upload_count} icons")


if __name__ == "__main__":
    main()
