"""GitHub commits importer for Lifestream."""

import json

import dateutil.parser
import pytz
import requests

from lifestream.importers.base import BaseImporter


class GithubCommitsImporter(BaseImporter):
    """Import commits from GitHub repositories."""

    name = "github"
    description = "Import commits from GitHub repositories"
    config_section = "github"

    MAX_PAGES = 2
    URL_PREFIX = "https://github.com"

    def validate_config(self) -> bool:
        """Ensure GitHub credentials are configured."""
        if not self.get_config("username"):
            self.logger.error("No GitHub username in config")
            return False
        if not self.get_config("auth_token"):
            self.logger.error("No GitHub auth_token in config")
            return False
        return True

    def github_call(self, path: str, page: int = 1, perpage: int = 100) -> dict:
        """Make an authenticated GitHub API call."""
        token = self.get_config("auth_token")
        gh_url = f"https://api.github.com/{path}?page={page}&perpage={perpage}"
        headers = {"Authorization": f"token {token}"}

        self.logger.debug("Calling %s", path)
        r = requests.get(gh_url, headers=headers)

        if r.status_code != 200:
            self.logger.error(f"GitHub API error: {r.status_code}")
            self.logger.error(f"URL: {r.url}")
            self.logger.error(f"Response: {r.text}")
            raise Exception(f"GitHub API error: {r.status_code}")

        return json.loads(r.text)

    def run(self) -> None:
        """Import commits from all user repositories."""
        username = self.get_config("username")

        repos = self.github_call("user/repos")

        for repo in repos:
            self.logger.debug("Processing repo: %s", repo["name"])

            commits = self.github_call(f"repos/{repo['full_name']}/commits")

            for commit in commits:
                # Determine author
                if commit["author"] is None:
                    author = repo["owner"]["login"]
                else:
                    author = commit["author"]["login"]

                # Skip commits by other authors
                if username.lower() != author.lower():
                    self.logger.debug("Skipped: %s", commit["commit"]["message"])
                    continue

                message = f"{repo['name']}: {commit['commit']['message']}"
                url = commit["url"]
                localdate = dateutil.parser.parse(commit["commit"]["author"]["date"])
                utcdate = localdate.astimezone(pytz.utc).strftime("%Y-%m-%d %H:%M")
                commit_id = commit["sha"]

                self.logger.info(message)
                self.entry_store.add_entry(
                    "code",
                    commit_id,
                    message,
                    "github",
                    utcdate,
                    url=url,
                    fulldata_json=commit,
                )


def main():
    """Entry point for CLI."""
    return GithubCommitsImporter.main()


if __name__ == "__main__":
    exit(main())
