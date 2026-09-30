"""Tests for alembic c4e8f1a27d35, which makes owntracks_unhandled's archive
timestamp column `datestamp` on every database."""

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_PATH = (
    Path(__file__).parent.parent
    / "alembic"
    / "versions"
    / "c4e8f1a27d35_reconcile_owntracks_unhandled_datestamp.py"
)


@pytest.fixture
def migration(monkeypatch):
    spec = importlib.util.spec_from_file_location("reconcile_datestamp", _PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "op", MagicMock())
    return module


def _run(migration, monkeypatch, columns):
    monkeypatch.setattr(migration, "_existing_columns", lambda: set(columns))
    migration.upgrade()
    return [call.args[0] for call in migration.op.execute.call_args_list]


def test_production_shape_is_left_alone(migration, monkeypatch):
    assert _run(migration, monkeypatch, {"id", "type", "datestamp", "why"}) == []


def test_migration_created_shape_is_renamed(migration, monkeypatch):
    statements = _run(migration, monkeypatch, {"id", "type", "date_created"})

    assert len(statements) == 1
    assert "CHANGE COLUMN `date_created` `datestamp`" in statements[0]


def test_a_table_with_neither_gets_datestamp(migration, monkeypatch):
    statements = _run(migration, monkeypatch, {"id", "type"})

    assert len(statements) == 1
    assert "ADD COLUMN `datestamp`" in statements[0]


def test_never_renames_when_both_exist(migration, monkeypatch):
    assert _run(migration, monkeypatch, {"datestamp", "date_created"}) == []


def test_chains_after_the_why_migration(migration):
    assert migration.down_revision == "b7c1d2e94a10"
