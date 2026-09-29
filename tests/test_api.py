"""Tests for the public data API (#134): lifestream.core.api, mounted under
/v1 by lifestream.core.webserver.create_app()."""

import configparser
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from lifestream.core import api, webserver
from lifestream.core.db import LocationDedupLockError
from lifestream.core.ratelimit import limiter

API_SECRET = "secret123"
OWNTRACKS_PASSWORD = "phone-pass"


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """The rate limiter (lifestream.core.ratelimit.limiter) is a single
    process-wide, in-memory instance - see its module docstring - so
    without this, request counts would accumulate across every test in
    this file/session and could trip DEFAULT_RATE_LIMIT well before any
    individual test comes close to it itself."""
    limiter.reset()
    yield


def _cfg(api_key="", owntracks_password=""):
    cfg = configparser.ConfigParser()
    cfg.add_section("webserver")
    cfg.set("webserver", "allowed_origins", "")
    if api_key:
        cfg.set("webserver", "api_key", api_key)
    if owntracks_password:
        cfg.set("webserver", "owntracks_password", owntracks_password)
    return cfg


def _auth_headers(secret=API_SECRET):
    """A valid X-API-Key header: a freshly minted token, not the raw secret
    itself - mirrors what a real caller sends (see api.mint_api_token)."""
    return {"X-API-Key": api.mint_api_token(secret)}


@pytest.fixture
def store():
    # no_db must default to False: it's a real attribute api.py branches on
    # (create_entry's no-db echo path), and a bare MagicMock()'s attribute
    # access returns a truthy Mock, which would silently take that branch
    # in every test here that doesn't care about no-db mode specifically.
    store = MagicMock()
    store.no_db = False
    return store


@pytest.fixture
def client(store):
    # Both patches must stay live for the fixture's lifetime, not just
    # during create_app(): the API key check runs per-request, lazily
    # reading lifestream.core.api's module-level `config`.
    with (
        patch.object(webserver, "config", _cfg(api_key=API_SECRET)),
        patch.object(
            api,
            "config",
            _cfg(api_key=API_SECRET, owntracks_password=OWNTRACKS_PASSWORD),
        ),
    ):
        app = webserver.create_app()
        app.dependency_overrides[api.get_entry_store] = lambda: store
        yield TestClient(app)
        app.dependency_overrides.clear()


ENTRY_ROW = {
    "type": "steam",
    "systemid": "123",
    "title": "Achieved: Thing",
    "source": "Steam",
    "url": None,
    "image": None,
    "date_created": datetime(2024, 1, 1, 12, 0, 0),
    "date_updated": datetime(2024, 1, 1, 12, 0, 0),
    "fulldata_json": '{"raw": true}',
}

LOCATION_ROW = {
    "id": 1704110400,
    "source": "owntracks",
    "device": "phone",
    "lat": 51.5,
    "long": -0.1,
    "alt": 10.0,
    "alt_vague": 10.0,
    "lat_vague": 51.5,
    "long_vague": -0.1,
    "accuracy": 5,
    "title": "Home",
    "icon": None,
    "timestamp": datetime(2024, 1, 1, 12, 0, 0),
    "fulldata_json": '{"tst": 1704110400}',
}


class TestListEntries:
    def test_returns_page_with_decoded_fulldata(self, client, store):
        store.list_entries.return_value = ([ENTRY_ROW], 1)

        response = client.get("/v1/entries")

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["fulldata_json"] == {"raw": True}
        assert body["items"][0]["type"] == "steam"

    def test_passes_query_params_through(self, client, store):
        store.list_entries.return_value = ([], 0)

        client.get(
            "/v1/entries",
            params={"after": "2024-01-01T00:00:00", "offset": 5, "limit": 10},
        )

        _, kwargs = store.list_entries.call_args
        assert kwargs["offset"] == 5
        assert kwargs["limit"] == 10
        assert kwargs["after"] is not None

    def test_decodes_double_encoded_fulldata_json(self, client, store):
        """Regression: the existing atproto_posts importer calls
        add_entry(..., fulldata_json=item.post.model_dump_json()) - an
        already-JSON-encoded string, not a dict - which add_entry() then
        re-encodes, double-encoding it in storage. A naive single
        json.loads() of such a row returns a string where Entry expects a
        dict, so GET /v1/entries 500'd on any atproto-sourced row (a
        GitHub Copilot review finding on PR #206)."""
        double_encoded_row = {
            **ENTRY_ROW,
            "fulldata_json": json.dumps(json.dumps({"uri": "at://did/post/1"})),
        }
        store.list_entries.return_value = ([double_encoded_row], 1)

        response = client.get("/v1/entries")

        assert response.status_code == 200
        assert response.json()["items"][0]["fulldata_json"] == {
            "uri": "at://did/post/1"
        }

    def test_rejects_negative_offset(self, client, store):
        response = client.get("/v1/entries", params={"offset": -1})

        assert response.status_code == 400
        assert response.json()["status"] == 400

    def test_rejects_limit_over_200(self, client, store):
        response = client.get("/v1/entries", params={"limit": 500})

        assert response.status_code == 400


