"""
Lifestream importers package.

Each importer is a class that inherits from BaseImporter.
"""

# Import all converted importers
from lifestream.importers.atom import AtomImporter
from lifestream.importers.base import (
    BaseImporter,
    FeedImporter,
    OAuthImporter,
)
from lifestream.importers.flickr import FlickrImporter
from lifestream.importers.github_commits import GithubCommitsImporter
from lifestream.importers.historic import HistoricImporter
from lifestream.importers.lastfm import LastfmImporter
from lifestream.importers.mastodon_toots import MastodonImporter
from lifestream.importers.steam import SteamImporter
from lifestream.importers.switchbot import SwitchbotImporter
from lifestream.importers.tumblr import TumblrImporter
from lifestream.importers.wordpress import WordpressImporter

__all__ = [
    # Base classes
    "BaseImporter",
    "FeedImporter",
    "OAuthImporter",
    # Importers
    "AtomImporter",
    "FlickrImporter",
    "GithubCommitsImporter",
    "HistoricImporter",
    "LastfmImporter",
    "MastodonImporter",
    "SteamImporter",
    "SwitchbotImporter",
    "TumblrImporter",
    "WordpressImporter",
]

# Registry of all importers by name
IMPORTERS = {
    "atom": AtomImporter,
    "flickr": FlickrImporter,
    "github": GithubCommitsImporter,
    "github_commits": GithubCommitsImporter,  # legacy schedule name
    "historic": HistoricImporter,
    "lastfm": LastfmImporter,
    "mastodon": MastodonImporter,
    "mastodon_toots": MastodonImporter,  # legacy schedule name
    "steam": SteamImporter,
    "switchbot": SwitchbotImporter,
    "tumblr": TumblrImporter,
    "wordpress": WordpressImporter,
}
