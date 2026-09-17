"""Database functionality for Lifestream."""

import enum
import json
import warnings
from abc import ABC, abstractmethod
from datetime import datetime

import pymysql as MySQLdb
import pymysql.cursors
import pytz

from .config import config

# Suppress MySQL warnings
warnings.filterwarnings("ignore", category=MySQLdb.Warning)


class EntryResult(enum.Enum):
    """Outcome of EntryStore.add_entry()."""

    INSERTED = "inserted"
    UPDATED = "updated"
    SKIPPED = "skipped"


# Module-level state for no-db mode
_no_db_mode = False


def set_no_db_mode(enabled: bool) -> None:
    """Enable or disable no-db mode globally."""
    global _no_db_mode
    _no_db_mode = enabled


def get_no_db_mode() -> bool:
    """Check if no-db mode is enabled."""
    return _no_db_mode


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


class EntryStore(ABC):
    """
    Interface for the lifestream entry store.

    Instantiating this class dispatches to a concrete backend —
    :class:`MysqlEntryStore` or :class:`NoDbEntryStore` — chosen once, at
    construction time, from `no_db` (or the global no-db setting when
    `no_db` is omitted). This keeps existing call sites like
    `EntryStore()` / `EntryStore(no_db=True)` working unchanged, while the
    no-db/real-db behavior itself lives on the concrete type instead of a
    mutable flag re-checked in every method. `no_db` is a read-only
    property of the resulting instance; mixing modes mid-instance isn't
    possible.
    """

    def __new__(cls, no_db: bool | None = None):
        if cls is not EntryStore:
            return super().__new__(cls)
        effective_no_db = no_db if no_db is not None else get_no_db_mode()
        target = NoDbEntryStore if effective_no_db else MysqlEntryStore
        return super().__new__(target)

    def __init__(self, no_db: bool | None = None):
        """
        Initialize EntryStore.

        Args:
            no_db: Selects the backend. If None, uses the global setting.
                Only consulted by `__new__`; concrete backends ignore it.
        """

    @property
    @abstractmethod
    def no_db(self) -> bool:
        """Whether this store no-ops writes (printing instead of hitting the DB)."""

    @property
    @abstractmethod
    def dbcxn(self):
        """The underlying database connection, or None in no-db mode."""

    @property
    @abstractmethod
    def cursor(self):
        """A cursor on `dbcxn`, or None in no-db mode."""

    @abstractmethod
    def commit(self) -> None:
        """Commit the current transaction."""

    @abstractmethod
    def get_by_id(self, type: str, entry_id: str):
        """Get an entry by type and system ID."""

    @abstractmethod
    def get_by_title(self, type: str, title: str):
        """Get an entry by type and title."""

    @abstractmethod
    def delete_entry(self, type: str, entry_id: str) -> None:
        """Delete an entry by type and system ID."""

    @abstractmethod
    def add_entry(
        self,
        type: str,
        id: str,
        title: str,
        source: str,
        date,
        url: str = "",
        image: str = "",
        fulldata_json=None,
        update: bool = False,
        debug: bool = False,
    ) -> EntryResult | None:
        """
        Add or update a lifestream entry.

        Returns:
            EntryResult.INSERTED if a new row was written, EntryResult.UPDATED
            if an existing row was overwritten (only possible with
            update=True), or EntryResult.SKIPPED if the entry already existed
            and update=False. Returns None in no-db mode (no write is
            performed).
        """

    @abstractmethod
    def add_location(
        self,
        timestamp,
        source: str,
        lat: float,
        lon: float,
        title: str,
        icon: str = "",
        fulldata=None,
    ) -> None:
        """Add a location entry."""

    @abstractmethod
    def add_stat(self, date, stat: str, number: int | float) -> bool:
        """Add or update a statistic entry."""


