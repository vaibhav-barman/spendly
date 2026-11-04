from database.db import get_category_breakdown, get_db


def test_descending_order(demo_user_id):
    totals = [c["total"] for c in get_category_breakdown(demo_user_id)]
    assert totals and totals == sorted(totals, reverse=True)


def test_shopping_first_for_demo(demo_user_id):
    assert get_category_breakdown(demo_user_id)[0]["name"] == "Shopping"


def test_percents_sum_close_to_100(demo_user_id):
    total = sum(c["percent"] for c in get_category_breakdown(demo_user_id))
    assert abs(total - 100) <= 2


def test_empty_user(empty_user_id):
    assert get_category_breakdown(empty_user_id) == []


def test_no_cross_user_leakage(demo_user_id, empty_user_id):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date) VALUES (?, ?, ?, ?)",
            (empty_user_id, 50, "Unique", "2026-01-01"),
        )
        conn.commit()
    finally:
        conn.close()
    assert [c["name"] for c in get_category_breakdown(empty_user_id)] == ["Unique"]
    assert "Unique" not in [c["name"] for c in get_category_breakdown(demo_user_id)]