class TestSearchEntries:
    def test_requires_q(self, client, store):
        response = client.get("/v1/entries/search")

        assert response.status_code == 400

    def test_returns_matching_entries(self, client, store):
        store.search_entries.return_value = ([ENTRY_ROW], 1)

        response = client.get("/v1/entries/search", params={"q": "Thing"})

        assert response.status_code == 200
        assert response.json()["total"] == 1
        store.search_entries.assert_called_once_with(q="Thing", offset=0, limit=100)


class TestCreateEntry:
    BODY = {
        "type": "steam",
        "systemid": "123",
        "title": "Achieved: Thing",
        "source": "Steam",
        "date_created": "2024-01-01T12:00:00",
    }

    def test_requires_api_key(self, client, store):
        response = client.post("/v1/entries", json=self.BODY)

        assert response.status_code == 401
        assert response.json() == {
            "status": 401,
            "message": "Missing or invalid API key",
        }
        store.add_entry.assert_not_called()

    def test_rejects_wrong_api_key(self, client, store):
        response = client.post(
            "/v1/entries", json=self.BODY, headers={"X-API-Key": "wrong"}
        )

        assert response.status_code == 401

    def test_created_returns_201(self, client, store):
        from lifestream.core.db import EntryResult

        store.add_entry.return_value = EntryResult.INSERTED
        store.get_by_id.return_value = ENTRY_ROW

        response = client.post("/v1/entries", json=self.BODY, headers=_auth_headers())

        assert response.status_code == 201
        assert response.json()["systemid"] == "123"

    def test_existing_entry_returns_200(self, client, store):
        from lifestream.core.db import EntryResult

        store.add_entry.return_value = EntryResult.SKIPPED
        store.get_by_id.return_value = ENTRY_ROW

        response = client.post("/v1/entries", json=self.BODY, headers=_auth_headers())

        assert response.status_code == 200

    def test_concurrent_duplicate_insert_returns_200_not_500(self, client, store):
        """Regression: add_entry()'s SELECT-then-INSERT isn't atomic, so a
        concurrent request for the same (type, systemid) can insert first;
        this request's own INSERT then fails the table's primary key. That
        must surface as the same 200 idempotent no-op a slightly-later
        SELECT would have hit, not an uncaught 500 (a GitHub Copilot review
        finding on PR #206)."""
        from pymysql.err import IntegrityError

        store.add_entry.side_effect = IntegrityError(1062, "Duplicate entry")
        store.get_by_id.return_value = ENTRY_ROW

        response = client.post("/v1/entries", json=self.BODY, headers=_auth_headers())

        assert response.status_code == 200
        assert response.json()["systemid"] == "123"

    def test_no_db_echoes_input_instead_of_500(self, client, store):
        """Regression: in no-db mode, add_entry() returns None and
        get_by_id() always returns None, so this route always hit the
        "could not read back" 400 branch even though the (printed, not
        persisted) write succeeded (a GitHub Copilot review finding on
        PR #206). No-db mode should echo the input back, mirroring
        create_location's no-db behavior, not report success as a failure."""
        store.no_db = True
        store.add_entry.return_value = None
        store.get_by_id.return_value = None

        response = client.post("/v1/entries", json=self.BODY, headers=_auth_headers())

        assert response.status_code == 200
        body = response.json()
        assert body["systemid"] == "123"
        assert body["title"] == "Achieved: Thing"


