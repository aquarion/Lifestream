"""baseline schema

Represents the schema as it actually exists in production, for every
deployment created before Alembic was introduced. This is taken from
`SHOW CREATE TABLE` against the live database (2026-09-17), not from
schema.sql — the two have drifted apart over the years (column types,
an added `lifestream_locations.device` column, charsets), and schema.sql
was the stale one. A fresh install runs this via `alembic upgrade head`;
an existing deployment that already has this schema should instead run
`alembic stamp 827f4a24602a` to record that it's already at this point,
without re-running the DDL.

Revision ID: 827f4a24602a
Revises:
Create Date: 2026-09-17 17:10:37.210001

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "827f4a24602a"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the three tables, matching production's SHOW CREATE TABLE output."""
    op.execute(
        """
        CREATE TABLE `lifestream` (
          `id` int(11) DEFAULT NULL,
          `type` varchar(15) NOT NULL DEFAULT '',
          `systemid` varchar(128) NOT NULL DEFAULT '',
          `title` mediumtext DEFAULT NULL,
          `date_created` datetime DEFAULT NULL,
          `image` longtext NOT NULL DEFAULT '',
          `url` varchar(511) NOT NULL,
          `source` varchar(255) NOT NULL DEFAULT '',
          `date_updated` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          `subtype` varchar(255) DEFAULT NULL,
          `fulldata_json` mediumtext DEFAULT NULL,
          PRIMARY KEY (`systemid`,`type`)
        ) ENGINE=MyISAM DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )

    op.execute(
        """
        CREATE TABLE `lifestream_locations` (
          `id` bigint(20) unsigned NOT NULL,
          `source` char(32) NOT NULL,
          `device` char(128) NOT NULL DEFAULT 'old-data',
          `lat` double DEFAULT NULL,
          `long` double DEFAULT NULL,
          `alt` int(11) DEFAULT NULL,
          `alt_vague` int(11) DEFAULT NULL,
          `lat_vague` double DEFAULT NULL,
          `long_vague` double DEFAULT NULL,
          `timestamp` datetime NOT NULL,
          `accuracy` int(11) NOT NULL,
          `title` varchar(255) DEFAULT NULL,
          `icon` varchar(255) DEFAULT NULL,
          `fulldata_json` mediumtext NOT NULL,
          PRIMARY KEY (`id`,`source`,`device`)
        ) ENGINE=MyISAM DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci
        """
    )

    op.execute(
        """
        CREATE TABLE `lifestream_stats` (
          `date` datetime NOT NULL,
          `statistic` char(31) NOT NULL,
          `number` int(11) NOT NULL,
          PRIMARY KEY (`date`,`statistic`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci
        """
    )


def downgrade() -> None:
    """Drop all three tables."""
    op.execute("DROP TABLE IF EXISTS `lifestream_stats`")
    op.execute("DROP TABLE IF EXISTS `lifestream_locations`")
    op.execute("DROP TABLE IF EXISTS `lifestream`")
