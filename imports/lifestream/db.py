"""Database functionality for Lifestream."""

from datetime import datetime

import pymysql as MySQLdb
import pymysql.cursors
import pytz
import simplejson

from . import config, get_parsed_args


def get_connection():
    """Get a database connection using config settings."""
    db = {}
    for item in config.items("database"):
        db[item[0]] = item[1]

    dbcxn = MySQLdb.connect(
        user=db["username"],
        passwd=db["password"],
        db=db["database"],
        host=db["hostname"],
        charset="utf8mb4",
    )
    return dbcxn


def get_cursor(dbcxn):
    """Get a cursor with UTF-8 settings configured."""
    dbc = dbcxn.cursor()
    dbc.execute("SET NAMES utf8mb4;")
    dbc.execute("SET CHARACTER SET utf8mb4;")
    dbc.execute("SET character_set_connection=utf8mb4;")
    return dbc


class EntryStore:
    """Main database interface for lifestream entries."""

    def __init__(self):
        self._dbcxn = None
        self._cursor = None
        parsed_args = get_parsed_args()
        self.no_db = parsed_args.no_db if parsed_args else False

    @property
    def dbcxn(self):
        """Lazy database connection."""
        if self.no_db:
            return None
        if self._dbcxn is None:
            self._dbcxn = get_connection()
        return self._dbcxn

    @property
    def cursor(self):
        """Lazy cursor initialization."""
        if self.no_db:
            return None
        if self._cursor is None:
            self._cursor = get_cursor(self.dbcxn)
        return self._cursor

    def get_by_id(self, type, entry_id):
        """Get an entry by type and system ID."""
        if self.no_db:
            return None
        cursor = self.dbcxn.cursor(pymysql.cursors.DictCursor)
        sql = "select * from lifestream where type = %s and systemid = %s"
        cursor.execute(sql, (type, entry_id))
        return cursor.fetchone()

    def get_by_title(self, type, title):
        """Get an entry by type and title."""
        if self.no_db:
            return None
        cursor = self.dbcxn.cursor(pymysql.cursors.DictCursor)
        sql = "select * from lifestream where type = %s and title = %s"
        cursor.execute(sql, (type, title))
        return cursor.fetchone()

    def delete_entry(self, type, entry_id):
        """Delete an entry by type and system ID."""
        if self.no_db:
            print(f"[NO-DB] DELETE: type={type}, systemid={entry_id}")
            return
        sql = "delete from lifestream where type = %s and systemid = %s"
        self.cursor.execute(sql, (type, entry_id))
        self.dbcxn.commit()

    def add_entry(
        self,
        type,
        id,
        title,
        source,
        date,
        url="",
        image="",
        fulldata_json=False,
        update=False,
        debug=False,
    ):
        """Add or update a lifestream entry."""
        if fulldata_json:
            fulldata_json = simplejson.dumps(fulldata_json)

        if self.no_db:
            print(
                f"[NO-DB] INSERT: type={type}, systemid={id}, title={title}, "
                f"source={source}, date={date}, url={url}, image={image}"
            )
            return

        sql = (
            "select date_created from lifestream where type = %s and systemid = %s "
            "order by date_created desc limit 1"
        )

        self.cursor.execute(sql, (type, str(id)))
        if self.cursor.fetchone():
            if not update:
                return False
            else:
                s_sql = (
                    "UPDATE lifestream set `title`=%s, `url`=%s, `date_created`=%s, "
                    "`source`=%s, `image`=%s, `fulldata_json`=%s "
                    "where `systemid`=%s and `type`=%s"
                )
                self.cursor.execute(
                    s_sql, (title, url, date, source, image, fulldata_json, id, type)
                )
                if debug:
                    print(self.cursor._executed)
        else:
            s_sql = (
                "INSERT INTO lifestream (`type`, `systemid`, `title`, `url`, "
                "`date_created`, `source`, `image`, `fulldata_json`) "
                "values (%s, %s, %s, %s, %s, %s, %s, %s)"
            )
            self.cursor.execute(
                s_sql, (type, id, title, url, date, source, image, fulldata_json)
            )
            if debug:
                print(self.cursor._executed)

    def add_location(
        self, timestamp, source, lat, lon, title, icon=False, fulldata=False
    ):
        """Add a location entry."""
        if self.no_db:
            print(
                f"[NO-DB] LOCATION: source={source}, lat={lat}, lon={lon}, "
                f"timestamp={timestamp}, title={title}"
            )
            return

        l_sql = (
            "replace into lifestream_locations "
            "(`id`, `source`, `lat`, `long`, `lat_vague`, `long_vague`, "
            "`timestamp`, `accuracy`, `title`, `icon`, `fulldata_json`) "
            'values (%s, %s, %s, %s, %s, %s, %s, 1, %s, %s, "")'
        )
        time_start = datetime(1970, 1, 1, 0, 0, 0, 0, pytz.UTC)
        epoch = (timestamp - time_start).total_seconds()
        self.cursor.execute(
            l_sql,
            (
                epoch,
                source,
                lat,
                lon,
                round(lat, 2),
                round(lon, 2),
                timestamp,
                title,
                icon,
            ),
        )

    def add_stat(self, date, stat, number):
        """Add or update a statistic entry."""
        if self.no_db:
            print(f"[NO-DB] STAT: date={date}, stat={stat}, number={number}")
            return True

        s_sql = "replace into lifestream_stats (`date`, `statistic`, `number`) values (%s, %s, %s);"
        self.cursor.execute(s_sql, (date, stat, number))
        self.dbcxn.commit()
        return True
