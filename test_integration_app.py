import types
from datetime import datetime

import pytest
import app  # your Flask app module


# ---------------------------------------------------------
# Fake in-memory collections and API responses
# ---------------------------------------------------------
class FakeZipCollection:
    """Fake Mongo collection for rental data (in-memory)."""

    def __init__(self):
        self.docs = []

    def find_one(self, query):
        if "ZipCode" in query:
            for d in self.docs:
                if d.get("ZipCode") == query["ZipCode"]:
                    return d
        return None

    def insert_one(self, doc):
        # Simulate MongoDB assigning an _id
        if "_id" not in doc:
            doc["_id"] = f"fake-zip-{len(self.docs) + 1}"
        self.docs.append(doc)

        class Result:
            inserted_id = doc["_id"]

        return Result()


class FakeUserCollection:
    """Fake Mongo collection for users (in-memory)."""

    def __init__(self, users=None):
        self.users = {u["username"]: u for u in (users or [])}
        self.updated = []

    def find_one(self, query):
        """
        Support:
          - {"username": u}
          - {"username": u, "password": p}
        """
        username = query.get("username")
        if not username:
            return None
        user = self.users.get(username)
        if not user:
            return None
        if "password" in query and user.get("password") != query["password"]:
            return None
        return user

    def insert_one(self, doc):
        self.users[doc["username"]] = doc

        class Result:
            inserted_id = "fake-user-id"

        return Result()

    def update_one(self, query, update):
        """
        Used by forgot-password:
          query = {"_id": user["_id"]}
          update = {"$set": {"password": new_pw}}
        """
        uid = query.get("_id")
        new_pw = update.get("$set", {}).get("password")
        for u in self.users.values():
            if u.get("_id") == uid:
                u["password"] = new_pw
        self.updated.append((query, update))


class FakeResponse:
    """Fake requests.Response for RentCast."""

    def __init__(self, status_code=200, json_data=None, text="OK"):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text

    def json(self):
        return self._json_data


# ---------------------------------------------------------
# Global fixture: patch DB + HTTP for ALL tests
# ---------------------------------------------------------
@pytest.fixture(autouse=True)
def patch_environment(monkeypatch):
    """
    Integration tests use the real Flask app (routes, templates, sessions),
    but fake out MongoDB collections and RentCast HTTP calls.
    """
    fake_zip_collection = FakeZipCollection()
    fake_user_collection = FakeUserCollection()

    monkeypatch.setattr(app, "collection", fake_zip_collection, raising=False)
    monkeypatch.setattr(app, "users_collection", fake_user_collection, raising=False)

    # Default RentCast: returns empty list unless a test overrides it.
    def default_fake_get(url, headers=None, params=None):
        return FakeResponse(status_code=200, json_data=[])

    monkeypatch.setattr(app, "requests", types.SimpleNamespace(get=default_fake_get))

    yield  # tests run here


@pytest.fixture
def client():
    app.app.config["TESTING"] = True
    with app.app.test_client() as c:
        yield c


# =====================================================================
# A. fetch_or_cache_zip "integration-ish" tests
#   (aligned with your unit test summary use cases)
# =====================================================================

def test_fetch_or_cache_zip_uses_cache_integration(monkeypatch):
    """
    DB already contains ZIP 75080 → uses cache, no API call.
    (test_fetch_or_cache_zip_uses_cache)
    """
    app.collection.docs = [{
        "_id": "cached-1",
        "ZipCode": 75080,
        "City": "Richardson",
        "County": "Dallas",
        "State": "TX",
        "AverageRent": 1500,
        "MedianRent": 1400,
    }]

    def fail_if_called(*args, **kwargs):
        raise AssertionError("requests.get should NOT be called on cached ZIP")

    monkeypatch.setattr(app, "requests", types.SimpleNamespace(get=fail_if_called))

    result = app.fetch_or_cache_zip("75080", api_key="dummy")

    assert result["City"] == "Richardson"
    assert result["_id"] == "cached-1"


def test_fetch_or_cache_zip_calls_api_and_caches_integration(monkeypatch):
    """
    DB empty; API returns Tyler, TX data → inserts parsed data into DB.
    (test_fetch_or_cache_zip_calls_api_and_caches)
    """
    json_data = [{
        "city": "Tyler",
        "county": "Smith",
        "state": "TX",
        "rentalData": {
            "lastUpdatedDate": "2025-01-01T00:00:00",
            "averageRent": 1800,
            "medianRent": 1750,
            "averageRentPerSquareFoot": 1.2,
            "medianRentPerSquareFoot": 1.1,
        },
    }]

    def fake_get(url, headers=None, params=None):
        assert params.get("zipCode") == "75701"
        return FakeResponse(status_code=200, json_data=json_data)

    monkeypatch.setattr(app, "requests", types.SimpleNamespace(get=fake_get))

    result = app.fetch_or_cache_zip("75701", api_key="dummy-key")

    assert result["City"] == "Tyler"
    assert result["ZipCode"] == 75701
    # cached
    assert len(app.collection.docs) == 1
    assert app.collection.docs[0]["ZipCode"] == 75701