class TestListLocations:
    def test_requires_from(self, client, store):
        response = client.get("/v1/locations")

        assert response.status_code == 400

    def test_redacts_precise_fields_without_api_key(self, client, store):
        store.list_locations.return_value = [LOCATION_ROW]

        response = client.get("/v1/locations", params={"from": "2024-01-01T00:00:00"})

        assert response.status_code == 200
        [point] = response.json()
        assert point["lat"] is None
        assert point["long"] is None
        assert point["fulldata_json"] is None
        assert point["lat_vague"] == 51.5

    def test_includes_precise_fields_with_valid_api_key(self, client, store):
        store.list_locations.return_value = [LOCATION_ROW]

        response = client.get(
            "/v1/locations",
            params={"from": "2024-01-01T00:00:00"},
            headers=_auth_headers(),
        )

        [point] = response.json()
        assert point["lat"] == 51.5
        assert point["fulldata_json"] == {"tst": 1704110400}

    def test_alt_and_alt_vague_serialize_as_integers(self, client, store):
        """Regression: the Location response model declared alt/alt_vague
        as float, so FastAPI's generated schema and JSON output (e.g.
        13.0) disagreed with both docs/api/openapi.yaml and the INT
        columns create_location() actually rounds to before storing (a
        GitHub Copilot review finding on PR #206)."""
        store.list_locations.return_value = [LOCATION_ROW]

        response = client.get(
            "/v1/locations",
            params={"from": "2024-01-01T00:00:00"},
            headers=_auth_headers(),
        )

        [point] = response.json()
        assert point["alt"] == 10
        assert isinstance(point["alt"], int)
        assert point["alt_vague"] == 10
        assert isinstance(point["alt_vague"], int)

    def test_invalid_api_key_still_redacts(self, client, store):
        store.list_locations.return_value = [LOCATION_ROW]

        response = client.get(
            "/v1/locations",
            params={"from": "2024-01-01T00:00:00"},
            headers={"X-API-Key": "wrong"},
        )

        [point] = response.json()
        assert point["lat"] is None

    def test_omitted_to_defaults_to_now_not_unbounded(self, client, store):
        """Regression: an omitted `to` used to reach the store as None,
        which list_locations() treats as no upper bound at all - so a
        future-dated row (e.g. from a clock-skewed client) would appear in
        a request for a historical range, contradicting the documented
        'defaults to now' contract (a GitHub Copilot review finding on
        PR #206)."""
        store.list_locations.return_value = []

        client.get("/v1/locations", params={"from": "2024-01-01T00:00:00"})

        _, kwargs = store.list_locations.call_args
        assert kwargs["date_to"] is not None


class TestCreateLocation:
    BODY = {
        "source": "owntracks",
        "lat": 51.5,
        "long": -0.1,
        "timestamp": "2024-01-01T12:00:00",
    }

    def test_requires_api_key(self, client, store):
        response = client.post("/v1/locations", json=self.BODY)

        assert response.status_code == 401
        store.create_location.assert_not_called()

    def test_created_returns_201(self, client, store):
        store.create_location.return_value = (LOCATION_ROW, True)

        response = client.post("/v1/locations", json=self.BODY, headers=_auth_headers())

        assert response.status_code == 201
        # Writer supplied a valid key, so the response is never redacted.
        assert response.json()["lat"] == 51.5

    def test_duplicate_returns_200(self, client, store):
        store.create_location.return_value = (LOCATION_ROW, False)

        response = client.post("/v1/locations", json=self.BODY, headers=_auth_headers())

        assert response.status_code == 200

    def test_rejects_out_of_range_lat(self, client, store):
        response = client.post(
            "/v1/locations",
            json={**self.BODY, "lat": 200},
            headers=_auth_headers(),
        )

        assert response.status_code == 400

    def test_lock_contention_returns_503(self, client, store):
        """A GitHub Copilot review finding on PR #206: create_location()
        raises LocationDedupLockError when it can't acquire the dedup
        lock, rather than silently proceeding unprotected. The route must
        surface that as a clean 503, not an uncaught 500."""
        from lifestream.core.db import LocationDedupLockError

        store.create_location.side_effect = LocationDedupLockError("no lock")

        response = client.post("/v1/locations", json=self.BODY, headers=_auth_headers())

        assert response.status_code == 503
        assert response.json()["status"] == 503


