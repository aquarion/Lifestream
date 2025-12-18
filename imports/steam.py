#!/usr/bin/python

import sys
import requests

import logging
import pytz
import requests
from datetime import datetime
from pprint import pprint
import hashlib

# Local
import lifestream

# Libraries


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
STEAMID = lifestream.config.get("steam", "steamid")
API_KEY = lifestream.config.get("steam", "apikey")


class SteamAPI:
  BASE_URL = "http://api.steampowered.com/"
  
  def __init__(self, api_key):
    self.api_key = api_key
    
  def make_steam_call(self, interface, method, version, params):
    url = f"{self.BASE_URL}{interface}/{method}/v{int(version):04d}/"
    params['key'] = self.api_key
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()
  
  def get_news_for_app(self, appid, count=3, maxlength=300):
    params = {
      'appid': appid,
      'count': count,
      'maxlength': maxlength
    }
    return self.make_steam_call("ISteamNews", "GetNewsForApp", "2", params)
  
  def get_global_achievements(self, appid):
    params = {
      'appid': appid
    }
    return self.make_steam_call("ISteamUserStats", "GetGlobalAchievementPercentagesForApp", "2", params)
  
  def get_player_summaries(self, steamids):
    params = {
      'steamids': ','.join(steamids)
    }
    return self.make_steam_call("ISteamUser", "GetPlayerSummaries", "2", params) 
  
  def get_friend_list(self, steamid, relationship="friend"):
    params = {
      'steamid': steamid,
      'relationship': relationship
    }
    return self.make_steam_call("ISteamUser", "GetFriendList", "1", params)
  
  def get_player_achievements(self, steamid, appid):
    params = {
      'steamid': steamid,
      'appid': appid
    }
    return self.make_steam_call("ISteamUserStats", "GetPlayerAchievements", "1", params)
  
  def get_user_stats_for_game(self, steamid, appid):
    params = {
      'steamid': steamid,
      'appid': appid
    }
    return self.make_steam_call("ISteamUserStats", "GetUserStatsForGame", "2", params)
  
  def get_owned_games(self, steamid, include_appinfo=True, include_played_free_games=True):
    params = {
      'steamid': steamid,
      'include_appinfo': int(include_appinfo),
      'include_played_free_games': int(include_played_free_games)
    }
    return self.make_steam_call("IPlayerService", "GetOwnedGames", "1", params)
  
  def get_recently_played_games(self, steamid, count=5):
    params = {
      'steamid': steamid,
      'count': count
    }
    return self.make_steam_call("IPlayerService", "GetRecentlyPlayedGames", "1", params)
  
  
  def get_badges(self, steamid):
    params = {
      'steamid': steamid
    }
    return self.make_steam_call("IPlayerService", "GetBadges", "1", params)
  
  
  def get_game_achievements(self, appid):
    params = {
      'appid': appid
    }
    return self.make_steam_call("ISteamUserStats", "GetSchemaForGame", "2", params)
  
  def get_global_stats_for_game(self, appid, count, name):
    params = {
      'appid': appid,
      'count': count,
      'name': name
    }
    return self.make_steam_call("ISteamUserStats", "GetGlobalStatsForGame", "1", params)
  
if __name__ == "__main__":
  steam_cxn = SteamAPI(API_KEY)
  if args.catchup:
    logger.info("CATCHUP MODE: Fetching all achievements.")
    games = steam_cxn.get_owned_games(STEAMID, include_appinfo=True)
  else:
    logger.info("NORMAL MODE: Fetching only recent achievements.")
    games = steam_cxn.get_recently_played_games(STEAMID, count=10)
  
  logger.info(f"Found {len(games['response'].get('games', []))} games to check for achievements.")
    
  for game in games['response']['games']:
    appid = game['appid']
    name = game['name']
    playtime_2weeks = game.get('playtime_2weeks', 0)
    playtime_forever = game['playtime_forever']
    
    text = f"Played {name}: {playtime_2weeks} mins in last 2 weeks, {playtime_forever} mins total."
    logger.info(text)
    
    try:
      player_achievements = steam_cxn.get_player_achievements(STEAMID, appid)
    except requests.HTTPError as e:
      logger.warning(f"Error fetching achievements for {name} ({appid}): {e}")
      pprint(game)
      sys.exit(1)
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
          
          # pprint(player_achievement)
          # pprint(game_achievement)
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

            