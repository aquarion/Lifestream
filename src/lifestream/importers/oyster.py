"""Oyster card journey history importer for Lifestream.

Scrapes the TfL Oyster website with ``mechanize`` (not a project
dependency — install it separately if you need to run this importer).
"""

import argparse
import csv
import hashlib
import io
import re
from datetime import datetime
from time import sleep

import pytz

from lifestream.importers.base import BaseImporter

LONDON_TZ = pytz.timezone("Europe/London")


class OysterImporter(BaseImporter):
    """Log in to the TfL Oyster website and import journey history."""

    name = "oyster"
    description = "Import Oyster card journey history by scraping the TfL website"
    config_section = "oyster"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add the card type and number arguments."""
        parser.add_argument("card_type", help="Oyster card class")
        parser.add_argument("card_number", help="Oyster card number")

    def validate_config(self) -> bool:
        """Ensure Oyster credentials are configured."""
        missing = [k for k in ("username", "password") if not self.get_config(k)]
        if missing:
            self.logger.error(f"Missing Oyster config keys: {', '.join(missing)}")
            return False
        return True

    def _fetch_journey_csv(self, browser) -> str:
        browser.open("https://oyster.tfl.gov.uk/oyster/entry.do")

        browser.select_form(name="sign-in")
        browser["j_password"] = self.get_config("password")
        browser["j_username"] = self.get_config("username")
        browser.submit()

        browser.select_form(nr=0)
        browser["cardId"] = [self.args.card_number]
        browser.submit()

        link = browser.find_link(text="Journey history")
        browser.follow_link(link)

        sleep(10)

        html = browser.response().read().decode("utf-8")
        codes = re.findall(r'/oyster/journeyDetailsPrint\.do\?_qv=(.*?)"', html)

        browser.open(f"/oyster/journeyDetailsPrint.do?_qv={codes[1]}")

        return browser.response().read().decode("utf-8")

    def run(self) -> None:
        """Scrape and store new journeys from the Oyster website."""
        from mechanize import Browser, RobustFactory

        browser = Browser(factory=RobustFactory())
        browser.set_handle_robots(False)

        data = self._fetch_journey_csv(browser)

        rows = list(csv.reader(io.StringIO(data)))
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

            self.logger.info(action)
            self.entry_store.add_entry(
                "oyster", id_hash.hexdigest(), action, "oyster", utcdate
            )


def main():
    """Entry point for CLI."""
    return OysterImporter.main()


if __name__ == "__main__":
    exit(main())
