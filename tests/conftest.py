import pytest
from werkzeug.security import generate_password_hash

import app as app_module
from database import db


@pytest.fixture
def app(tmp_path, monkeypatch):
    """Flask app bound to a throwaway database seeded with the demo user."""
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    db.seed_db()
    app_module.app.config.update(TESTING=True)
    return app_module.app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def demo_user_id(app):
    conn = db.get_db()
    try:
        return conn.execute(
            "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
        ).fetchone()["id"]
    finally:
        conn.close()


@pytest.fixture
def empty_user_id(app):
    """A second user with no expenses."""
    conn = db.get_db()
    try:
        cur = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Empty User", "empty@spendly.com", generate_password_hash("empty123")),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


@pytest.fixture
def login(client):
    def _login(user_id):
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
    return _login