def test_fetch_or_cache_zip_api_error_status_integration(monkeypatch):
    """
    API returns HTTP 500 → error dict.
    (test_fetch_or_cache_zip_api_error_status)
    """
    def fake_get(url, headers=None, params=None):
        return FakeResponse(status_code=500, json_data=None, text="Server error")

    monkeypatch.setattr(app, "requests", types.SimpleNamespace(get=fake_get))

    result = app.fetch_or_cache_zip("00000", api_key="dummy")

    assert "error" in result
    assert "500" in result["error"]


def test_fetch_or_cache_zip_no_data_integration(monkeypatch):
    """
    API returns 200 but [] → 'No data found'.
    (test_fetch_or_cache_zip_no_data)
    """
    def fake_get(url, headers=None, params=None):
        return FakeResponse(status_code=200, json_data=[])

    monkeypatch.setattr(app, "requests", types.SimpleNamespace(get=fake_get))

    result = app.fetch_or_cache_zip("99999", api_key="dummy")

    assert result == {"error": "No data found for that ZIP."}


# =====================================================================
# B. Authentication & Routing Flows
# =====================================================================

def test_login_success_redirects_home_integration(client):
    """
    Valid credentials POST → 302 → /home.
    (test_login_success_redirects_home)
    """
    app.users_collection.users = {
        "maddy": {
            "_id": "u1",
            "username": "maddy",
            "password": "secret",
            "api_key": "test-api-key",
            "security_question": "pet",
            "security_answer": "Fluffy",
        }
    }

    resp = client.post("/", data={"username": "maddy", "password": "secret"})
    assert resp.status_code == 302
    assert "/home" in resp.headers["Location"]


def test_login_invalid_credentials_returns_error_context_integration(client):
    """
    Wrong credentials POST → stays on login page with error.
    (test_login_invalid_credentials_returns_error_context)
    """
    resp = client.post("/", data={"username": "wrong", "password": "nope"}, follow_redirects=True)
    html = resp.data.decode().lower()
    assert "invalid credentials" in html or "error" in html


def test_signup_missing_username_shows_error_integration(client):
    """
    Signup missing username → 'Username required' message.
    (test_signup_missing_username_shows_error)
    """
    resp = client.post(
        "/signup",
        data={
            "username": "",
            "password": "pw",
            "confirm_password": "pw",
            "api_key": "key",
            "security_question": "pet",
            "security_answer": "Fluffy",
        },
        follow_redirects=True,
    )
    html = resp.data.decode().lower()
    assert "username is required" in html or "username required" in html


def test_home_requires_login_integration(client):
    """
    Access /home without session → redirect → /
    (test_home_requires_login)
    """
    resp = client.get("/home")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/")


def test_api_search_zip_missing_api_key_integration(client):
    """
    No API key in session → 403 JSON error.
    (test_api_search_zip_missing_api_key)
    """
    resp = client.get("/api/search_zip/75080")
    assert resp.status_code == 403
    data = resp.get_json()
    assert data["error"] == "Missing API key"


# =====================================================================
# C. Forgot Password – Full 2-Step Flow
# =====================================================================

def test_forgot_password_lookup_missing_username_integration(client):
    """
    step=lookup, username='' → error, show_reset=False.
    (test_forgot_password_lookup_missing_username_shows_error)
    """
    resp = client.post("/forgot_password", data={"step": "lookup", "username": ""}, follow_redirects=True)
    html = resp.data.decode().lower()
    assert "enter your username" in html or "please enter your username" in html


def test_forgot_password_lookup_valid_username_integration(client):
    """
    Valid username → shows security question, show_reset=True.
    (test_forgot_password_lookup_valid_username_shows_security_question)
    """
    app.users_collection.users = {
        "maddy": {
            "_id": "u1",
            "username": "maddy",
            "password": "oldpw",
            "api_key": "key",
            "security_question": "pet",
            "security_answer": "Fluffy",
        }
    }

    resp = client.post("/forgot_password", data={"step": "lookup", "username": "maddy"}, follow_redirects=True)
    html = resp.data.decode()
    assert "what is the name of your first pet" in html.lower()


def test_forgot_password_reset_wrong_security_answer_integration(client):
    """
    step=reset, wrong answer → 'incorrect answer' error.
    (test_forgot_password_reset_wrong_security_answer_shows_error)
    """
    app.users_collection.users = {
        "maddy": {
            "_id": "u1",
            "username": "maddy",
            "password": "oldpw",
            "api_key": "key",
            "security_question": "pet",
            "security_answer": "Fluffy",
        }
    }

    resp = client.post(
        "/forgot_password",
        data={
            "step": "reset",
            "username": "maddy",
            "security_answer": "WRONG",
            "new_password": "p1",
            "confirm_password": "p1",
        },
        follow_redirects=True,
    )
    html = resp.data.decode().lower()
    assert "security answer is incorrect" in html or "incorrect" in html


