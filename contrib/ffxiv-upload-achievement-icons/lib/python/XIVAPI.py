"""XIVAPI Client Module."""

import logging

import requests

logger = logging.getLogger(__name__)


class XIVClient:
    """Client for interacting with XIVAPI."""

    def __init__(self, api_key):
        self.api_key = api_key

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
