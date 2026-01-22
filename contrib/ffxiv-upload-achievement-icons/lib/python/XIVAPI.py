"""XIVAPI Client Module."""

import logging
import sys

import requests

logger = logging.getLogger("XIVAPI")


class XIVClient:
    """Client for interacting with XIVAPI."""

    def __init__(self, api_key):
        self.api_key = api_key

    def set_log_level(self, level):
        """Set the logging level for the module."""
        logger.setLevel(level)

        # Ensure the logger propagates to parent loggers (inherits handlers)
        logger.propagate = True

        # If the logger doesn't have handlers, add a basic handler
        if not logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        if isinstance(level, int):
            level = logging.getLevelName(level)
        logger.debug("XIVAPI log level set to %s", level)

    def _call(self, url, limit=1000, page=1):
        """Make a call to the XIVAPI."""
        url_base = "https://xivapi.com"
        params = {"private_key": self.api_key}
        if limit:
            params["limit"] = limit
        if page > 1:
            params["page"] = page

        response = requests.get(url_base + url, params=params, timeout=10)
        return response.json()

    def get_achievement(self, identifier):
        """Get a specific achievement by identifier."""
        url = f"/achievement/{identifier}"
        return self._call(url)

    def list_achievements(self):
        """List all achievements from the API."""
        logger.info("Getting achievements")
        url = "/achievement"
        achievements = []
        this_page = self._call(url)
        achievements += this_page["Results"]
        while this_page["Pagination"]["PageNext"]:
            logger.debug(
                "Getting page %s/%s of achievements",
                this_page["Pagination"]["PageNext"],
                this_page["Pagination"]["PageTotal"],
            )
            this_page = self._call(url, page=this_page["Pagination"]["PageNext"])
            achievements += this_page["Results"]
            logger.debug("Next page is %s", this_page["Pagination"]["PageNext"])

        return achievements