class TestGetLocationHeatmap:
    def test_returns_points(self, client, store):
        store.get_location_heatmap.return_value = [
            {"lat": 51.5, "long": -0.1, "count": 3, "title": "Home", "icon": None}
        ]

        response = client.get(
            "/v1/locations/heatmap", params={"from": "2024-01-01T00:00:00"}
        )

        assert response.status_code == 200
        assert response.json() == [
            {"lat": 51.5, "long": -0.1, "count": 3, "title": "Home", "icon": None}
        ]

    def test_omitted_to_defaults_to_now_not_unbounded(self, client, store):
        store.get_location_heatmap.return_value = []

        client.get("/v1/locations/heatmap", params={"from": "2024-01-01T00:00:00"})

        _, kwargs = store.get_location_heatmap.call_args
        assert kwargs["date_to"] is not None

    def test_requires_from(self, client, store):
        response = client.get("/v1/locations/heatmap")

        assert response.status_code == 400


class TestGetLatestLocation:
    def test_returns_404_when_none_recorded(self, client, store):
        store.get_latest_location.return_value = None

        response = client.get("/v1/locations/latest")

        assert response.status_code == 404
        assert response.json()["status"] == 404

    def test_redacts_without_api_key(self, client, store):
        store.get_latest_location.return_value = LOCATION_ROW

        response = client.get("/v1/locations/latest")

        assert response.status_code == 200
        assert response.json()["lat"] is None

    def test_precise_with_api_key(self, client, store):
        store.get_latest_location.return_value = LOCATION_ROW

        response = client.get("/v1/locations/latest", headers=_auth_headers())

        assert response.json()["lat"] == 51.5


class TestCreateUnhandledLocation:
    def test_requires_api_key(self, client, store):
        response = client.post(
            "/v1/locations/unhandled",
            json={"type": "waypoints", "fulldata_json": {"a": 1}},
        )

        assert response.status_code == 401
        store.add_unhandled_location.assert_not_called()

    def test_stores_payload(self, client, store):
        response = client.post(
            "/v1/locations/unhandled",
            json={"type": "waypoints", "fulldata_json": {"a": 1}},
            headers=_auth_headers(),
        )

        assert response.status_code == 201
        store.add_unhandled_location.assert_called_once_with("waypoints", {"a": 1})


class TestApiTokens:
    """Tests for mint_api_token/_verify_api_token directly: the signed,
    self-expiring token that stands in for sending the shared secret on
    every request (see API_TOKEN_MAX_AGE_SECONDS)."""

    def test_token_minted_with_secret_verifies(self):
        token = api.mint_api_token(API_SECRET)

        assert api._verify_api_token(token, API_SECRET) is True

    def test_token_minted_with_wrong_secret_fails(self):
        token = api.mint_api_token("other-secret")

        assert api._verify_api_token(token, API_SECRET) is False

    def test_garbage_token_fails(self):
        assert api._verify_api_token("not-a-real-token", API_SECRET) is False

    def test_validly_signed_but_wrong_payload_fails(self):
        """Regression: _verify_api_token only checked that *some* payload
        was signed with the secret, not which one - so a timestamped
        signature over any other payload, minted with the same secret for
        an unrelated purpose, would double as a valid API token (a GitHub
        Copilot review finding on PR #206)."""
        from itsdangerous import TimestampSigner

        other_token = (
            TimestampSigner(API_SECRET).sign(b"not-the-lifestream-payload").decode()
        )

        assert api._verify_api_token(other_token, API_SECRET) is False

    def test_non_ascii_token_fails_cleanly(self):
        """Regression: token.encode("ascii") previously ran outside any
        except clause covering UnicodeEncodeError, so a non-ASCII
        X-API-Key raised past this function instead of just failing
        verification (a GitHub Copilot review finding on PR #206)."""
        assert api._verify_api_token("töken-with-ünïcode", API_SECRET) is False

    def test_expired_token_fails(self):
        token = api.mint_api_token(API_SECRET)

        with patch.object(
            api, "API_TOKEN_MAX_AGE_SECONDS", -1
        ):  # token is already "older" than this by the time we verify it
            assert api._verify_api_token(token, API_SECRET) is False

    def test_expired_token_rejected_over_http(self, client, store):
        """An end-to-end check that an old token - not just a malformed one -
        is rejected by the live dependency, mirroring a leaked-and-replayed
        token after API_TOKEN_MAX_AGE_SECONDS has passed."""
        token = api.mint_api_token(API_SECRET)

        # -1 guarantees expiry regardless of timing jitter: a token's age at
        # verification is always >= 0, and 0 > -1 already trips itsdangerous's
        # "age > max_age" check.
        with patch.object(api, "API_TOKEN_MAX_AGE_SECONDS", -1):
            response = client.post(
                "/v1/locations/unhandled",
                json={"type": "waypoints", "fulldata_json": {"a": 1}},
                headers={"X-API-Key": token},
            )

        assert response.status_code == 401


