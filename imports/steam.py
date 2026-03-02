#!/usr/bin/python

import hashlib
import logging
from datetime import datetime

import pytz
import requests

# Local
import lifestream
from lifestream.steam_api import SteamAPI


logger = logging.getLogger("Steam")


lifestream.arguments.add_argument(
    "--catchup",
    required=False,
    help="Get all achievements, not just last fortnight",
    default=False,
    action="store_true",
)


args = lifestream.arguments.parse_args()

Lifestream = lifestream.Lifestream()

STEAMTIME = pytz.timezone("US/Pacific")

USER = lifestream.config.get("steam", "username")


if __name__ == "__main__":
  steam_cxn = SteamAPI()
  if args.catchup:
    logger.info("CATCHUP MODE: Fetching all achievements.")
    games = steam_cxn.get_owned_games(include_appinfo=True)
  else:
    logger.info("NORMAL MODE: Fetching only recent achievements.")
    games = steam_cxn.get_recently_played_games(count=10)
  
  logger.info(f"Found {len(games['response'].get('games', []))} games to check for achievements.")
    
  for game in games['response']['games']:
    appid = game['appid']
    name = game['name']
    playtime_2weeks = game.get('playtime_2weeks', 0)
    playtime_forever = game['playtime_forever']
    
    text = f"Played {name}: {playtime_2weeks} mins in last 2 weeks, {playtime_forever} mins total."
    logger.info(text)
    
    try:
      player_achievements = steam_cxn.get_player_achievements(appid)
    except requests.HTTPError as e:
      logger.warning(f"Error fetching achievements for {name} ({appid}): {e}")
      continue
      
    unsorted_game_achievements = steam_cxn.get_game_achievements(appid)
    
    game_achievements = {}
    if 'availableGameStats' not in unsorted_game_achievements['game'] or 'achievements' not in unsorted_game_achievements['game']['availableGameStats']:
      logger.info(f"   + No achievements found for {name} ({appid}).")
      continue
      
    for achievement in unsorted_game_achievements['game']['availableGameStats']['achievements']:
      game_achievements[achievement['name']] = achievement
    
    
    if 'playerstats' in player_achievements and 'achievements' in player_achievements['playerstats']:
      for player_achievement in player_achievements['playerstats']['achievements']:
        if player_achievement['achieved'] == 1:
          ach_id = player_achievement['apiname']
          game_achievement = game_achievements.get(ach_id, {})
          ach_name = game_achievement.get('displayName', 'Unknown Achievement')
          text_ach = f"Earned achievement in {name}: {ach_id}"
          
          message = "%s &ndash; %s" % (name, ach_name)
          
          achieved_date = datetime.fromtimestamp(player_achievement['unlocktime'])
          
          
          logger.info(message)
          
          closedImage = game_achievement.get('icongray', None)
          openImage = game_achievement.get('icon', None)
          
          id = hashlib.md5()
          id.update(f"{appid}-{ach_id}".encode("utf-8"))
          
          entry = Lifestream.get_by_title("achievement", message)
          if entry and not entry['systemid'] == id.hexdigest():
              logger.info("           + Achievement already in Lifestream, deleting.")
              logger.info(f"             + Entry ID: {entry['title']}")
              Lifestream.delete_entry(entry['type'], entry['systemid'])
          else:
              logger.info("           + Adding Achievement to Lifestream.")
                    
          statsPage = f"https://steamcommunity.com/id/%s/stats/%s/?tab=achievements" % (USER, appid)
          
          Lifestream.add_entry(
              "achievement",
              id.hexdigest(),
              message,
              "steam",
              achieved_date,
              url=statsPage,
              image=openImage,
          )

            
