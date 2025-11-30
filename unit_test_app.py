import types
import sys

# --- Lightweight stub for pymongo so app.py can import without the real package ---
if "pymongo" not in sys.modules:
    class _DummyCollection:
        def __getitem__(self, name):
            return self
    class _DummyDB:
        def __getitem__(self, name):
            return _DummyCollection()
    class _DummyMongoClient:
        def __init__(self, *args, **kwargs):
            pass
        def __getitem__(self, name):
            return _DummyDB()
    dummy_module = types.SimpleNamespace(MongoClient=_DummyMongoClient)
    sys.modules["pymongo"] = dummy_module

import pytest
import app  # your app.py


# -------------------------------------------------------------------
# Fake in-memory "collections" and fake HTTP response for RentCast
# -------------------------------------------------------------------
class FakeZipCollection:
    """Fake Mongo collection for zipcode rental data."""

    def __init__(self, initial=None):
        self.docs = list(initial or [])
        self.inserted = []

    def find_one(self, query):
        # Only handle {"ZipCode": int(zip)} queries
        if "ZipCode" in query:
            for d in self.docs:
                if d.get("ZipCode") == query["ZipCode"]:
                    return d.copy()
            return None
        raise ValueError(f"Unexpected query to FakeZipCollection.find_one: {query!r}")

    def insert_one(self, doc):
        # Simulate MongoDB assigning an _id on insert
        if "_id" not in doc:
            doc["_id"] = "fake-id"
        self.docs.append(doc.copy())
        self.inserted.append(doc.copy())

        class Result:
            inserted_id = doc["_id"]

        return Result()


class FakeUserCollection:
    """Fake Mongo collection for users."""

    def __init__(self, users=None):
        # Index by username
        self.users = {u["username"]: u for u in (users or [])}
        self.updated = []

    def find_one(self, query):
        """
        Support:
          - {"username": username}
          - {"username": username, "password": password}
        """
        if "username" in query:
            u = self.users.get(query["username"])
            if not u:
                return None
            # If password is also specified, enforce it
            if "password" in query and u.get("password") != query["password"]:
                return None
            return u.copy()
        return None

    def insert_one(self, doc):
        self.users[doc["username"]] = doc.copy()

        class Result:
            inserted_id = "user-id"

        return Result()

    def update_one(self, query, update):
        """
        Only support app's pattern:
          query: {"_id": user["_id"]}
          update: {"$set": {"password": new_password}}
        """
        self.updated.append((query, update))
        # Update in-place if we can find user by _id
        target_id = query.get("_id")
        for uname, data in self.users.items():
            if data.get("_id") == target_id:
                new_pw = update.get("$set", {}).get("password")
                if new_pw is not None:
                    data["password"] = new_pw


class FakeResponse:
    """Fake requests.Response for RentCast calls."""

    def __init__(self, status_code=200, json_data=None, text="OK"):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text

    def json(self):
        return self._json_data


# -------------------------------------------------------------------
# Global patching fixture: collections + render_template
# -------------------------------------------------------------------
@pytest.fixture(autouse=True)
def patch_globals(monkeypatch):
    """
    For every test:
      - Replace real Mongo collections with fake in-memory ones.
      - Replace render_template with a dummy function (no real HTML files).
    """
    fake_zip_collection = FakeZipCollection()
    fake_user_collection = FakeUserCollection()

    monkeypatch.setattr(app, "collection", fake_zip_collection, raising=False)
    monkeypatch.setattr(app, "users_collection", fake_user_collection, raising=False)

    def fake_render_template(name, **context):
        # Return a string that embeds template name + context
        return f"TEMPLATE:{name}|CTX:{context}"

    monkeypatch.setattr(app, "render_template", fake_render_template, raising=False)

    yield  # tests run here


# -------------------------------------------------------------------
# Unit tests for fetch_or_cache_zip
# -------------------------------------------------------------------
def test_fetch_or_cache_zip_uses_cache(monkeypatch):
    """
    Case: ZIP already in Mongo cache.
    Expectation:
      - No HTTP call to RentCast.
      - Return cached document with same data.
    """
    app.collection.docs = [{
        "_id": "abc123",
        "ZipCode": 75080,
        "City": "Richardson",
        "AverageRent": 1500,
        "MedianRent": 1400,
    }]

    # If this gets called, the test should fail
    def fake_get(*args, **kwargs):
        raise AssertionError("requests.get must NOT be called when data is cached")

    monkeypatch.setattr(app, "requests", types.SimpleNamespace(get=fake_get))

    result = app.fetch_or_cache_zip("75080", api_key="dummy")

    assert result["ZipCode"] == 75080
    assert result["City"] == "Richardson"
    assert "_id" in result  # app code converts _id to string


