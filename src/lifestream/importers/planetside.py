"""Planetside 2 importer for Lifestream, via Daybreak Games' Census API."""

import hashlib
from datetime import UTC, datetime

import requests

from lifestream.core import check_and_set_backoff, niceTimeDelta
from lifestream.importers.base import BaseImporter

CENSUS_BASE = "https://census.daybreakgames.com"

WARNING_BACKOFF_KEY = "planetside:api_error:warning_sent"


class PlanetsideImporter(BaseImporter):
    """Import Planetside 2 character rank and achievements from Daybreak's Census API."""

    name = "planetside"
    description = "Import Planetside 2 character rank and achievements"
    config_section = "planetside"

    def validate_config(self) -> bool:
        """Ensure at least one Planetside 2 character is configured."""
        self.require_config("characters")
        return True

    def _census_get(self, path: str, params: dict) -> dict:
        """GET a Census API endpoint, adding the configured service key if any."""
        service_key = self.get_config("service_key")
        api_key = f"s:{service_key}" if service_key else ""
        response = requests.get(
            f"{CENSUS_BASE}/{api_key}/get/ps2:v2/{path}",
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def _import_rank(self, character_name: str) -> tuple[str, str]:
        """Log the character's current battle rank, returning (character_id,
        canonical_name) - the API's own capitalization of the name, which may
        differ from how it's spelled in config and must be used consistently
        so achievement entries hash/match the same way the legacy importer's
        did."""
        profile = self._census_get(
            "character/",
            {"name.first_lower": character_name, "c:resolve": "faction"},
        )["character_list"][0]

        character_id = profile["character_id"]
        battle_rank = profile["battle_rank"]
        faction = profile["faction"]["code_tag"].lower()
        name = profile["name"]["first"]

        rank_info = self._census_get("experience_rank", {"rank": battle_rank["value"]})[
            "experience_rank_list"
        ][0]

        rank = rank_info[faction]["title"]["en"]
        text = f"In Planetside 2, {name} achieved the rank {rank}"
        image = CENSUS_BASE + rank_info[f"{faction}_image_path"]

        # text is rank/name data from the API response, not the service key -
        # but CodeQL's requests model treats a response as tainted by the URL
        # that fetched it, which embeds the key (Census has no other way to
        # take it). False positives on both lines below.
        self.logger.info(text)  # codeql[py/clear-text-logging-sensitive-data]
        digest = hashlib.md5(text.encode())  # codeql[py/weak-sensitive-data-hashing]
        self.entry_store.add_entry(
            "gaming",
            digest.hexdigest(),
            text,
            "Planetside 2",
            datetime.now(),
            url=f"https://players.planetside2.com/#!/{character_id}",
            image=image,
            fulldata_json=profile,
        )
        return character_id, name

    def _log_achievement(
        self, achievement: dict, character_name: str, url: str
    ) -> None:
        """Log one finished achievement as an entry."""
        info = achievement["achievement_id_join_achievement"]
        name = info["name"]["en"]
        text = f"{character_name} earnt {name}"
        finish_date = achievement["finish_date"]
        date = datetime.fromtimestamp(int(finish_date), tz=UTC)
        image = CENSUS_BASE + info["image_path"]
        raw = f"{text}{finish_date}"

        # Same false positive as _import_rank: text/raw hold achievement and
        # character data, not the service key.
        self.logger.info(text)  # codeql[py/clear-text-logging-sensitive-data]
        digest = hashlib.md5(raw.encode())  # codeql[py/weak-sensitive-data-hashing]
        self.entry_store.add_entry(
            "gaming",
            digest.hexdigest(),
            text,
            "PS2 Achievement",
            date,
            url=url,
            image=image,
            fulldata_json=achievement,
        )

    def _import_achievements(self, character_id: str, character_name: str) -> None:
        """Log every finished achievement for one character."""
        achievements = self._census_get(
            "characters_achievement/",
            {
                "character_id": character_id,
                "c:join": "achievement",
                "c:limit": 100,
            },
        )["characters_achievement_list"]
        url = f"https://players.planetside2.com/#!/{character_id}"

        for achievement in achievements:
            if achievement["finish"] == "0":
                continue
            self._log_achievement(achievement, character_name, url)

    def run(self) -> None:
        """Log rank and achievements for each configured character."""
        characters = self.get_config("characters").split(",")

        try:
            for character_name in characters:
                self.logger.info("Data for %s", character_name)
                character_id, canonical_name = self._import_rank(character_name)
                self._import_achievements(character_id, canonical_name)
        except Exception as e:
            ttl = check_and_set_backoff(WARNING_BACKOFF_KEY)
            if ttl:
                self.logger.info(
                    "Error fetching achievements: %s (already warned %s ago)",
                    e,
                    niceTimeDelta(ttl),
                )
            else:
                self.logger.error("Error fetching achievements: %s", e)
            raise


def main():
    """Entry point for CLI."""
    return PlanetsideImporter.main()


if __name__ == "__main__":
    exit(main())
