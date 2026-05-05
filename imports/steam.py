import hashlib
import logging
from datetime import datetime

import pytz
import requests

# Local
import lifestream
from lifestream.db import EntryStore
from lifestream.steam_api import SteamAPI

logger = logging.getLogger("Steam")


lifestream.arguments.add_argument(
    "--catchup",
    required=False,
    help="Get all achievements, not just last fortnight",
    default=False,
    action="store_true",
)


args = lifestream.parse_args()

entry_store = EntryStore()

STEAMTIME = pytz.timezone("US/Pacific")

USER = lifestream.config.get("steam", "username")


def process_achievement(appid, name, player_achievement, game_achievements):
    ach_id = player_achievement["apiname"]
    game_achievement = game_achievements.get(ach_id, {})
    ach_name = game_achievement.get("displayName", "Unknown Achievement")
    message = "%s &ndash; %s" % (name, ach_name)
    achieved_date = datetime.fromtimestamp(player_achievement["unlocktime"])
    openImage = game_achievement.get("icon", None)

    logger.info(message)

    id = hashlib.md5()
    id.update(f"{appid}-{ach_id}".encode("utf-8"))

    entry = entry_store.get_by_title("achievement", message)
    if entry and not entry["systemid"] == id.hexdigest():
        logger.info("           + Achievement already in Lifestream, deleting.")
        logger.info(f"             + Entry ID: {entry['title']}")
        entry_store.delete_entry(entry["type"], entry["systemid"])
    else:
        logger.info("           + Adding Achievement to entry_store.")

    statsPage = f"https://steamcommunity.com/id/{USER}/stats/{appid}/?tab=achievements"
    entry_store.add_entry(
        "achievement",
        id.hexdigest(),
        message,
        "steam",
        achieved_date,
        url=statsPage,
        image=openImage,
    )


def process_game(steam_cxn, game):
    appid = game["appid"]
    name = game["name"]
    playtime_2weeks = game.get("playtime_2weeks", 0)
    playtime_forever = game["playtime_forever"]
    logger.info(
        f"Played {name}: {playtime_2weeks} mins in last 2 weeks, {playtime_forever} mins total."
    )

    try:
        player_achievements = steam_cxn.get_player_achievements(appid)
    except requests.HTTPError as e:
        logger.warning(f"Error fetching achievements for {name} ({appid}): {e}")
        return

    unsorted = steam_cxn.get_game_achievements(appid)
    stats = unsorted["game"].get("availableGameStats", {})
    if "achievements" not in stats:
        logger.info(f"   + No achievements found for {name} ({appid}).")
        return

    game_achievements = {a["name"]: a for a in stats["achievements"]}

    for player_achievement in player_achievements.get("playerstats", {}).get(
        "achievements", []
    ):
        if player_achievement["achieved"] == 1:
            process_achievement(appid, name, player_achievement, game_achievements)


def main():
    steam_cxn = SteamAPI()
    if args.catchup:
        logger.info("CATCHUP MODE: Fetching all achievements.")
        games = steam_cxn.get_owned_games(include_appinfo=True)
    else:
        logger.info("NORMAL MODE: Fetching only recent achievements.")
        games = steam_cxn.get_recently_played_games(count=10)

    logger.info(
        f"Found {len(games['response'].get('games', []))} games to check for achievements."
    )

    for game in games["response"]["games"]:
        process_game(steam_cxn, game)


if __name__ == "__main__":
    main()
