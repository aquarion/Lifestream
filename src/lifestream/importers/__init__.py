"""
Lifestream importers package.

Each importer is a class that inherits from BaseImporter.
"""

from lifestream.importers.base import (
    BaseImporter,
    FeedImporter,
    OAuthImporter,
)

# Import all converted importers
from lifestream.importers.atom import AtomImporter
from lifestream.importers.flickr import FlickrImporter
from lifestream.importers.github_commits import GithubCommitsImporter
from lifestream.importers.lastfm import LastfmImporter
from lifestream.importers.mastodon_toots import MastodonImporter
from lifestream.importers.steam import SteamImporter
from lifestream.importers.switchbot import SwitchbotImporter
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
    "LastfmImporter",
    "MastodonImporter",
    "SteamImporter",
    "SwitchbotImporter",
    "WordpressImporter",
]

# Registry of all importers by name
IMPORTERS = {
    "atom": AtomImporter,
    "flickr": FlickrImporter,
    "github": GithubCommitsImporter,
    "lastfm": LastfmImporter,
    "mastodon": MastodonImporter,
    "steam": SteamImporter,
    "switchbot": SwitchbotImporter,
    "wordpress": WordpressImporter,
}