def test_fetch_or_cache_zip_calls_api_and_caches(monkeypatch):
    """
    Case: ZIP not cached; API returns one market entry.
    Expectation:
      - HTTP call made.
      - Result document built correctly and inserted into collection.
    """
    app.collection.docs = []  # nothing cached

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
        assert "zipCode" in (params or {})
        assert headers and "X-Api-Key" in headers
        return FakeResponse(status_code=200, json_data=json_data)

    monkeypatch.setattr(app, "requests", types.SimpleNamespace(get=fake_get))

    result = app.fetch_or_cache_zip("75701", api_key="dummy-key")

    assert result["ZipCode"] == 75701
    assert result["City"] == "Tyler"
    assert result["County"] == "Smith"
    assert result["State"] == "TX"
    assert result["AverageRent"] == 1800
    assert result["MedianRent"] == 1750

    # verify it was cached
    assert len(app.collection.docs) == 1
    assert app.collection.docs[0]["ZipCode"] == 75701


def test_fetch_or_cache_zip_api_error_status(monkeypatch):
    """
    Case: RentCast returns a non-200 HTTP status.
    Expectation:
      - Function returns an error dict containing the status code.
    """
    def fake_get(url, headers=None, params=None):
        return FakeResponse(status_code=500, json_data=None, text="Server error")

    monkeypatch.setattr(app, "requests", types.SimpleNamespace(get=fake_get))

    result = app.fetch_or_cache_zip("00000", api_key="dummy")

    assert "error" in result
    assert "500" in result["error"]


def test_fetch_or_cache_zip_no_data(monkeypatch):
    """
    Case: RentCast returns HTTP 200 but an empty list.
    Expectation:
      - Function returns {"error": "No data found for that ZIP."}
    """
    def fake_get(url, headers=None, params=None):
        return FakeResponse(status_code=200, json_data=[])

    monkeypatch.setattr(app, "requests", types.SimpleNamespace(get=fake_get))

    result = app.fetch_or_cache_zip("00000", api_key="dummy")

    assert result == {"error": "No data found for that ZIP."}


# -------------------------------------------------------------------
# Flask test client fixture
# -------------------------------------------------------------------
@pytest.fixture
def client():
    app.app.config["TESTING"] = True
    with app.app.test_client() as client:
        yield client


# -------------------------------------------------------------------
# Unit tests for auth + routes (login, signup, home, API)
# -------------------------------------------------------------------
def test_login_success_redirects_home(client):
    """
    Case: Correct username/password.
    Expectation:
      - 302 redirect to /home.
    """
    user_doc = {
        "_id": "user1",
        "username": "maddy",
        "password": "secret",
        "api_key": "api-key-123",
    }
    app.users_collection.users = {"maddy": user_doc}

    resp = client.post(
        "/", data={"username": "maddy", "password": "secret"}, follow_redirects=False
    )

    assert resp.status_code == 302
    assert "/home" in resp.headers["Location"]


def test_login_invalid_credentials_returns_error_context(client):
    """
    Case: Wrong username/password.
    Expectation:
      - Renders LoginHibbs template with an error (no redirect).
    """
    resp = client.post(
        "/", data={"username": "wrong", "password": "nope"}, follow_redirects=True
    )

    body = resp.data.decode()
    assert resp.status_code == 200
    assert "TEMPLATE:LoginHibbs.html" in body
    assert "Invalid credentials!" in body


def test_signup_missing_username_shows_error(client):
    """
    Case: Signup with empty username.
    Expectation:
      - Stay on SignUp.html template with 'Username is required!' error.
    """
    resp = client.post("/signup", data={
        "username": "",
        "password": "pw",
        "confirm_password": "pw",
        "api_key": "key",
        "security_question": "pet",
        "security_answer": "fluffy",
    })

    body = resp.data.decode()
    assert resp.status_code == 200
    assert "TEMPLATE:SignUp.html" in body
    assert "Username is required!" in body


def test_home_requires_login(client):
    """
    Case: Access /home without being logged in.
    Expectation:
      - 302 redirect back to login ("/").
    """
    resp = client.get("/home")

    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/")  # login route is "/"


def test_api_search_zip_missing_api_key(client):
    """
    Case: Call /api/search_zip/<zip> without api_key in session.
    Expectation:
      - HTTP 403 with error JSON.
    """
    resp = client.get("/api/search_zip/75701")
    assert resp.status_code == 403
    data = resp.get_json()
    assert data["error"] == "Missing API key"


