"""add owntracks_unhandled table

The public API's `POST /v1/locations/unhandled`
(lifestream.core.db.EntryStore.add_unhandled_location, mirroring
lifestream-web's raw_location_data()) writes to `owntracks_unhandled`, but
the 827f4a24602a baseline - a snapshot of `SHOW CREATE TABLE` against
production - only covers `lifestream`, `lifestream_locations`, and
`lifestream_stats`, so a fresh `alembic upgrade head` never creates this
table and every request to that endpoint fails with a missing-table error.

Unlike the baseline, this isn't a production schema snapshot - the two
columns actually written (`type`, `fulldata_json`) are known from the
existing INSERT; `id`/`date_created` are a reasonable inferred shape, not
a confirmed one. Uses CREATE TABLE IF NOT EXISTS since it's possible some
deployments already created this table by hand outside of migrations -
which is also why downgrade() doesn't DROP it: there's no way to tell,
after the fact, "this migration's upgrade() created the table" from "it
already existed", and guessing wrong would destroy a pre-existing table's
data on exactly the deployments IF NOT EXISTS was added to protect.

Revision ID: 0eb85726c19e
Revises: 827f4a24602a
Create Date: 2026-09-27 19:33:03.382162

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0eb85726c19e"
down_revision: Union[str, Sequence[str], None] = "827f4a24602a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create owntracks_unhandled if it doesn't already exist."""
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS `owntracks_unhandled` (
          `id` bigint(20) NOT NULL AUTO_INCREMENT,
          `type` varchar(255) NOT NULL DEFAULT '',
          `fulldata_json` mediumtext NOT NULL,
          `date_created` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY (`id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )


def downgrade() -> None:
    """Intentionally a no-op, not a DROP TABLE.

    upgrade() uses CREATE TABLE IF NOT EXISTS because some deployments may
    already have had owntracks_unhandled before this migration existed; on
    those, an unconditional DROP TABLE here would destroy a pre-existing
    table (and all its data) that this migration never created. There's no
    reliable way to tell "this revision's upgrade() created the table" from
    "it already existed" after the fact, so downgrading this revision
    leaves the table in place rather than guessing wrong in the destructive
    direction.
    """
