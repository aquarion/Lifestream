"""
Historic Tumblr reblog importer for Lifestream.

Finds Tumblr posts that were originally posted ten years ago (in a rolling
15-minute window) and reblogs them onto a dedicated "on this day" blog,
queued to go out at the same time of day ten years later.
"""

import json
from datetime import UTC, datetime, timedelta

from dateutil.relativedelta import relativedelta

from lifestream.importers.base import OAuthImporter
from lifestream.importers.tumblr import authenticate

TEN_YEARS = relativedelta(years=10)
WINDOW = timedelta(minutes=15)
TO_BLOG = "aquarions-of-history"

SELECT_SQL = (
    "select title, date_created, url, fulldata_json, systemid, source, type "
    "from lifestream where source = 'tumblr' and date_created between %s and %s"
)


class HistoricImporter(OAuthImporter):
    """Reblog Tumblr posts from ten years ago onto a dedicated blog."""

    name = "historic"
    description = "Reblog Tumblr posts from ten years ago"
    config_section = "tumblr"

    def validate_config(self) -> bool:
        """Ensure Tumblr credentials are configured."""
        missing = [
            k
            for k in ("consumer_key", "secret_key", "secrets_file")
            if not self.get_config(k)
        ]
        if missing:
            self.logger.error(f"Missing Tumblr config keys: {', '.join(missing)}")
            return False
        return True

    def get_oauth_path(self) -> str:
        """Historic reblogs share the [tumblr] OAuth token file."""
        return self.get_config("secrets_file")

    def run(self) -> None:
        """Reblog posts from exactly ten years ago in this run's window."""
        now = datetime.now(UTC)
        date_from = now - TEN_YEARS
        date_to = date_from + WINDOW

        with self.entry_store.dbcxn.cursor() as cursor:
            cursor.execute(SELECT_SQL, (date_from.isoformat(), date_to.isoformat()))
            rows = cursor.fetchall()

        if not rows:
            self.logger.info("Nothing posted in this window ten years ago")
            return

        tumblr = authenticate(self)

        for row in rows:
            title, date_created, url, fulldata_json, systemid, source, contenttype = row

            if not title:
                self.logger.info("Skipping, no content")
                continue

            if not fulldata_json:
                self.logger.info("Skipping %s, no fulldata", title)
                continue

            data = json.loads(fulldata_json)

            self.logger.info(
                "Reblogging %r from %s", title.replace("@", "💬"), date_created
            )

            tumblr.reblog(
                TO_BLOG,
                id=systemid,
                reblog_key=data["reblog_key"],
                state="queue",
                date=date_created + TEN_YEARS,
            )


def main():
    """Entry point for CLI."""
    return HistoricImporter.main()


if __name__ == "__main__":
    exit(main())
