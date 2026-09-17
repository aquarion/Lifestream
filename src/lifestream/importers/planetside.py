"""Planetside 2 importer for Lifestream, via Daybreak Games' Census API."""

import hashlib
from datetime import datetime

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

    def _api_base(self) -> str:
        service_key = self.get_config("service_key")
        api_key = f"s:{service_key}" if service_key else ""
        return f"{CENSUS_BASE}/{api_key}/get/ps2:v2"

    def _import_rank(self, api_base: str, character_name: str) -> str:
        """Log the character's current battle rank, returning its character_id."""
        response = requests.get(
            f"{api_base}/character/",
            params={"name.first_lower": character_name, "c:resolve": "faction"},
            timeout=30,
        )
        response.raise_for_status()
        profile = response.json()["character_list"][0]

        character_id = profile["character_id"]
        battle_rank = profile["battle_rank"]
        faction = profile["faction"]["code_tag"].lower()
        name = profile["name"]["first"]

        rank_response = requests.get(
            f"{api_base}/experience_rank",
            params={"rank": battle_rank["value"]},
            timeout=30,
        )
        rank_response.raise_for_status()
        rank_info = rank_response.json()["experience_rank_list"][0]

        rank = rank_info[faction]["title"]["en"]
        text = f"In Planetside 2, {name} achieved the rank {rank}"
        image = CENSUS_BASE + rank_info[f"{faction}_image_path"]

        self.logger.info(text)
        self.entry_store.add_entry(
            "gaming",
            hashlib.md5(text.encode()).hexdigest(),
            text,
            "Planetside 2",
            datetime.now(),
            url=f"https://players.planetside2.com/#!/{character_id}",
            image=image,
            fulldata_json=profile,
        )
        return character_id

    def _import_achievements(
        self, api_base: str, character_id: str, character_name: str
    ) -> None:
        """Log every finished achievement for one character."""
        response = requests.get(
            f"{api_base}/characters_achievement/",
            params={
                "character_id": character_id,
                "c:join": "achievement",
                "c:limit": 100,
            },
            timeout=30,
        )
        response.raise_for_status()
        url = f"https://players.planetside2.com/#!/{character_id}"

        for achievement in response.json()["characters_achievement_list"]:
            if achievement["finish"] == "0":
                continue

            info = achievement["achievement_id_join_achievement"]
            name = info["name"]["en"]
            text = f"{character_name} earnt {name}"
            date = achievement["finish_date"]
            image = CENSUS_BASE + info["image_path"]

            self.logger.info(text)
            self.entry_store.add_entry(
                "gaming",
                hashlib.md5(f"{text}{date}".encode()).hexdigest(),
                text,
                "PS2 Achivement",
                date,
                url=url,
                image=image,
                fulldata_json=achievement,
            )

    def run(self) -> None:
        """Log rank and achievements for each configured character."""
        characters = self.get_config("characters").split(",")
        api_base = self._api_base()

        try:
            for character_name in characters:
                self.logger.info("Data for %s", character_name)
                character_id = self._import_rank(api_base, character_name)
                self._import_achievements(api_base, character_id, character_name)
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
