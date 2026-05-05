"""GitHub commits importer for Lifestream."""

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

    def github_call(self, path: str, page: int = 1, per_page: int = 100) -> list | dict:
        """Make an authenticated GitHub API call."""
        token = self.get_config("auth_token")
        gh_url = f"https://api.github.com/{path}?page={page}&per_page={per_page}"
        headers = {"Authorization": f"token {token}"}

        self.logger.debug("Calling %s page %d", path, page)
        r = requests.get(gh_url, headers=headers, timeout=30)
        r.raise_for_status()
        return r.json()

    def _paginate(self, path: str, max_pages: int | None = None) -> list:
        """Fetch all pages from a GitHub API endpoint."""
        results = []
        page = 1
        while True:
            data = self.github_call(path, page=page)
            if not data:
                break
            results.extend(data)
            if max_pages and page >= max_pages:
                break
            page += 1
        return results

    def run(self) -> None:
        """Import commits from all user repositories."""
        username = self.get_config("username")

        repos = self._paginate("user/repos")

        for repo in repos:
            self.logger.debug("Processing repo: %s", repo["name"])

            commits = self._paginate(
                f"repos/{repo['full_name']}/commits", max_pages=self.MAX_PAGES
            )

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
                url = commit["html_url"]
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
