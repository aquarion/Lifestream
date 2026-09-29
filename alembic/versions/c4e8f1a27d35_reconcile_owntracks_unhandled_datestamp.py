"""reconcile owntracks_unhandled's archive timestamp column

Production's `owntracks_unhandled` (created by lifestream-web) timestamps
its rows in a `datestamp` column, but 0eb85726c19e created the table for
fresh databases with `date_created` instead - a guess at the shape, per its
own docstring. Code that reads the archive (the OwnTracks backfill) uses
`datestamp`, so a database built from migrations alone would fail with an
unknown-column error.

This makes every database end up with `datestamp`, and never touches one
that already has it (production): the column is renamed only when
`date_created` exists and `datestamp` doesn't, and added only when the table
has neither.

Revision ID: c4e8f1a27d35
Revises: b7c1d2e94a10
Create Date: 2026-09-30 00:40:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4e8f1a27d35"
down_revision: Union[str, Sequence[str], None] = "b7c1d2e94a10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMN_DEF = "timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP"


def _existing_columns() -> set[str]:
    rows = op.get_bind().execute(
        sa.text(
            "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'owntracks_unhandled'"
        )
    )
    return {row[0] for row in rows}


def upgrade() -> None:
    """Rename date_created to datestamp, or add datestamp, if it's missing."""
    columns = _existing_columns()
    if "datestamp" in columns:
        return
    if "date_created" in columns:
        op.execute(
            "ALTER TABLE `owntracks_unhandled` "
            f"CHANGE COLUMN `date_created` `datestamp` {_COLUMN_DEF}"
        )
    else:
        op.execute(
            f"ALTER TABLE `owntracks_unhandled` ADD COLUMN `datestamp` {_COLUMN_DEF}"
        )


def downgrade() -> None:
    """Intentionally a no-op.

    upgrade() can't tell, afterwards, a column it renamed from one that was
    already called `datestamp` (production's always was), so renaming it
    back to `date_created` could break a database that never had that name.
    """
