"""baseline schema

Represents the schema as it has existed since schema.sql (2015), for every
deployment created before Alembic was introduced. A fresh install runs this
via `alembic upgrade head`; an existing deployment that already applied
schema.sql by hand should instead run `alembic stamp 827f4a24602a` to record
that it's already at this point, without re-running the DDL.

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
    """Create the three tables from schema.sql, verbatim."""
    op.execute(
        """
        CREATE TABLE `lifestream` (
          `id` int(11) DEFAULT NULL,
          `type` varchar(15) COLLATE utf8_unicode_ci NOT NULL DEFAULT '',
          `systemid` varchar(128) COLLATE utf8_unicode_ci NOT NULL DEFAULT '',
          `title` varchar(2047) COLLATE utf8_unicode_ci DEFAULT NULL,
          `date_created` datetime DEFAULT NULL,
          `image` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT '',
          `url` varchar(511) COLLATE utf8_unicode_ci NOT NULL,
          `source` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT '',
          `date_updated` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          `subtype` varchar(255) COLLATE utf8_unicode_ci DEFAULT NULL,
          `fulldata_json` mediumtext CHARACTER SET utf32 COLLATE utf32_unicode_ci,
          PRIMARY KEY (`systemid`,`type`)
        ) ENGINE=MyISAM DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci
        """
    )

    op.execute(
        """
        CREATE TABLE `lifestream_locations` (
          `id` bigint(20) unsigned NOT NULL,
          `source` varchar(255) COLLATE utf8_unicode_ci NOT NULL,
          `lat` double DEFAULT NULL,
          `long` double DEFAULT NULL,
          `alt` int(11) DEFAULT NULL,
          `alt_vague` int(11) DEFAULT NULL,
          `lat_vague` double DEFAULT NULL,
          `long_vague` double DEFAULT NULL,
          `timestamp` datetime NOT NULL,
          `accuracy` int(11) NOT NULL,
          `title` varchar(255) COLLATE utf8_unicode_ci DEFAULT NULL,
          `icon` varchar(255) COLLATE utf8_unicode_ci DEFAULT NULL,
          PRIMARY KEY (`id`,`source`)
        ) ENGINE=MyISAM DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci
        """
    )

    op.execute(
        """
        CREATE TABLE `lifestream_stats` (
          `date` date NOT NULL,
          `statistic` char(31) COLLATE utf8_unicode_ci NOT NULL,
          `number` int(11) NOT NULL,
          PRIMARY KEY (`date`,`statistic`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci
        """
    )


def downgrade() -> None:
    """Drop all three tables."""
    op.execute("DROP TABLE IF EXISTS `lifestream_stats`")
    op.execute("DROP TABLE IF EXISTS `lifestream_locations`")
    op.execute("DROP TABLE IF EXISTS `lifestream`")
