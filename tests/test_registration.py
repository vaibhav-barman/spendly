import sqlite3

import pytest
from werkzeug.security import check_password_hash

from database import db


VALID = {
    "name": "New Person",
    "email": "new@example.com",
    "password": "longenough1",
    "confirm_password": "longenough1",
}


def _form(**overrides):
    data = dict(VALID)
    data.update(overrides)
    return data


def _user_count():
    conn = db.get_db()
    try:
        return conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
    finally:
        conn.close()


def _users_by_email(email):
    conn = db.get_db()
    try:
        return conn.execute(
            "SELECT * FROM users WHERE LOWER(email) = LOWER(?)", (email,)
        ).fetchall()
    finally:
        conn.close()


class TestRegisterPage:
    def test_get_register_renders_form(self, client):
        response = client.get("/register")
        assert response.status_code == 200
        for field in (b'name="name"', b'name="email"',
                      b'name="password"', b'name="confirm_password"'):
            assert field in response.data, f"Missing input {field!r}"
        assert b'method="post"' in response.data.lower()

    def test_logged_in_user_redirected_to_profile(self, client, login, demo_user_id):
        login(demo_user_id)
        response = client.get("/register")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/profile")

    def test_logged_in_user_post_redirected_to_profile(self, client, login, demo_user_id):
        login(demo_user_id)
        before = _user_count()
        response = client.post("/register", data=_form())
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/profile")
        assert _user_count() == before


class TestRegisterSuccess:
    def test_valid_registration_redirects_to_login(self, client):
        response = client.post("/register", data=_form())
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")

    def test_valid_registration_creates_user_row(self, client):
        before = _user_count()
        client.post("/register", data=_form())
        assert _user_count() == before + 1
        rows = _users_by_email(VALID["email"])
        assert len(rows) == 1
        assert rows[0]["name"] == VALID["name"]

    def test_password_is_hashed_not_plaintext(self, client):
        client.post("/register", data=_form())
        row = _users_by_email(VALID["email"])[0]
        assert row["password_hash"] != VALID["password"]
        assert VALID["password"] not in row["password_hash"]
        assert check_password_hash(row["password_hash"], VALID["password"])

    def test_login_page_shows_success_flash(self, client):
        response = client.post("/register", data=_form(), follow_redirects=True)
        assert response.status_code == 200
        assert b"Account created. Please sign in." in response.data

    def test_registered_user_can_log_in(self, client):
        client.post("/register", data=_form())
        response = client.post(
            "/login",
            data={"email": VALID["email"], "password": VALID["password"]},
        )
        assert response.status_code == 302, "Expected redirect after login"
        with client.session_transaction() as sess:
            assert "user_id" in sess, "Expected user to be logged in"

    def test_registered_user_wrong_password_cannot_log_in(self, client):
        client.post("/register", data=_form())
        client.post(
            "/login",
            data={"email": VALID["email"], "password": "wrongpassword"},
        )
        with client.session_transaction() as sess:
            assert "user_id" not in sess


class TestRegisterValidation:
    @pytest.mark.parametrize(
        "field", ["name", "email", "password", "confirm_password"]
    )
    def test_empty_field_shows_error_and_no_insert(self, client, field):
        before = _user_count()
        response = client.post("/register", data=_form(**{field: ""}))
        assert response.status_code == 200
        assert b"All fields are required" in response.data
        assert _user_count() == before

    def test_all_fields_empty_shows_error(self, client):
        before = _user_count()
        response = client.post(
            "/register",
            data={"name": "", "email": "", "password": "", "confirm_password": ""},
        )
        assert response.status_code == 200
        assert b"All fields are required" in response.data
        assert _user_count() == before

    def test_short_password_shows_error_and_no_insert(self, client):
        before = _user_count()
        response = client.post(
            "/register", data=_form(password="short7!", confirm_password="short7!")
        )
        assert response.status_code == 200
        assert b"8" in response.data, "Expected error mentioning 8 characters"
        assert b"Account created" not in response.data
        assert _user_count() == before
        assert _users_by_email(VALID["email"]) == []

    def test_password_of_exactly_8_chars_accepted(self, client):
        response = client.post(
            "/register", data=_form(password="exactly8", confirm_password="exactly8")
        )
        assert response.status_code == 302
        assert len(_users_by_email(VALID["email"])) == 1

    def test_mismatched_passwords_shows_error_and_no_insert(self, client):
        before = _user_count()
        response = client.post(
            "/register", data=_form(confirm_password="different123")
        )
        assert response.status_code == 200
        assert b"Passwords do not match" in response.data
        assert _user_count() == before

    @pytest.mark.parametrize(
        "email", ["demo@spendly.com", "DEMO@spendly.com", "Demo@Spendly.com"]
    )
    def test_duplicate_email_case_insensitive_rejected(self, client, email):
        before = _user_count()
        response = client.post("/register", data=_form(email=email))
        assert response.status_code == 200
        assert b"Email already registered" in response.data
        assert _user_count() == before
        assert len(_users_by_email("demo@spendly.com")) == 1

    def test_repeated_registration_creates_single_user(self, client):
        client.post("/register", data=_form())
        response = client.post("/register", data=_form())
        assert response.status_code == 200
        assert b"Email already registered" in response.data
        assert len(_users_by_email(VALID["email"])) == 1

    def test_sql_injection_in_email_stored_literally(self, client):
        payload = "x'); DROP TABLE users;--@example.com"
        client.post("/register", data=_form(email=payload))
        assert _user_count() >= 1, "users table must still exist"


class TestCreateUserHelper:
    def test_create_user_returns_id(self, app):
        user_id = db.create_user("Helper User", "helper@example.com", "password123")
        assert isinstance(user_id, int)
        rows = _users_by_email("helper@example.com")
        assert len(rows) == 1
        assert rows[0]["id"] == user_id

    def test_create_user_hashes_password(self, app):
        db.create_user("Helper User", "helper@example.com", "password123")
        row = _users_by_email("helper@example.com")[0]
        assert row["password_hash"] != "password123"
        assert check_password_hash(row["password_hash"], "password123")

    def test_create_user_duplicate_email_raises_integrity_error(self, app):
        db.create_user("First", "dup@example.com", "password123")
        with pytest.raises(sqlite3.IntegrityError):
            db.create_user("Second", "dup@example.com", "password456")
        assert len(_users_by_email("dup@example.com")) == 1

    def test_create_user_duplicate_of_seeded_email_raises(self, app):
        with pytest.raises(sqlite3.IntegrityError):
            db.create_user("Other", "demo@spendly.com", "password123")
