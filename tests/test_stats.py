from database import db


def _add_expense(user_id, amount, category):
    conn = db.get_db()
    try:
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, "2026-01-01", "test"),
        )
        conn.commit()
    finally:
        conn.close()


def test_demo_user_summary(demo_user_id):
    summary = db.get_expense_summary(demo_user_id)
    assert summary["total_spent"] == 6398.00
    assert summary["transaction_count"] == 8
    assert summary["top_category"] == "Shopping"


def test_empty_user_summary(empty_user_id):
    summary = db.get_expense_summary(empty_user_id)
    assert summary == {"total_spent": 0.0, "transaction_count": 0, "top_category": None}
    assert isinstance(summary["total_spent"], float)


def test_user_isolation(demo_user_id, empty_user_id):
    before = db.get_expense_summary(demo_user_id)
    _add_expense(empty_user_id, 99999.0, "Travel")
    assert db.get_expense_summary(demo_user_id) == before
    other = db.get_expense_summary(empty_user_id)
    assert other["total_spent"] == 99999.0
    assert other["transaction_count"] == 1
    assert other["top_category"] == "Travel"


def test_tie_break_is_alphabetical(empty_user_id):
    _add_expense(empty_user_id, 100.0, "Zebra")
    _add_expense(empty_user_id, 100.0, "Alpha")
    for _ in range(3):
        assert db.get_expense_summary(empty_user_id)["top_category"] == "Alpha"
