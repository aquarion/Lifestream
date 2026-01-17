"""Module for interacting with SaintCoinach achievement database."""

import csv
import io
import logging
import math
import os
import re
import sqlite3
import sys
from glob import iglob

import requests

logger = logging.getLogger(__name__)


class SaintCoinach:
    """Interface for working with SaintCoinach achievement database."""

    db_connection = False
    config = None

    def __init__(self, dbpath, config):
        self.db_connection = sqlite3.connect(dbpath)
        self.db_connection.row_factory = sqlite3.Row  # add this row
        self.config = config

    def count_achievements(self):
        """Count the number of achievements in the database."""
        cursor = self.db_connection.cursor()
        result = cursor.execute("SELECT COUNT(*) FROM achievements")
        return result.fetchone()[0]

    def list_achievements(self):
        """List all achievements in the database."""
        cursor = self.db_connection.cursor()
        result = cursor.execute("SELECT * FROM achievements")
        return result

    def get_achievement(self, achievement_id):
        """Get a specific achievement by ID."""
        cursor = self.db_connection.cursor()
        result = cursor.execute(
            "SELECT * FROM achievements WHERE ID = ?", (achievement_id,)
        )
        record = result.fetchone()
        return record

    def icon_path(self, icon_id):
        """Get the icon path for a given icon ID."""
        icon_id = int(icon_id)
        filename = f"{icon_id:06d}"
        foldername = f"{math.floor(icon_id / 1000) * 1000:06d}"
        return f"{foldername}/{filename}.png"

    def icon_image(self, icon_id):
        """Get the icon image filename for a given icon ID, preferring high quality."""
        local_icons_base = self.config.get("local", "icon_directory")
        local_icons = self.find_icons_path(local_icons_base)

        icon_id = int(icon_id)
        filename = f"{icon_id:06d}"
        foldername = f"{math.floor(icon_id / 1000) * 1000:06d}"
        low_quality = f"{foldername}/{filename}.png"
        high_quality = f"{foldername}/{filename}_hr1.png"
        if os.path.isfile(f"{local_icons}/{high_quality}"):
            return high_quality
        return low_quality

    def find_icons_path(self, icon_local_base):
        """Find the path to the icon directory in the local Saint Coinach data."""
        if not os.path.isdir(icon_local_base):
            raise IOError(f"Unable to find icon location {icon_local_base}")

        dirs = []
        for icon_location in iglob(f"{icon_local_base}/*"):
            if os.path.isdir(icon_location):
                dirname = os.path.basename(icon_location)
                # 0000.00.00.0000.0000
                if re.match(r"^\d{4}\.\d{2}\.\d{2}\.\d{4}\.\d{4}$", dirname):
                    dirs.append(icon_location)
        if not dirs:
            raise IOError(
                f"Unable to find icon directory {icon_local_base}/XXXX.XX.XX.0000.0000"
            )
        icon_directory_path = sorted(dirs).pop() + "/ui/icon"
        # logger.info("Using icon directory %s", icon_directory_path)
        return icon_directory_path

    def update_achievement_database(self, schema_file_path=None):
        """Update the achievement database from the remote CSV file."""

        url = "https://github.com/xivapi/ffxiv-datamining/raw/master/csv/en/Achievement.csv"
        logger.info("Updating achievement database from %s", url)
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            logger.error(
                "Unable to download achievement database from %s: %s",
                url,
                response.status_code,
            )
            sys.exit(1)

        conn = self.db_connection
        cur = conn.cursor()

        cur.execute("DROP TABLE IF EXISTS achievements")

        basedir = os.path.abspath(os.path.dirname(__file__))

        if schema_file_path is None:
            schema_file_path = os.path.join(
                basedir, "schemas", "saintcoinach_achievements.sql"
            )

        with open(schema_file_path, "r", encoding="utf-8") as schema_file:
            schema_sql = schema_file.read()

        conn.executescript(schema_sql)
        cur = conn.cursor()

        csvfile = io.StringIO(response.text)
        reader = csv.reader(csvfile)

        for row in range(0, 3):
            skipped_row = next(reader)
            logger.debug("Skipping row %d: %s", row, skipped_row)

        logger.info("Inserting achievements into database")

        for row in reader:
            cur.execute(
                f'INSERT INTO achievements VALUES ({",".join(["?"]*len(row))})', row
            )
        conn.commit()
        logger.info("Achievement database update complete")