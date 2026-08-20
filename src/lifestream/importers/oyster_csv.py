"""Oyster card CSV importer for Lifestream."""

import argparse
import csv
import hashlib
from datetime import datetime

import pytz

from lifestream.importers.base import BaseImporter

LONDON_TZ = pytz.timezone("Europe/London")


class OysterCsvImporter(BaseImporter):
    """Import Oyster card journey history from a downloaded CSV file."""

    name = "oyster_csv"
    description = "Import Oyster card journey history from a CSV file"
    config_section = "oyster"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add the CSV filename argument."""
        parser.add_argument("filename", help="Path to the Oyster CSV export")

    def run(self) -> None:
        """Parse the CSV and add a journey entry per row."""
        with open(self.args.filename, newline="") as data:
            rows = list(csv.reader(data))

        if not rows:
            self.logger.info("No rows found in %s", self.args.filename)
            return

        for row in rows[1:]:
            if not row:
                continue

            date, time_from, time_to, action = row[0], row[1], row[2], row[3]

            if not time_from and time_to:
                time_from = time_to
            elif not time_from:
                time_from = "00:00"

            timestamp = datetime.strptime(f"{date} {time_from}", "%d-%b-%Y %H:%M")
            loc_date = LONDON_TZ.localize(timestamp)
            utcdate = loc_date.astimezone(pytz.utc).strftime("%Y-%m-%d %H:%M")

            id_hash = hashlib.md5()
            id_hash.update(utcdate.encode("utf-8"))
            id_hash.update(action.encode("utf-8"))

            self.logger.info("%s: %s", action, utcdate)
            self.entry_store.add_entry(
                "oyster",
                id_hash.hexdigest(),
                action,
                "oyster",
                utcdate,
                fulldata_json=row,
            )


def main():
    """Entry point for CLI."""
    return OysterCsvImporter.main()


if __name__ == "__main__":
    exit(main())
