"""
Lifestream importers package.

Each importer is a class that inherits from BaseImporter.
"""

# Import all converted importers
from lifestream.importers.atom import AtomImporter
from lifestream.importers.atproto_posts import AtprotoImporter
from lifestream.importers.base import BaseImporter, FeedImporter, OAuthImporter
from lifestream.importers.destiny2 import Destiny2Importer
from lifestream.importers.facebook_page import FacebookPageImporter
from lifestream.importers.facebook_posts import FacebookPostsImporter
from lifestream.importers.ffxiv import FFXIVImporter
from lifestream.importers.flickr import FlickrImporter
from lifestream.importers.foursquare import FoursquareImporter
from lifestream.importers.github_commits import GithubCommitsImporter
from lifestream.importers.gw2 import GW2Importer
from lifestream.importers.historic import HistoricImporter
from lifestream.importers.instagram import InstagramImporter
from lifestream.importers.lastfm import LastfmImporter
from lifestream.importers.mastodon_toots import MastodonImporter
from lifestream.importers.oyster import OysterImporter
from lifestream.importers.oyster_csv import OysterCsvImporter
from lifestream.importers.steam import SteamImporter
from lifestream.importers.switchbot import SwitchbotImporter
from lifestream.importers.tumblr import TumblrImporter
from lifestream.importers.wordpress import WordpressImporter
from lifestream.importers.wow import WowImporter

__all__ = [
    # Base classes
    "BaseImporter",
    "FeedImporter",
    "OAuthImporter",
    # Importers
    "AtomImporter",
    "AtprotoImporter",
    "Destiny2Importer",
    "FacebookPageImporter",
    "FacebookPostsImporter",
    "FFXIVImporter",
    "FlickrImporter",
    "FoursquareImporter",
    "GithubCommitsImporter",
    "GW2Importer",
    "HistoricImporter",
    "InstagramImporter",
    "LastfmImporter",
    "MastodonImporter",
    "OysterImporter",
    "OysterCsvImporter",
    "SteamImporter",
    "SwitchbotImporter",
    "TumblrImporter",
    "WordpressImporter",
    "WowImporter",
]

# Registry of all importers by name
IMPORTERS = {
    "atom": AtomImporter,
    "atproto_posts": AtprotoImporter,
    "destiny2": Destiny2Importer,
    "facebook_page": FacebookPageImporter,
    "facebook_posts": FacebookPostsImporter,
    "ffxiv": FFXIVImporter,
    "flickr": FlickrImporter,
    "foursquare": FoursquareImporter,
    "github": GithubCommitsImporter,
    "github_commits": GithubCommitsImporter,  # legacy schedule name
    "gw2": GW2Importer,
    "historic": HistoricImporter,
    "instagram": InstagramImporter,
    "lastfm": LastfmImporter,
    "mastodon": MastodonImporter,
    "mastodon_toots": MastodonImporter,  # legacy schedule name
    "oyster": OysterImporter,
    "oyster_csv": OysterCsvImporter,
    "steam": SteamImporter,
    "switchbot": SwitchbotImporter,
    "tumblr": TumblrImporter,
    "wordpress": WordpressImporter,
    "wow": WowImporter,
}