# -------------------------------------------------------------------
# Forgot password 2-step flow tests
# -------------------------------------------------------------------
def test_forgot_password_lookup_missing_username_shows_error(client):
    """
    STEP 1: lookup
    Case: no username provided.
    Expectation:
      - ForgotPassword template with 'Please enter your username.' and show_reset=False.
    """
    resp = client.post("/forgot_password", data={
        "step": "lookup",
        "username": "",
    })

    body = resp.data.decode()
    assert resp.status_code == 200
    assert "TEMPLATE:ForgotPassword.html" in body
    assert "Please enter your username." in body
    assert "show_reset': False" in body  # from context dict


def test_forgot_password_lookup_valid_username_shows_security_question(client):
    """
    STEP 1: lookup
    Case: valid existing username.
    Expectation:
      - ForgotPassword template with show_reset=True and correct question_text.
    """
    user_doc = {
        "_id": "user1",
        "username": "maddy",
        "password": "oldpw",
        "api_key": "key",
        "security_question": "pet",
        "security_answer": "Fluffy",
    }
    app.users_collection.users = {"maddy": user_doc}

    resp = client.post("/forgot_password", data={
        "step": "lookup",
        "username": "maddy",
    })

    body = resp.data.decode()
    assert resp.status_code == 200
    assert "TEMPLATE:ForgotPassword.html" in body
    # Text from SECURITY_QUESTIONS["pet"]
    assert "What is the name of your first pet?" in body
    assert "show_reset': True" in body


def test_forgot_password_reset_wrong_security_answer_shows_error(client):
    """
    STEP 2: reset
    Case: wrong security answer.
    Expectation:
      - ForgotPassword template with 'Security answer is incorrect.' and show_reset=True.
    """
    user_doc = {
        "_id": "user1",
        "username": "maddy",
        "password": "oldpw",
        "api_key": "key",
        "security_question": "pet",
        "security_answer": "Fluffy",
    }
    app.users_collection.users = {"maddy": user_doc}

    resp = client.post("/forgot_password", data={
        "step": "reset",
        "username": "maddy",
        "security_answer": "Wrong",
        "new_password": "newpw",
        "confirm_password": "newpw",
    })

    body = resp.data.decode()
    assert resp.status_code == 200
    assert "TEMPLATE:ForgotPassword.html" in body
    assert "Security answer is incorrect." in body
    assert "show_reset': True" in body


def test_forgot_password_reset_password_mismatch_shows_error(client):
    """
    STEP 2: reset
    Case: security answer correct but passwords do not match.
    Expectation:
      - ForgotPassword template with 'Passwords do not match.' and show_reset=True.
    """
    user_doc = {
        "_id": "user1",
        "username": "maddy",
        "password": "oldpw",
        "api_key": "key",
        "security_question": "pet",
        "security_answer": "Fluffy",
    }
    app.users_collection.users = {"maddy": user_doc}

    resp = client.post("/forgot_password", data={
        "step": "reset",
        "username": "maddy",
        "security_answer": "Fluffy",
        "new_password": "newpw1",
        "confirm_password": "newpw2",
    })

    body = resp.data.decode()
    assert resp.status_code == 200
    assert "TEMPLATE:ForgotPassword.html" in body
    assert "Passwords do not match." in body
    assert "show_reset': True" in body


def test_forgot_password_reset_success_updates_password_and_shows_success(client):
    """
    STEP 2: reset
    Case: correct security answer and matching new passwords.
    Expectation:
      - users_collection.update_one called with new password.
      - ForgotPassword template with success message and show_reset=False.
    """
    user_doc = {
        "_id": "user1",
        "username": "maddy",
        "password": "oldpw",
        "api_key": "key",
        "security_question": "pet",
        "security_answer": "Fluffy",
    }
    app.users_collection.users = {"maddy": user_doc}

    resp = client.post("/forgot_password", data={
        "step": "reset",
        "username": "maddy",
        "security_answer": "Fluffy",
        "new_password": "newpw",
        "confirm_password": "newpw",
    })

    body = resp.data.decode()
    assert resp.status_code == 200
    assert "TEMPLATE:ForgotPassword.html" in body
    assert "Password updated successfully. You can now log in." in body
    assert "show_reset': False" in body

    # Confirm update_one recorded a password change
    assert len(app.users_collection.updated) == 1
    query, update = app.users_collection.updated[0]
    assert query == {"_id": "user1"}
    assert update == {"$set": {"password": "newpw"}}