def test_forgot_password_reset_password_mismatch_integration(client):
    """
    Correct answer, mismatched passwords → mismatch error.
    (test_forgot_password_reset_password_mismatch_shows_error)
    """
    app.users_collection.users = {
        "maddy": {
            "_id": "u1",
            "username": "maddy",
            "password": "oldpw",
            "api_key": "key",
            "security_question": "pet",
            "security_answer": "Fluffy",
        }
    }

    resp = client.post(
        "/forgot_password",
        data={
            "step": "reset",
            "username": "maddy",
            "security_answer": "Fluffy",
            "new_password": "p1",
            "confirm_password": "p2",
        },
        follow_redirects=True,
    )
    html = resp.data.decode().lower()
    assert "passwords do not match" in html or "do not match" in html


def test_forgot_password_reset_success_updates_password_integration(client):
    """
    Correct answer + matching passwords → password updated, success message.
    (test_forgot_password_reset_success_updates_password_and_shows_success)
    """
    app.users_collection.users = {
        "maddy": {
            "_id": "u1",
            "username": "maddy",
            "password": "oldpw",
            "api_key": "key",
            "security_question": "pet",
            "security_answer": "Fluffy",
        }
    }

    resp = client.post(
        "/forgot_password",
        data={
            "step": "reset",
            "username": "maddy",
            "security_answer": "Fluffy",
            "new_password": "newpw",
            "confirm_password": "newpw",
        },
        follow_redirects=True,
    )
    html = resp.data.decode().lower()
    assert "password updated successfully" in html or "updated" in html
    assert app.users_collection.users["maddy"]["password"] == "newpw"


# =====================================================================
# D. Extra: search_all ZIPs integration flows
# =====================================================================

def test_search_all_with_typed_zip_only_integration(client, monkeypatch):
    """
    User logs in, types a ZIP, clicks Search All → gets results, data cached.
    """
    # Seed user
    app.users_collection.users = {
        "maddy": {
            "_id": "u1",
            "username": "maddy",
            "password": "secret",
            "api_key": "test-api-key",
            "security_question": "pet",
            "security_answer": "Fluffy",
        }
    }

    # Fake RentCast response for 75701
    json_data = [{
        "city": "Tyler",
        "county": "Smith",
        "state": "TX",
        "rentalData": {
            "lastUpdatedDate": "2025-01-01T00:00:00",
            "averageRent": 1800,
            "medianRent": 1750,
            "averageRentPerSquareFoot": 1.2,
            "medianRentPerSquareFoot": 1.1,
        },
    }]

    def fake_get(url, headers=None, params=None):
        assert params.get("zipCode") == "75701"
        return FakeResponse(status_code=200, json_data=json_data)

    monkeypatch.setattr(app, "requests", types.SimpleNamespace(get=fake_get))

    # Login
    client.post("/", data={"username": "maddy", "password": "secret"}, follow_redirects=True)

    # Ensure zip_list starts empty
    with client.session_transaction() as sess:
        sess["zip_list"] = []

    # Search All with typed ZIP
    resp = client.post(
        "/home",
        data={"action": "search_all", "zipcode": "75701"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "75701" in html
    assert "Tyler" in html or "Average Rent" in html
    assert len(app.collection.docs) == 1
    assert app.collection.docs[0]["ZipCode"] == 75701


def test_search_all_with_saved_zip_list_integration(client, monkeypatch):
    """
    User logs in, has multiple ZIPs in session zip_list, clicks Search All →
    results for all ZIPs, both cached.
    """
    app.users_collection.users = {
        "maddy": {
            "_id": "u1",
            "username": "maddy",
            "password": "secret",
            "api_key": "test-api-key",
            "security_question": "pet",
            "security_answer": "Fluffy",
        }
    }

    def fake_get(url, headers=None, params=None):
        z = params.get("zipCode")
        if z == "75701":
            data = [{
                "city": "Tyler",
                "county": "Smith",
                "state": "TX",
                "rentalData": {
                    "lastUpdatedDate": "2025-01-01T00:00:00",
                    "averageRent": 1800,
                    "medianRent": 1750,
                    "averageRentPerSquareFoot": 1.2,
                    "medianRentPerSquareFoot": 1.1,
                },
            }]
        elif z == "75080":
            data = [{
                "city": "Richardson",
                "county": "Dallas",
                "state": "TX",
                "rentalData": {
                    "lastUpdatedDate": "2025-01-02T00:00:00",
                    "averageRent": 1900,
                    "medianRent": 1850,
                    "averageRentPerSquareFoot": 1.3,
                    "medianRentPerSquareFoot": 1.2,
                },
            }]
        else:
            data = []
        return FakeResponse(status_code=200, json_data=data)

    monkeypatch.setattr(app, "requests", types.SimpleNamespace(get=fake_get))

    # Login
    client.post("/", data={"username": "maddy", "password": "secret"}, follow_redirects=True)

    # Pre-populate zip_list
    with client.session_transaction() as sess:
        sess["zip_list"] = ["75701", "75080"]

    resp = client.post(
        "/home",
        data={"action": "search_all"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "75701" in html
    assert "75080" in html

    stored_zips = {doc["ZipCode"] for doc in app.collection.docs}
    assert stored_zips == {75701, 75080}