class MysqlEntryStore(EntryStore):
    """EntryStore backend that reads and writes the real MySQL database."""

    def __init__(self, no_db: bool | None = None):
        self._dbcxn = None
        self._cursor = None

    @property
    def no_db(self) -> bool:
        return False

    @property
    def dbcxn(self):
        """Lazy database connection."""
        if self._dbcxn is None:
            self._dbcxn = get_connection()
        return self._dbcxn

    @property
    def cursor(self):
        """Lazy cursor initialization."""
        if self._cursor is None:
            self._cursor = get_cursor(self.dbcxn)
        return self._cursor

    def commit(self):
        self.dbcxn.commit()

    def get_by_id(self, type: str, entry_id: str):
        cursor = self.dbcxn.cursor(pymysql.cursors.DictCursor)
        sql = "select * from lifestream where type = %s and systemid = %s"
        cursor.execute(sql, (type, entry_id))
        return cursor.fetchone()

    def get_by_title(self, type: str, title: str):
        cursor = self.dbcxn.cursor(pymysql.cursors.DictCursor)
        sql = "select * from lifestream where type = %s and title = %s"
        cursor.execute(sql, (type, title))
        return cursor.fetchone()

    def delete_entry(self, type: str, entry_id: str):
        sql = "delete from lifestream where type = %s and systemid = %s"
        self.cursor.execute(sql, (type, entry_id))
        self.dbcxn.commit()

    def add_entry(
        self,
        type: str,
        id: str,
        title: str,
        source: str,
        date,
        url: str = "",
        image: str = "",
        fulldata_json=None,
        update: bool = False,
        debug: bool = False,
    ) -> EntryResult | None:
        if fulldata_json:
            fulldata_json = json.dumps(fulldata_json)

        sql = (
            "select date_created from lifestream where type = %s and systemid = %s "
            "order by date_created desc limit 1"
        )

        self.cursor.execute(sql, (type, str(id)))
        if self.cursor.fetchone():
            if not update:
                return EntryResult.SKIPPED
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
                self.dbcxn.commit()
                return EntryResult.UPDATED
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
            self.dbcxn.commit()
            return EntryResult.INSERTED

    def add_location(
        self,
        timestamp,
        source: str,
        lat: float,
        lon: float,
        title: str,
        icon: str = "",
        fulldata=None,
    ):
        fulldata_json = json.dumps(fulldata) if fulldata else ""

        l_sql = (
            "replace into lifestream_locations "
            "(`id`, `source`, `lat`, `long`, `lat_vague`, `long_vague`, "
            "`timestamp`, `accuracy`, `title`, `icon`, `fulldata_json`) "
            "values (%s, %s, %s, %s, %s, %s, %s, 1, %s, %s, %s)"
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
                fulldata_json,
            ),
        )
        self.dbcxn.commit()

    def add_stat(self, date, stat: str, number: int | float):
        s_sql = "replace into lifestream_stats (`date`, `statistic`, `number`) values (%s, %s, %s);"
        self.cursor.execute(s_sql, (date, stat, number))
        self.dbcxn.commit()
        return True


class NoDbEntryStore(EntryStore):
    """EntryStore backend that prints intended writes instead of executing them."""

    def __init__(self, no_db: bool | None = None):
        pass

    @property
    def no_db(self) -> bool:
        return True

    @property
    def dbcxn(self):
        return None

    @property
    def cursor(self):
        return None

    def commit(self):
        pass

    def get_by_id(self, type: str, entry_id: str):
        return None

    def get_by_title(self, type: str, title: str):
        return None

    def delete_entry(self, type: str, entry_id: str):
        print(f"[NO-DB] DELETE: type={type}, systemid={entry_id}")

    def add_entry(
        self,
        type: str,
        id: str,
        title: str,
        source: str,
        date,
        url: str = "",
        image: str = "",
        fulldata_json=None,
        update: bool = False,
        debug: bool = False,
    ) -> EntryResult | None:
        print(
            f"[NO-DB] INSERT: type={type}, systemid={id}, title={title}, "
            f"source={source}, date={date}, url={url}, image={image}"
        )
        return None

    def add_location(
        self,
        timestamp,
        source: str,
        lat: float,
        lon: float,
        title: str,
        icon: str = "",
        fulldata=None,
    ):
        print(
            f"[NO-DB] LOCATION: source={source}, lat={lat}, lon={lon}, "
            f"timestamp={timestamp}, title={title}"
        )

    def add_stat(self, date, stat: str, number: int | float):
        print(f"[NO-DB] STAT: date={date}, stat={stat}, number={number}")
        return True
