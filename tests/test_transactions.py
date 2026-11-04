from database import db


def test_newest_first(demo_user_id):
    rows = db.get_recent_expenses(demo_user_id)
    assert rows[0]["description"] == "Dinner out"
    dates = [r["date"] for r in rows]
    assert dates == sorted(dates, reverse=True)
    assert set(rows[0]) == {"date", "description", "category", "amount"}


def test_limit_respected(demo_user_id):
    assert len(db.get_recent_expenses(demo_user_id, limit=3)) == 3


def test_no_leak_between_users(demo_user_id, empty_user_id):
    before = db.get_recent_expenses(demo_user_id)
    conn = db.get_db()
    try:
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (empty_user_id, 99.0, "Food", "2099-01-01", "Other user"),
        )
        conn.commit()
    finally:
        conn.close()
    assert db.get_recent_expenses(demo_user_id) == before
    assert [r["description"] for r in db.get_recent_expenses(empty_user_id)] == ["Other user"]


def test_empty_user(empty_user_id):
    assert db.get_recent_expenses(empty_user_id) == []
