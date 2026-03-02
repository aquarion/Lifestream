"""Steam API client library."""

import requests

from . import config


class SteamAPI:
    """Client for the Steam Web API."""

    BASE_URL = "http://api.steampowered.com/"

    def __init__(self):
        self.api_key = config.get("steam", "apikey")
        self.steamid = config.get("steam", "steamid")

    def make_steam_call(self, interface, method, version, params):
        """Make a call to the Steam API."""
        url = f"{self.BASE_URL}{interface}/{method}/v{int(version):04d}/"
        params["key"] = self.api_key
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def get_news_for_app(self, appid, count=3, maxlength=300):
        """Get news for a Steam app."""
        params = {"appid": appid, "count": count, "maxlength": maxlength}
        return self.make_steam_call("ISteamNews", "GetNewsForApp", "2", params)

    def get_global_achievements(self, appid):
        """Get global achievement percentages for an app."""
        params = {"appid": appid}
        return self.make_steam_call(
            "ISteamUserStats", "GetGlobalAchievementPercentagesForApp", "2", params
        )

    def get_player_summaries(self, steamids):
        """Get player summaries for a list of Steam IDs."""
        params = {"steamids": ",".join(steamids)}
        return self.make_steam_call("ISteamUser", "GetPlayerSummaries", "2", params)

    def get_friend_list(self, steamid=None, relationship="friend"):
        """Get a player's friend list."""
        params = {"steamid": steamid or self.steamid, "relationship": relationship}
        return self.make_steam_call("ISteamUser", "GetFriendList", "1", params)

    def get_player_achievements(self, appid, steamid=None):
        """Get a player's achievements for a specific game."""
        params = {"steamid": steamid or self.steamid, "appid": appid}
        return self.make_steam_call(
            "ISteamUserStats", "GetPlayerAchievements", "1", params
        )

    def get_user_stats_for_game(self, appid, steamid=None):
        """Get a player's stats for a specific game."""
        params = {"steamid": steamid or self.steamid, "appid": appid}
        return self.make_steam_call(
            "ISteamUserStats", "GetUserStatsForGame", "2", params
        )

    def get_owned_games(
        self, steamid=None, include_appinfo=True, include_played_free_games=True
    ):
        """Get all games owned by a player."""
        params = {
            "steamid": steamid or self.steamid,
            "include_appinfo": int(include_appinfo),
            "include_played_free_games": int(include_played_free_games),
        }
        return self.make_steam_call("IPlayerService", "GetOwnedGames", "1", params)

    def get_recently_played_games(self, steamid=None, count=5):
        """Get a player's recently played games."""
        params = {"steamid": steamid or self.steamid, "count": count}
        return self.make_steam_call(
            "IPlayerService", "GetRecentlyPlayedGames", "1", params
        )

    def get_badges(self, steamid=None):
        """Get a player's badges."""
        params = {"steamid": steamid or self.steamid}
        return self.make_steam_call("IPlayerService", "GetBadges", "1", params)

    def get_game_achievements(self, appid):
        """Get the achievement schema for a game."""
        params = {"appid": appid}
        return self.make_steam_call("ISteamUserStats", "GetSchemaForGame", "2", params)

    def get_global_stats_for_game(self, appid, count, name):
        """Get global stats for a game."""
        params = {"appid": appid, "count": count, "name": name}
        return self.make_steam_call(
            "ISteamUserStats", "GetGlobalStatsForGame", "1", params
        )
