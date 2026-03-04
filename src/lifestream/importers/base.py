"""
Base importer class for Lifestream.

All importers should inherit from BaseImporter and implement the run() method.
"""

import argparse
import logging
import sys
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from lifestream.core import (
    config,
    EntryStore,
    setup_logging,
    get_secrets_dir,
    set_no_db_mode,
)


class BaseImporter(ABC):
    """
    Base class for all Lifestream importers.

    Subclasses must implement:
    - name: Class attribute with the importer name
    - run(): The main import logic

    Optional overrides:
    - add_arguments(): Add custom CLI arguments
    - validate_config(): Check required config sections
    """

    # Subclasses should override these
    name: str = "base"
    description: str = "Base importer"
    config_section: str | None = None

    def __init__(self):
        """Initialize the importer."""
        self.logger = logging.getLogger(self.name)
        self._entry_store: EntryStore | None = None
        self._args: argparse.Namespace | None = None
        self._parser: argparse.ArgumentParser | None = None

    @property
    def entry_store(self) -> EntryStore:
        """Lazy-initialized entry store."""
        if self._entry_store is None:
            self._entry_store = EntryStore()
        return self._entry_store

    @property
    def args(self) -> argparse.Namespace:
        """Parsed command line arguments."""
        if self._args is None:
            self._args = self.parse_args()
        return self._args

    def get_parser(self) -> argparse.ArgumentParser:
        """Get the argument parser, creating if needed."""
        if self._parser is None:
            self._parser = argparse.ArgumentParser(
                description=self.description,
                prog=f"lifestream-import {self.name}",
            )
            # Add standard arguments
            self._parser.add_argument(
                "--debug",
                action="store_true",
                help="Enable debug logging",
            )
            self._parser.add_argument(
                "--verbose",
                "-v",
                action="store_true",
                help="Enable verbose logging",
            )
            self._parser.add_argument(
                "--no-db",
                action="store_true",
                help="Print database operations instead of executing them",
            )
            # Let subclasses add their own arguments
            self.add_arguments(self._parser)
        return self._parser

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """
        Add custom arguments to the parser.

        Override this in subclasses to add importer-specific arguments.
        """
        pass

    def parse_args(self, args: list[str] | None = None) -> argparse.Namespace:
        """Parse command line arguments."""
        parser = self.get_parser()
        return parser.parse_args(args)

    def get_config(self, key: str, fallback: str | None = None) -> str | None:
        """Get a config value from this importer's section."""
        section = self.config_section or self.name
        if config.has_option(section, key):
            return config.get(section, key)
        return fallback

    def get_config_bool(self, key: str, fallback: bool = False) -> bool:
        """Get a boolean config value from this importer's section."""
        section = self.config_section or self.name
        if config.has_option(section, key):
            return config.getboolean(section, key)
        return fallback

    def require_config(self, *keys: str) -> dict[str, str]:
        """
        Require that config keys exist, returning their values.

        Raises SystemExit if any keys are missing.
        """
        section = self.config_section or self.name
        values = {}
        missing = []

        for key in keys:
            if config.has_option(section, key):
                values[key] = config.get(section, key)
            else:
                missing.append(key)

        if missing:
            self.logger.error(
                f"Missing required config keys in [{section}]: {', '.join(missing)}"
            )
            sys.exit(5)

        return values

    def validate_config(self) -> bool:
        """
        Validate that required config is present.

        Override in subclasses that need specific config.
        Returns True if valid, False otherwise.
        """
        return True

    def get_secrets_path(self, filename: str) -> str:
        """Get the full path to a secrets file."""
        return str(get_secrets_dir() / filename)

    @abstractmethod
    def run(self) -> None:
        """
        Run the import.

        This is the main entry point that subclasses must implement.
        """
        pass

    def execute(self, args: list[str] | None = None) -> int:
        """
        Execute the importer with full setup.

        This is the main entry point called by the CLI.

        Args:
            args: Command line arguments (uses sys.argv if None)

        Returns:
            Exit code (0 for success)
        """
        try:
            # Parse arguments
            self._args = self.parse_args(args)

            # Setup logging based on arguments
            setup_logging(
                debug=self.args.debug,
                verbose=self.args.verbose,
            )

            # Set no-db mode if requested
            if self.args.no_db:
                set_no_db_mode(True)

            # Validate config
            if not self.validate_config():
                return 5

            # Run the import
            start_time = datetime.now()
            self.logger.info(f"Starting {self.name} import")

            self.run()

            duration = (datetime.now() - start_time).total_seconds()
            self.logger.info(f"Completed {self.name} import in {duration:.1f}s")

            return 0

        except KeyboardInterrupt:
            self.logger.warning("Import interrupted by user")
            return 130
        except Exception as e:
            self.logger.exception(f"Import failed: {e}")
            return 1

    @classmethod
    def main(cls, args: list[str] | None = None) -> int:
        """
        Main entry point for running this importer.

        Creates an instance and runs it.

        Args:
            args: Command line arguments (uses sys.argv if None)

        Returns:
            Exit code
        """
        importer = cls()
        return importer.execute(args)


class FeedImporter(BaseImporter):
    """
    Base class for feed-based importers (RSS, Atom, etc.).

    Provides common functionality for parsing feeds.
    """

    feed_url: str | None = None
    entry_type: str = "feed"
    source_name: str = "feed"

    def get_feed_url(self) -> str:
        """Get the feed URL. Override if URL is dynamic."""
        if self.feed_url:
            return self.feed_url
        url = self.get_config("feed_url")
        if not url:
            self.logger.error("No feed URL configured")
            sys.exit(5)
        return url

    def process_entry(self, entry: dict[str, Any]) -> None:
        """
        Process a single feed entry.

        Override this to customize entry processing.
        """
        pass


class OAuthImporter(BaseImporter):
    """
    Base class for importers that use OAuth authentication.

    Provides common OAuth flow handling.
    """

    oauth_filename: str | None = None

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add OAuth-related arguments."""
        parser.add_argument(
            "--reauth",
            action="store_true",
            help="Force re-authentication",
        )

    def get_oauth_path(self) -> str:
        """Get the path to the OAuth token file."""
        if self.oauth_filename:
            return self.get_secrets_path(self.oauth_filename)
        return self.get_secrets_path(f"{self.name}.oauth")

    def load_oauth_token(self):
        """Load OAuth token from file. Override to customize."""
        import pickle

        path = self.get_oauth_path()
        try:
            with open(path, "rb") as f:
                return pickle.load(f)
        except (FileNotFoundError, pickle.UnpicklingError):
            return None

    def save_oauth_token(self, token) -> None:
        """Save OAuth token to file."""
        import pickle

        path = self.get_oauth_path()
        with open(path, "wb") as f:
            pickle.dump(token, f)
