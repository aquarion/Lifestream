"""OAuth utility functions for Lifestream."""

from pathlib import Path


def write_token_file(
    filename: str | Path,
    oauth_token: str,
    oauth_token_secret: str,
) -> None:
    """
    Write a token file to hold the oauth token and oauth token secret.

    Args:
        filename: Path to the token file
        oauth_token: The OAuth token
        oauth_token_secret: The OAuth token secret
    """
    with open(filename, "w") as oauth_file:
        oauth_file.write(oauth_token + "\n")
        oauth_file.write(oauth_token_secret + "\n")


def read_token_file(filename: str | Path) -> tuple[str, str]:
    """
    Read a token file and return the oauth token and oauth token secret.

    Args:
        filename: Path to the token file

    Returns:
        Tuple of (oauth_token, oauth_token_secret)
    """
    with open(filename) as f:
        return f.readline().strip(), f.readline().strip()
