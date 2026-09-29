"""Database functionality for Lifestream."""

import enum
import json
import warnings
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

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


class LocationDedupLockError(RuntimeError):
    """Raised by EntryStore.create_location() when the MySQL advisory lock
    guarding its dedup check couldn't be acquired (timeout or error) -
    proceeding anyway would silently reintroduce the concurrent-insert race
    the lock exists to prevent. lifestream.core.api's POST /v1/locations
    route catches this and returns 503."""


# Module-level state for no-db mode
_no_db_mode = False


def set_no_db_mode(enabled: bool) -> None:
    """Enable or disable no-db mode globally."""
    global _no_db_mode
    _no_db_mode = enabled


def get_no_db_mode() -> bool:
    """Check if no-db mode is enabled."""
    return _no_db_mode


def get_connection() -> MySQLdb.connections.Connection:
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


def get_cursor(dbcxn: MySQLdb.connections.Connection) -> pymysql.cursors.Cursor:
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

    def __new__(cls, no_db: bool | None = None) -> "EntryStore":
        if cls is not EntryStore:
            return super().__new__(cls)
        effective_no_db = no_db if no_db is not None else get_no_db_mode()
        target = NoDbEntryStore if effective_no_db else MysqlEntryStore
        return super().__new__(target)

    def __init__(self, no_db: bool | None = None) -> None:
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
    def dbcxn(self) -> MySQLdb.connections.Connection | None:
        """The underlying database connection, or None in no-db mode."""

    @property
    @abstractmethod
    def cursor(self) -> pymysql.cursors.Cursor | None:
        """A cursor on `dbcxn`, or None in no-db mode."""

    @abstractmethod
    def commit(self) -> None:
        """Commit the current transaction."""

    @abstractmethod
    def close(self) -> None:
        """Close the underlying connection, if one was ever opened. Safe to
        call even if no query ran (e.g. a request handler that never
        touched the store) - a no-op in that case, not a forced connect
        just to immediately disconnect. Used by the public API's per-request
        EntryStore dependency (lifestream.core.api.get_entry_store) so a
        long-running webserver process doesn't leak one MySQL connection
        per request."""

    @abstractmethod
    def get_by_id(self, type: str, entry_id: str) -> dict[str, Any] | None:
        """Get an entry by type and system ID."""

    @abstractmethod
    def get_by_title(self, type: str, title: str) -> dict[str, Any] | None:
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
        date: datetime | str,
        url: str = "",
        image: str = "",
        fulldata_json: Any = None,
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
        timestamp: datetime,
        source: str,
        lat: float,
        lon: float,
        title: str,
        icon: str = "",
        fulldata: Any = None,
    ) -> None:
        """Add a location entry."""

    @abstractmethod
    def add_stat(self, date: datetime | str, stat: str, number: int | float) -> bool:
        """Add or update a statistic entry."""

    @abstractmethod
    def get_historic_entries(
        self, date_from: datetime | str, date_to: datetime | str
    ) -> list[dict[str, Any]]:
        """
        Get Tumblr posts and tweets created in [date_from, date_to).

        Used by the historic replay importer to find posts from ten years ago.
        """

    @abstractmethod
    def list_entries(
        self,
        *,
        after: datetime | str | None = None,
        date_from: datetime | str | None = None,
        date_to: datetime | str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[dict[str, Any]], int]:
        """
        List feed entries for the public API (#134).

        Always excludes null-title rows and `source in (tumblr, lastfm)`,
        matching the current public feed. Ordered ascending by
        `date_updated` when `after` is given (polling for changes), else by
        `date_created`. Returns (items, total) where total ignores
        offset/limit.
        """

    @abstractmethod
    def search_entries(
        self, *, q: str, offset: int = 0, limit: int = 100
    ) -> tuple[list[dict[str, Any]], int]:
        """
        Title `LIKE %q%` search over feed entries for the public API (#134),
        applying the same exclusions as `list_entries`. Ordered ascending by
        `date_created`. Returns (items, total).
        """

    @abstractmethod
    def list_locations(
        self,
        *,
        date_from: datetime | str,
        date_to: datetime | str | None = None,
        source: str | None = None,
    ) -> list[dict[str, Any]]:
        """List location points in [date_from, date_to), ordered ascending
        by timestamp, for the public API (#134)."""

    @abstractmethod
    def get_location_heatmap(
        self,
        *,
        date_from: datetime | str,
        date_to: datetime | str | None = None,
        source: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Aggregated heatmap points for the public API (#134): rounds
        lat/long to 2 decimal places, groups identical rounded points, and
        counts, mirroring `generate_location_query()` in `fetchNext.php`.
        """

    @abstractmethod
    def get_latest_location(self) -> dict[str, Any] | None:
        """The most recently recorded location point, or None."""

    @abstractmethod
    def create_location(
        self,
        *,
        source: str,
        lat: float,
        lon: float,
        timestamp: datetime,
        device: str | None = None,
        alt: float | None = None,
        accuracy: int = 0,
        title: str | None = None,
        icon: str | None = None,
        fulldata_json: Any = None,
    ) -> tuple[dict[str, Any], bool]:
        """
        Record a location ping for the public API's `POST /v1/locations`
        (#134). Mirrors lifestream-web's `add_location()` dedup rule: if
        the source's chronologically-preceding point rounds to the same
        lat/long (1 decimal place), the write is skipped and that existing
        point is returned instead.

        Returns (row, created) — created is False when the write was
        skipped as a duplicate.

        Raises LocationDedupLockError if the advisory lock serializing this
        check-then-insert against concurrent callers couldn't be acquired.
        """

    @abstractmethod
    def add_unhandled_location(
        self, type: str, data: Any, why: str | None = None
    ) -> None:
        """Archive a raw OwnTracks payload, mirroring `raw_location_data()`,
        for the public API's `POST /v1/locations/unhandled` (#134). `why`
        records the reason it is archived (see lifestream.core.api's
        WHY_* constants); NULL when the caller doesn't say."""

    @abstractmethod
    def list_unhandled_locations(
        self, *, arrived_after: datetime
    ) -> list[dict[str, Any]]:
        """Archived OwnTracks `location` payloads (`owntracks_unhandled`,
        type = 'location') that were archived at or after `arrived_after`,
        oldest-archived first. Used by the OwnTracks backfill, which replays
        them through `create_location`. Rows carry `id`, `datestamp` and the
        raw `fulldata_json` string."""


class MysqlEntryStore(EntryStore):
    """EntryStore backend that reads and writes the real MySQL database."""

    def __init__(self, no_db: bool | None = None) -> None:
        self._dbcxn: MySQLdb.connections.Connection | None = None
        self._cursor: pymysql.cursors.Cursor | None = None

    @property
    def no_db(self) -> bool:
        return False

    @property
    def dbcxn(self) -> MySQLdb.connections.Connection:
        """Lazy database connection."""
        if self._dbcxn is None:
            self._dbcxn = get_connection()
        return self._dbcxn

    @property
    def cursor(self) -> pymysql.cursors.Cursor:
        """Lazy cursor initialization."""
        if self._cursor is None:
            self._cursor = get_cursor(self.dbcxn)
        return self._cursor

    def commit(self) -> None:
        self.dbcxn.commit()

    def close(self) -> None:
        # Checks the private attribute directly, not the public `dbcxn`/
        # `cursor` properties - those lazily open a connection on access,
        # which would defeat the point of a no-op close when one was never
        # opened.
        if self._dbcxn is not None:
            self._dbcxn.close()
            self._dbcxn = None
            self._cursor = None

    def get_by_id(self, type: str, entry_id: str) -> dict[str, Any] | None:
        cursor = self.dbcxn.cursor(pymysql.cursors.DictCursor)
        sql = "select * from lifestream where type = %s and systemid = %s"
        cursor.execute(sql, (type, entry_id))
        return cursor.fetchone()

    def get_by_title(self, type: str, title: str) -> dict[str, Any] | None:
        cursor = self.dbcxn.cursor(pymysql.cursors.DictCursor)
        sql = "select * from lifestream where type = %s and title = %s"
        cursor.execute(sql, (type, title))
        return cursor.fetchone()

    def delete_entry(self, type: str, entry_id: str) -> None:
        sql = "delete from lifestream where type = %s and systemid = %s"
        self.cursor.execute(sql, (type, entry_id))
        self.dbcxn.commit()

    def add_entry(
        self,
        type: str,
        id: str,
        title: str,
        source: str,
        date: datetime | str,
        url: str = "",
        image: str = "",
        fulldata_json: Any = None,
        update: bool = False,
        debug: bool = False,
    ) -> EntryResult | None:
        # Not `if fulldata_json:` - that treats an explicitly-passed empty
        # object ({}) the same as omitted, leaving it as a raw dict that
        # pymysql can't bind as a query parameter at all (TypeError) rather
        # than encoding it like any other payload. No existing caller relies
        # on the old truthiness check (none pass a deliberately falsy but
        # non-None value), so narrowing to `is not None` only changes this
        # empty-object case.
        if fulldata_json is not None:
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
        timestamp: datetime,
        source: str,
        lat: float,
        lon: float,
        title: str,
        icon: str = "",
        fulldata: Any = None,
    ) -> None:
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

    def add_stat(self, date: datetime | str, stat: str, number: int | float) -> bool:
        s_sql = "replace into lifestream_stats (`date`, `statistic`, `number`) values (%s, %s, %s);"
        self.cursor.execute(s_sql, (date, stat, number))
        self.dbcxn.commit()
        return True

    def get_historic_entries(
        self, date_from: datetime | str, date_to: datetime | str
    ) -> list[dict[str, Any]]:
        cursor = self.dbcxn.cursor(pymysql.cursors.DictCursor)
        sql = (
            "select title, date_created, url, fulldata_json, systemid, source, type "
            "from lifestream where (source = 'tumblr' or type = 'twitter') "
            "and date_created >= %s and date_created < %s"
        )
        cursor.execute(sql, (date_from, date_to))
        return list(cursor.fetchall())

    def list_entries(
        self,
        *,
        after: datetime | str | None = None,
        date_from: datetime | str | None = None,
        date_to: datetime | str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[dict[str, Any]], int]:
        cursor = self.dbcxn.cursor(pymysql.cursors.DictCursor)

        where_clauses = ["title IS NOT NULL", "source NOT IN (%s, %s)"]
        params: list[Any] = ["tumblr", "lastfm"]

        if after is not None:
            where_clauses.append("date_updated >= %s")
            params.append(after)
        if date_from is not None:
            where_clauses.append("date_created >= %s")
            params.append(date_from)
        if date_to is not None:
            where_clauses.append("date_created < %s")
            params.append(date_to)

        where_sql = " AND ".join(where_clauses)

        cursor.execute(
            f"SELECT COUNT(*) AS total FROM lifestream WHERE {where_sql}", params
        )
        total = cursor.fetchone()["total"]

        order_column = "date_updated" if after is not None else "date_created"
        cursor.execute(
            f"SELECT * FROM lifestream WHERE {where_sql} "
            f"ORDER BY {order_column} ASC LIMIT %s OFFSET %s",
            [*params, limit, offset],
        )
        return list(cursor.fetchall()), total

    def search_entries(
        self, *, q: str, offset: int = 0, limit: int = 100
    ) -> tuple[list[dict[str, Any]], int]:
        cursor = self.dbcxn.cursor(pymysql.cursors.DictCursor)

        where_sql = "title IS NOT NULL AND source NOT IN (%s, %s) AND title LIKE %s"
        params: list[Any] = ["tumblr", "lastfm", f"%{q}%"]

        cursor.execute(
            f"SELECT COUNT(*) AS total FROM lifestream WHERE {where_sql}", params
        )
        total = cursor.fetchone()["total"]

        cursor.execute(
            f"SELECT * FROM lifestream WHERE {where_sql} "
            "ORDER BY date_created ASC LIMIT %s OFFSET %s",
            [*params, limit, offset],
        )
        return list(cursor.fetchall()), total

    def list_locations(
        self,
        *,
        date_from: datetime | str,
        date_to: datetime | str | None = None,
        source: str | None = None,
    ) -> list[dict[str, Any]]:
        cursor = self.dbcxn.cursor(pymysql.cursors.DictCursor)

        where_clauses = ["timestamp >= %s"]
        params: list[Any] = [date_from]
        if date_to is not None:
            where_clauses.append("timestamp < %s")
            params.append(date_to)
        if source is not None:
            where_clauses.append("source = %s")
            params.append(source)

        where_sql = " AND ".join(where_clauses)
        cursor.execute(
            f"SELECT * FROM lifestream_locations WHERE {where_sql} "
            "ORDER BY timestamp ASC",
            params,
        )
        return list(cursor.fetchall())

    def get_location_heatmap(
        self,
        *,
        date_from: datetime | str,
        date_to: datetime | str | None = None,
        source: str | None = None,
    ) -> list[dict[str, Any]]:
        cursor = self.dbcxn.cursor(pymysql.cursors.DictCursor)

        where_clauses = ["timestamp >= %s", "lat IS NOT NULL", "`long` IS NOT NULL"]
        params: list[Any] = [date_from]
        if date_to is not None:
            where_clauses.append("timestamp < %s")
            params.append(date_to)
        if source is not None:
            where_clauses.append("source = %s")
            params.append(source)

        where_sql = " AND ".join(where_clauses)
        # Aggregated in SQL (ROUND/GROUP BY), not by fetching every raw row
        # and grouping in Python: a multi-year range can have millions of
        # points, and this way the API - and the network/memory between it
        # and MySQL - only ever handles one row per heatmap cell, not the
        # underlying long tail of raw pings. MIN() picks an arbitrary (but
        # deterministic-enough-for-a-marker-icon) representative title/icon
        # per group - MySQL's own ANY_VALUE() isn't available on MariaDB,
        # which is what this project actually runs against (see CI).
        cursor.execute(
            f"SELECT ROUND(lat, 2) AS lat, ROUND(`long`, 2) AS `long`, "
            f"COUNT(*) AS count, MIN(title) AS title, MIN(icon) AS icon "
            f"FROM lifestream_locations WHERE {where_sql} "
            f"GROUP BY ROUND(lat, 2), ROUND(`long`, 2)",
            params,
        )
        return list(cursor.fetchall())

    def get_latest_location(self) -> dict[str, Any] | None:
        cursor = self.dbcxn.cursor(pymysql.cursors.DictCursor)
        cursor.execute(
            "SELECT * FROM lifestream_locations ORDER BY timestamp DESC LIMIT 1"
        )
        return cursor.fetchone()

    def create_location(
        self,
        *,
        source: str,
        lat: float,
        lon: float,
        timestamp: datetime,
        device: str | None = None,
        alt: float | None = None,
        accuracy: int = 0,
        title: str | None = None,
        icon: str | None = None,
        fulldata_json: Any = None,
    ) -> tuple[dict[str, Any], bool]:
        # A naive `timestamp` is ambiguous: Python's .timestamp() interprets
        # it as the *server's local* timezone, so the same wall-clock string
        # would derive a different epoch id depending on the server's own
        # timezone setting, and would compare inconsistently against the
        # UTC-implicit values already in the table. Normalize to a naive UTC
        # value up front - matching every other timestamp in this table,
        # none of which carry tz info - so both the epoch id and the dedup
        # comparison below are well-defined regardless of what the caller
        # sent or where this process runs.
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        else:
            timestamp = timestamp.astimezone(timezone.utc)
        epoch = int(timestamp.timestamp())
        timestamp = timestamp.replace(tzinfo=None)

        cursor = self.dbcxn.cursor(pymysql.cursors.DictCursor)

        # The read (last point for this source) and the write below aren't
        # otherwise atomic - two concurrent requests for the same source
        # could both read the same predecessor and both insert, defeating
        # the dedup rule. A MySQL advisory lock, scoped to `source` and held
        # for this whole check-then-insert, serializes exactly that.
        lock_name = f"lifestream_location_dedup:{source}"
        cursor.execute("SELECT GET_LOCK(%s, 5) AS acquired", (lock_name,))
        lock_row = cursor.fetchone()
        # GET_LOCK returns 1 on success, 0 on timeout, NULL on error - any
        # non-1 result means we don't actually hold the lock, so proceeding
        # into the check-then-insert below would silently reintroduce the
        # exact race this lock exists to prevent. Only enter the try/finally
        # (and only ever release) once acquisition is confirmed.
        if lock_row is None or lock_row.get("acquired") != 1:
            raise LocationDedupLockError(
                f"Could not acquire the location dedup lock for source {source!r} "
                "within 5s"
            )
        try:
            cursor.execute(
                "SELECT * FROM lifestream_locations WHERE source = %s "
                "AND timestamp < %s ORDER BY timestamp DESC LIMIT 1",
                (source, timestamp),
            )
            last = cursor.fetchone()
            if (
                last is not None
                and last.get("lat_vague") is not None
                and last.get("long_vague") is not None
                and round(last["lat_vague"], 1) == round(lat, 1)
                and round(last["long_vague"], 1) == round(lon, 1)
            ):
                return last, False

            lat_vague = round(lat, 2)
            long_vague = round(lon, 2)
            # lifestream_locations.alt/alt_vague are both plain INT columns
            # (see the baseline schema) - storing the raw float would let
            # MySQL silently truncate it, so the response would claim a
            # decimal precision that was never actually persisted. Round
            # once here and use that same integer for both the stored value
            # and the response, rather than a value that only matches what
            # was requested, not what's in the database.
            alt = round(alt) if alt is not None else None
            alt_vague = alt
            # Both columns are NOT NULL in the schema (device also has its
            # own DEFAULT 'old-data', which binding an explicit NULL would
            # bypass rather than trigger) - normalize omitted values to the
            # same non-null placeholders the legacy add_location()/schema
            # already use, instead of passing None through to the query.
            device = device if device is not None else "old-data"
            fulldata = json.dumps(fulldata_json) if fulldata_json is not None else ""

            self.cursor.execute(
                "REPLACE INTO lifestream_locations "
                "(`id`, `source`, `device`, `accuracy`, `lat`, `long`, `alt`, "
                "`lat_vague`, `long_vague`, `alt_vague`, `timestamp`, `title`, "
                "`icon`, `fulldata_json`) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    epoch,
                    source,
                    device,
                    accuracy,
                    lat,
                    lon,
                    alt,
                    lat_vague,
                    long_vague,
                    alt_vague,
                    timestamp,
                    title,
                    icon,
                    fulldata,
                ),
            )
            self.dbcxn.commit()

            return {
                "id": epoch,
                "source": source,
                "device": device,
                "accuracy": accuracy,
                "lat": lat,
                "long": lon,
                "alt": alt,
                "lat_vague": lat_vague,
                "long_vague": long_vague,
                "alt_vague": alt_vague,
                "timestamp": timestamp,
                "title": title,
                "icon": icon,
                "fulldata_json": fulldata,
            }, True
        finally:
            cursor.execute("SELECT RELEASE_LOCK(%s)", (lock_name,))

    def add_unhandled_location(
        self, type: str, data: Any, why: str | None = None
    ) -> None:
        self.cursor.execute(
            "INSERT INTO owntracks_unhandled (`type`, `fulldata_json`, `why`) "
            "VALUES (%s, %s, %s)",
            (type, json.dumps(data), why),
        )
        self.dbcxn.commit()

    def list_unhandled_locations(
        self, *, arrived_after: datetime
    ) -> list[dict[str, Any]]:
        cursor = self.dbcxn.cursor(pymysql.cursors.DictCursor)
        cursor.execute(
            "SELECT id, datestamp, fulldata_json FROM owntracks_unhandled "
            "WHERE type = 'location' AND datestamp >= %s ORDER BY id ASC",
            (arrived_after,),
        )
        return list(cursor.fetchall())


class NoDbEntryStore(EntryStore):
    """EntryStore backend that prints intended writes instead of executing them."""

    def __init__(self, no_db: bool | None = None) -> None:
        pass

    @property
    def no_db(self) -> bool:
        return True

    @property
    def dbcxn(self) -> None:
        return None

    @property
    def cursor(self) -> None:
        return None

    def commit(self) -> None:
        pass

    def close(self) -> None:
        pass

    def get_by_id(self, type: str, entry_id: str) -> None:
        return None

    def get_by_title(self, type: str, title: str) -> None:
        return None

    def delete_entry(self, type: str, entry_id: str) -> None:
        print(f"[NO-DB] DELETE: type={type}, systemid={entry_id}")

    def add_entry(
        self,
        type: str,
        id: str,
        title: str,
        source: str,
        date: datetime | str,
        url: str = "",
        image: str = "",
        fulldata_json: Any = None,
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
        timestamp: datetime,
        source: str,
        lat: float,
        lon: float,
        title: str,
        icon: str = "",
        fulldata: Any = None,
    ) -> None:
        print(
            f"[NO-DB] LOCATION: source={source}, lat={lat}, lon={lon}, "
            f"timestamp={timestamp}, title={title}"
        )

    def add_stat(self, date: datetime | str, stat: str, number: int | float) -> bool:
        print(f"[NO-DB] STAT: date={date}, stat={stat}, number={number}")
        return True

    def get_historic_entries(
        self, date_from: datetime | str, date_to: datetime | str
    ) -> list[dict[str, Any]]:
        return []

    def list_entries(
        self,
        *,
        after: datetime | str | None = None,
        date_from: datetime | str | None = None,
        date_to: datetime | str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[dict[str, Any]], int]:
        return [], 0

    def search_entries(
        self, *, q: str, offset: int = 0, limit: int = 100
    ) -> tuple[list[dict[str, Any]], int]:
        return [], 0

    def list_locations(
        self,
        *,
        date_from: datetime | str,
        date_to: datetime | str | None = None,
        source: str | None = None,
    ) -> list[dict[str, Any]]:
        return []

    def get_location_heatmap(
        self,
        *,
        date_from: datetime | str,
        date_to: datetime | str | None = None,
        source: str | None = None,
    ) -> list[dict[str, Any]]:
        return []

    def get_latest_location(self) -> dict[str, Any] | None:
        return None

    def create_location(
        self,
        *,
        source: str,
        lat: float,
        lon: float,
        timestamp: datetime,
        device: str | None = None,
        alt: float | None = None,
        accuracy: int = 0,
        title: str | None = None,
        icon: str | None = None,
        fulldata_json: Any = None,
    ) -> tuple[dict[str, Any], bool]:
        print(
            f"[NO-DB] LOCATION (API): source={source}, lat={lat}, lon={lon}, "
            f"timestamp={timestamp}, title={title}"
        )
        # Mirrors MysqlEntryStore.create_location's normalization (naive ->
        # UTC epoch, alt rounded to int, fulldata_json's NOT NULL default)
        # so a no-db preview matches what the real backend would persist.
        if timestamp.tzinfo is None:
            epoch_ts = timestamp.replace(tzinfo=timezone.utc)
        else:
            epoch_ts = timestamp.astimezone(timezone.utc)
        alt = round(alt) if alt is not None else None
        return {
            "id": int(epoch_ts.timestamp()),
            "source": source,
            "device": device if device is not None else "old-data",
            "accuracy": accuracy,
            "lat": lat,
            "long": lon,
            "alt": alt,
            "lat_vague": round(lat, 2),
            "long_vague": round(lon, 2),
            "alt_vague": alt,
            "timestamp": timestamp,
            "title": title,
            "icon": icon,
            "fulldata_json": (
                json.dumps(fulldata_json) if fulldata_json is not None else ""
            ),
        }, True

    def add_unhandled_location(
        self, type: str, data: Any, why: str | None = None
    ) -> None:
        print(f"[NO-DB] UNHANDLED LOCATION: type={type}, why={why}, data={data}")

    def list_unhandled_locations(
        self, *, arrived_after: datetime
    ) -> list[dict[str, Any]]:
        return []
