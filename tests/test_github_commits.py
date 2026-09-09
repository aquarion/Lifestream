"""Tests for the GitHub commits importer."""

from unittest.mock import MagicMock, patch

from lifestream.importers.github_commits import GithubCommitsImporter


class TestGithubCommitsImporter:
    def _make_importer(self):
        imp = GithubCommitsImporter()
        imp._args = imp.parse_args([])
        imp._entry_store = MagicMock()
        return imp

    def test_validate_config_fails_when_keys_missing(self):
        imp = self._make_importer()
        imp.get_config = MagicMock(return_value=None)
        assert imp.validate_config() is False

    def test_validate_config_passes_when_all_keys_present(self):
        imp = self._make_importer()
        imp.get_config = MagicMock(return_value="set")
        assert imp.validate_config() is True

    def test_github_call_sends_bearer_auth_header(self):
        imp = self._make_importer()
        imp.get_config = MagicMock(return_value="mytoken")
        response = MagicMock()
        response.json.return_value = []

        with patch(
            "lifestream.importers.github_commits.requests.get", return_value=response
        ) as mock_get:
            imp.github_call("user/repos")

        args, kwargs = mock_get.call_args
        assert kwargs["headers"] == {"Authorization": "Bearer mytoken"}
        response.raise_for_status.assert_called_once()

    def test_run_adds_entries_only_for_own_commits(self):
        imp = self._make_importer()
        imp.get_config = MagicMock(
            side_effect=lambda k, fallback=None: {
                "username": "octocat",
                "auth_token": "tok",
            }.get(k, fallback)
        )

        repos = [
            {
                "name": "repo1",
                "full_name": "octocat/repo1",
                "owner": {"login": "octocat"},
            }
        ]
        commits = [
            {
                "sha": "abc123",
                "author": {"login": "octocat"},
                "commit": {
                    "message": "Fix bug",
                    "author": {"date": "2024-01-01T12:00:00Z"},
                },
                "html_url": "https://github.com/octocat/repo1/commit/abc123",
            },
            {
                "sha": "def456",
                "author": {"login": "someone-else"},
                "commit": {
                    "message": "Not mine",
                    "author": {"date": "2024-01-01T12:00:00Z"},
                },
                "html_url": "https://github.com/octocat/repo1/commit/def456",
            },
        ]

        with patch.object(imp, "_paginate", side_effect=[repos, commits]):
            imp.run()

        imp._entry_store.add_entry.assert_called_once()
        args = imp._entry_store.add_entry.call_args.args
        assert args[1] == "abc123"
        assert args[2] == "repo1: Fix bug"

    def test_run_handles_commit_with_no_author_using_repo_owner(self):
        imp = self._make_importer()
        imp.get_config = MagicMock(
            side_effect=lambda k, fallback=None: {
                "username": "octocat",
                "auth_token": "tok",
            }.get(k, fallback)
        )

        repos = [
            {
                "name": "repo1",
                "full_name": "octocat/repo1",
                "owner": {"login": "octocat"},
            }
        ]
        commits = [
            {
                "sha": "abc123",
                "author": None,
                "commit": {
                    "message": "Orphaned commit",
                    "author": {"date": "2024-01-01T12:00:00Z"},
                },
                "html_url": "https://github.com/octocat/repo1/commit/abc123",
            }
        ]

        with patch.object(imp, "_paginate", side_effect=[repos, commits]):
            imp.run()

        imp._entry_store.add_entry.assert_called_once()

    def test_paginate_stops_at_max_pages(self):
        imp = self._make_importer()
        imp.get_config = MagicMock(return_value="tok")

        with patch.object(
            imp, "github_call", side_effect=[["a"], ["b"], ["c"]]
        ) as mock_call:
            result = imp._paginate("some/path", max_pages=2)

        assert result == ["a", "b"]
        assert mock_call.call_count == 2

    def test_paginate_stops_when_page_is_empty(self):
        imp = self._make_importer()
        imp.get_config = MagicMock(return_value="tok")

        with patch.object(imp, "github_call", side_effect=[["a"], []]):
            result = imp._paginate("some/path")

        assert result == ["a"]
