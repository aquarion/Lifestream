"""add why to owntracks_unhandled

`POST /v1/owntracks` archives every payload it receives, including the
`location` ones it also stores as points, so a row's presence in
`owntracks_unhandled` no longer says whether the payload was handled. The
new nullable `why` column records the reason the row is there:

- `stored`: a location, saved as a point in `lifestream_locations`
- `dedupe`: a valid location skipped as the same 0.1 degree cell as the
  previous point
- `invalid_location`: a location missing or with unusable lat/lon/tst
- `unhandled_type`: any other OwnTracks `_type` (status, transition, ...)

NULL means "no reason recorded": every row from before this migration, and
rows written through `POST /v1/locations/unhandled`, which doesn't say.

Uses IF NOT EXISTS / IF EXISTS (MariaDB syntax; production and CI both run
MariaDB 10.11) so it is safe against a table that was altered by hand.

Revision ID: b7c1d2e94a10
Revises: 0eb85726c19e
Create Date: 2026-09-30 00:10:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7c1d2e94a10"
down_revision: Union[str, Sequence[str], None] = "0eb85726c19e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add the nullable `why` column."""
    op.execute(
        "ALTER TABLE `owntracks_unhandled` "
        "ADD COLUMN IF NOT EXISTS `why` varchar(32) NULL DEFAULT NULL"
    )


def downgrade() -> None:
    """Drop the `why` column (its values are lost)."""
    op.execute("ALTER TABLE `owntracks_unhandled` DROP COLUMN IF EXISTS `why`")