class TestRateLimiting:
    """Tests for the rate limiting wired up in api.py/webserver.py (#134's
    rate-limit hardening): every /v1 route carries its own
    @limiter.limit(DEFAULT_RATE_LIMIT) - see the comment above
    api.list_entries for why per-route decorators are used instead of
    SlowAPIMiddleware's app-level default_limits - and /health is exempt.

    These exercise the real configured DEFAULT_RATE_LIMIT (60/minute)
    rather than swapping in a stricter limiter: the per-route decorators
    close over lifestream.core.ratelimit.limiter directly at import time,
    so replacing app.state.limiter in a test has no effect on them.
    """

    def test_exceeding_limit_returns_429(self, client, store):
        store.list_entries.return_value = ([], 0)

        responses = [client.get("/v1/entries") for _ in range(61)]

        assert [r.status_code for r in responses[:60]] == [200] * 60
        assert responses[60].status_code == 429
        assert responses[60].json()["status"] == 429

    def test_health_is_exempt_from_rate_limiting(self, client):
        # One more than DEFAULT_RATE_LIMIT allows: if exemption ever broke,
        # this would start returning 429 partway through.
        responses = [client.get("/health") for _ in range(61)]

        assert all(r.status_code == 200 for r in responses)


class TestGetEntryStore:
    """Tests for the get_entry_store dependency's connection lifecycle
    (a GitHub Copilot review finding on PR #206): MysqlEntryStore opens its
    connection lazily and has no teardown of its own, so a plain
    `Depends(lambda: EntryStore())` would leak one connection per request
    on a long-running webserver. get_entry_store is a `yield` dependency
    instead, so FastAPI closes the store after every request regardless of
    whether the route touched the DB or the request raised."""

    def test_closes_the_store_after_use(self):
        with patch.object(api, "EntryStore") as mock_entry_store_cls:
            mock_store = MagicMock()
            mock_entry_store_cls.return_value = mock_store

            generator = api.get_entry_store()
            yielded = next(generator)
            assert yielded is mock_store
            mock_store.close.assert_not_called()

            with pytest.raises(StopIteration):
                next(generator)  # drives the `finally` block

        mock_store.close.assert_called_once()

    def test_closes_the_store_even_if_the_route_raises(self):
        with patch.object(api, "EntryStore") as mock_entry_store_cls:
            mock_store = MagicMock()
            mock_entry_store_cls.return_value = mock_store

            generator = api.get_entry_store()
            next(generator)

            with pytest.raises(RuntimeError):
                generator.throw(RuntimeError("route handler blew up"))

        mock_store.close.assert_called_once()


