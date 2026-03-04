"""
Configuration management for Lifestream.

Handles loading configuration from config.ini and providing path resolution.
"""

import configparser
from functools import lru_cache
from pathlib import Path


def _find_project_root() -> Path:
    """Find the project root directory by looking for pyproject.toml."""
    # Start from this file's location and walk up
    current = Path(__file__).resolve().parent

    # Walk up to find pyproject.toml
    for parent in [current] + list(current.parents):
        if (parent / "pyproject.toml").exists():
            return parent
        if (parent / "config.ini").exists():
            return parent

    # Fallback: use current working directory
    return Path.cwd()


def _find_config_file() -> Path | None:
    """Find the config.ini file."""
    project_root = _find_project_root()

    # Check common locations
    candidates = [
        project_root / "config.ini",
        Path.cwd() / "config.ini",
        Path.cwd().parent / "config.ini",
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return None


@lru_cache(maxsize=1)
def get_project_root() -> Path:
    """Get the project root directory."""
    return _find_project_root()


@lru_cache(maxsize=1)
def _load_config() -> configparser.ConfigParser:
    """Load and return the configuration."""
    cfg = configparser.ConfigParser()
    config_file = _find_config_file()

    if config_file:
        cfg.read(config_file)

    return cfg


# Global config object
config = _load_config()


def resolve_path(path: str) -> Path:
    """Resolve a path relative to the project root directory."""
    p = Path(path)
    if p.is_absolute():
        return p
    return get_project_root() / p


def get_secrets_dir() -> Path:
    """Get the secrets directory path, resolved relative to project root."""
    return resolve_path(config.get("global", "secrets_dir", fallback="keys"))


def get_log_dir() -> Path:
    """Get the log directory path, resolved relative to project root."""
    return resolve_path(config.get("global", "log_location", fallback="logs"))


def get_config_value(section: str, key: str, default: str | None = None) -> str | None:
    """Get a config value with an optional default."""
    if config.has_option(section, key):
        return config.get(section, key)
    return default


def get_config_bool(section: str, key: str, default: bool = False) -> bool:
    """Get a boolean config value."""
    if config.has_option(section, key):
        return config.getboolean(section, key)
    return default