class TestOwntracks:
    AUTH = ("anyone", OWNTRACKS_PASSWORD)
    LOCATION = {
        "_type": "location",
        "lat": 51.5,
        "lon": -0.12,
        "tst": 1704110400,
        "tid": "ab",
        "acc": 12,
        "alt": 30,
        "inregions": ["Home", "Garage"],
    }

    def test_location_is_stored_and_archived(self, client, store):
        store.create_location.return_value = ({}, True)
        resp = client.post("/v1/owntracks", json=self.LOCATION, auth=self.AUTH)
        assert resp.status_code == 200
        assert resp.json() == []
        kwargs = store.create_location.call_args.kwargs
        assert kwargs["source"] == "owntracks"
        assert kwargs["device"] == "ab"
        assert kwargs["lat"] == 51.5
        assert kwargs["lon"] == -0.12
        assert kwargs["accuracy"] == 12
        assert kwargs["title"] == "Home / Garage"
        assert kwargs["timestamp"] == datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
        store.add_unhandled_location.assert_called_once_with(
            "location", self.LOCATION, "stored"
        )

    def test_missing_inregions_stores_empty_title(self, client, store):
        payload = {k: v for k, v in self.LOCATION.items() if k != "inregions"}
        store.create_location.return_value = ({}, True)
        client.post("/v1/owntracks", json=payload, auth=self.AUTH)
        assert store.create_location.call_args.kwargs["title"] == ""

    def test_missing_type_is_archived_as_unknown(self, client, store):
        resp = client.post("/v1/owntracks", json={}, auth=self.AUTH)
        assert resp.status_code == 200
        store.add_unhandled_location.assert_called_once_with(
            "unknown", {}, "unhandled_type"
        )

    def test_401_carries_basic_challenge(self, client):
        resp = client.post("/v1/owntracks", json=self.LOCATION)
        assert resp.status_code == 401
        assert resp.headers["WWW-Authenticate"] == "Basic"

    def test_location_skipped_by_dedupe_is_archived_as_such(self, client, store):
        store.create_location.return_value = ({}, False)
        resp = client.post("/v1/owntracks", json=self.LOCATION, auth=self.AUTH)
        assert resp.status_code == 200
        store.add_unhandled_location.assert_called_once_with(
            "location", self.LOCATION, "dedupe"
        )

    def test_non_location_only_archived(self, client, store):
        payload = {"_type": "transition", "event": "enter"}
        resp = client.post("/v1/owntracks", json=payload, auth=self.AUTH)
        assert resp.status_code == 200
        store.create_location.assert_not_called()
        store.add_unhandled_location.assert_called_once_with(
            "transition", payload, "unhandled_type"
        )

    def test_unusable_location_is_archived_not_rejected(self, client, store):
        payload = {"_type": "location", "lat": 999, "lon": 0, "tst": 1704110400}
        resp = client.post("/v1/owntracks", json=payload, auth=self.AUTH)
        assert resp.status_code == 200
        store.create_location.assert_not_called()
        store.add_unhandled_location.assert_called_once_with(
            "location", payload, "invalid_location"
        )

    def test_dedup_lock_contention_returns_503_and_skips_archive(self, client, store):
        store.create_location.side_effect = LocationDedupLockError("busy")
        resp = client.post("/v1/owntracks", json=self.LOCATION, auth=self.AUTH)
        assert resp.status_code == 503
        store.add_unhandled_location.assert_not_called()

    @pytest.mark.parametrize("auth", [None, ("u", "wrong")])
    def test_bad_credentials_rejected(self, client, store, auth):
        resp = client.post("/v1/owntracks", json=self.LOCATION, auth=auth)
        assert resp.status_code == 401
        store.create_location.assert_not_called()
        store.add_unhandled_location.assert_not_called()

    def test_closed_when_password_unset(self, store):
        with (
            patch.object(webserver, "config", _cfg()),
            patch.object(api, "config", _cfg()),
        ):
            app = webserver.create_app()
            app.dependency_overrides[api.get_entry_store] = lambda: store
            resp = TestClient(app).post(
                "/v1/owntracks", json=self.LOCATION, auth=("u", "")
            )
        assert resp.status_code == 401

    def test_password_with_percent_authenticates(self, store):
        # Built via read_string, as a config file would be: ConfigParser's
        # interpolation rejects a bare `%` unless the value is read raw.
        cfg = configparser.ConfigParser()
        cfg.read_string("[webserver]\nowntracks_password = phone%pass\n")
        with (
            patch.object(webserver, "config", _cfg()),
            patch.object(api, "config", cfg),
        ):
            app = webserver.create_app()
            app.dependency_overrides[api.get_entry_store] = lambda: store
            client = TestClient(app)
            ok = client.post(
                "/v1/owntracks", json={"_type": "status"}, auth=("u", "phone%pass")
            )
            bad = client.post(
                "/v1/owntracks", json={"_type": "status"}, auth=("u", "phone")
            )
        assert ok.status_code == 200
        assert bad.status_code == 401

    def test_non_object_body_is_400(self, client):
        resp = client.post("/v1/owntracks", json=[1, 2], auth=self.AUTH)
        assert resp.status_code == 400
