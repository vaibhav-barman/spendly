from datetime import date, timedelta

import pytest
from werkzeug.security import generate_password_hash

from database import db

TODAY = date.today().isoformat()
TOMORROW = (date.today() + timedelta(days=1)).isoformat()


# ------------------------------------------------------------- helpers

def _fetch_row(expense_id):
    conn = db.get_db()
    try:
        return conn.execute(
            "SELECT * FROM expenses WHERE id = ?", (expense_id,)
        ).fetchone()
    finally:
        conn.close()


def _count_all():
    conn = db.get_db()
    try:
        return conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
    finally:
        conn.close()


def _count_user(user_id):
    conn = db.get_db()
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
    finally:
        conn.close()


def _snapshot(expense_id):
    row = _fetch_row(expense_id)
    return (row["user_id"], row["amount"], row["category"], row["date"],
            row["description"])


def _url(expense_id):
    return f"/expenses/{expense_id}/edit"


def _post(client, expense_id, **overrides):
    data = {
        "amount": "99.50",
        "category": "Transport",
        "date": TODAY,
        "description": "Edited description",
    }
    data.update(overrides)
    # A None override means "leave this field out of the form entirely".
    data = {k: v for k, v in data.items() if v is not None}
    return client.post(_url(expense_id), data=data)


@pytest.fixture
def other_user_id(app):
    """A second user (user B) distinct from the demo user, with no expenses."""
    conn = db.get_db()
    try:
        cur = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Other User", "other@spendly.com", generate_password_hash("other123")),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


@pytest.fixture
def groceries_id(demo_user_id):
    conn = db.get_db()
    try:
        return conn.execute(
            "SELECT id FROM expenses WHERE user_id = ? AND description = ?",
            (demo_user_id, "Weekly groceries"),
        ).fetchone()["id"]
    finally:
        conn.close()


@pytest.fixture
def owned_id(empty_user_id):
    """An expense with fully controlled values owned by empty_user_id."""
    return db.create_expense(empty_user_id, 200.0, "Food", "2024-03-10", "Original")


# ---------------------------------------------------------------- auth

def test_get_logged_out_redirects_to_login(client, groceries_id):
    resp = client.get(_url(groceries_id))
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_get_logged_out_nonexistent_id_redirects_to_login(client):
    resp = client.get(_url(1))
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_post_logged_out_redirects_and_changes_nothing(client, groceries_id):
    before = _snapshot(groceries_id)
    resp = _post(client, groceries_id)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")
    assert _snapshot(groceries_id) == before


def test_stale_session_redirects_to_login(client, login, groceries_id):
    login(99999)
    resp = client.get(_url(groceries_id))
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")
    login(99999)
    resp = _post(client, groceries_id)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


# ------------------------------------------------------- profile link

def test_profile_rows_have_edit_links(client, login, demo_user_id):
    login(demo_user_id)
    html = client.get("/profile").get_data(as_text=True)
    conn = db.get_db()
    try:
        rows = conn.execute(
            "SELECT id FROM expenses WHERE user_id = ?", (demo_user_id,)
        ).fetchall()
    finally:
        conn.close()
    assert rows
    # The profile shows recent transactions; at least one edit link must exist
    # and every link must point to one of this user's expenses.
    own_ids = {r["id"] for r in rows}
    found = [i for i in own_ids if f'href="{_url(i)}"' in html]
    assert found, "Expected at least one Edit link on the profile page"
    assert "Edit" in html


def test_profile_edit_link_for_controlled_row_opens_edit_page(
    client, login, empty_user_id, owned_id
):
    login(empty_user_id)
    html = client.get("/profile").get_data(as_text=True)
    assert f'href="{_url(owned_id)}"' in html
    assert "aria-label" in html  # accessible label on the edit link
    resp = client.get(_url(owned_id))
    assert resp.status_code == 200


# ---------------------------------------------------------------- form

def test_get_form_prefilled_and_headed_edit(client, login, demo_user_id, groceries_id):
    login(demo_user_id)
    resp = client.get(_url(groceries_id))
    html = resp.get_data(as_text=True)
    row = _fetch_row(groceries_id)
    assert resp.status_code == 200
    assert "Edit expense" in html
    assert "Save changes" in html
    assert 'value="450' in html
    assert '<option value="Food" selected>' in html
    assert f'value="{row["date"]}"' in html
    assert "Weekly groceries" in html
    assert f'action="{_url(groceries_id)}"' in html
    assert 'href="/profile"' in html  # Cancel link
    assert "₹" in html
    assert "$" not in html


def test_get_form_prefill_for_controlled_row(client, login, empty_user_id, owned_id):
    login(empty_user_id)
    html = client.get(_url(owned_id)).get_data(as_text=True)
    assert 'value="200' in html
    assert '<option value="Food" selected>' in html
    assert 'value="2024-03-10"' in html
    assert "Original" in html


# ------------------------------------------------------------- success

def test_valid_post_redirects_to_profile_and_updates_db(
    client, login, empty_user_id, owned_id
):
    login(empty_user_id)
    resp = _post(
        client, owned_id, amount="321.75", category="Health",
        date="2024-04-05", description="Pharmacy",
    )
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/profile")
    row = _fetch_row(owned_id)
    assert row["amount"] == pytest.approx(321.75)
    assert row["category"] == "Health"
    assert row["date"] == "2024-04-05"
    assert row["description"] == "Pharmacy"
    assert row["user_id"] == empty_user_id


def test_profile_shows_new_values_total_and_breakdown(
    client, login, empty_user_id, owned_id
):
    login(empty_user_id)
    before = client.get("/profile").get_data(as_text=True)
    assert "₹200.00" in before
    assert "Original" in before

    _post(client, owned_id, amount="1234.50", category="Transport",
          date="2024-04-05", description="Zebra cab")
    html = client.get("/profile").get_data(as_text=True)
    assert "Zebra cab" in html
    assert "Original" not in html
    assert "₹1,234.50" in html
    assert "2024-04-05" in html
    assert "Transport" in html
    assert "100%" in html  # sole category in breakdown


def test_edit_demo_expense_updates_total(client, login, demo_user_id, groceries_id):
    login(demo_user_id)
    # 450.00 -> 552.00 raises the seeded 6,398.00 total by 102.00
    _post(client, groceries_id, amount="552.00", category="Food",
          description="Weekly groceries")
    html = client.get("/profile").get_data(as_text=True)
    assert "₹6,500.00" in html


def test_edit_does_not_create_new_row(
    client, login, empty_user_id, owned_id, demo_user_id
):
    login(empty_user_id)
    total_before = _count_all()
    user_before = _count_user(empty_user_id)
    _post(client, owned_id)
    assert _count_all() == total_before
    assert _count_user(empty_user_id) == user_before


@pytest.mark.parametrize("blank", ["", "   "])
def test_clearing_description_saves_blank_not_none(
    client, login, empty_user_id, owned_id, blank
):
    login(empty_user_id)
    resp = _post(client, owned_id, description=blank)
    assert resp.status_code == 302
    assert _fetch_row(owned_id)["description"] in ("", None)
    assert "None" not in client.get("/profile").get_data(as_text=True)
    assert "None" not in client.get(_url(owned_id)).get_data(as_text=True)


def test_amount_rounds_half_up_to_two_places(client, login, empty_user_id, owned_id):
    login(empty_user_id)
    resp = _post(client, owned_id, amount="12.345")
    assert resp.status_code == 302
    assert _fetch_row(owned_id)["amount"] == pytest.approx(12.35)


def test_today_date_accepted(client, login, empty_user_id, owned_id):
    login(empty_user_id)
    assert _post(client, owned_id, date=TODAY).status_code == 302
    assert _fetch_row(owned_id)["date"] == TODAY


def test_minimum_date_accepted(client, login, empty_user_id, owned_id):
    login(empty_user_id)
    assert _post(client, owned_id, date="2000-01-01").status_code == 302
    assert _fetch_row(owned_id)["date"] == "2000-01-01"


def test_description_200_chars_accepted(client, login, empty_user_id, owned_id):
    login(empty_user_id)
    assert _post(client, owned_id, description="x" * 200).status_code == 302
    assert _fetch_row(owned_id)["description"] == "x" * 200


# ---------------------------------------------------------- validation

@pytest.mark.parametrize("amount", ["0", "-5", "abc", "nan", "inf", ""])
def test_bad_amount_rejected_and_row_unchanged(
    client, login, empty_user_id, owned_id, amount
):
    login(empty_user_id)
    before = _snapshot(owned_id)
    resp = _post(client, owned_id, amount=amount)
    assert resp.status_code == 200
    assert "Enter a valid amount greater than 0." in resp.get_data(as_text=True)
    assert _snapshot(owned_id) == before


@pytest.mark.parametrize("category", ["Travel", "food", ""])
def test_bad_category_rejected_and_row_unchanged(
    client, login, empty_user_id, owned_id, category
):
    login(empty_user_id)
    before = _snapshot(owned_id)
    resp = _post(client, owned_id, category=category)
    assert resp.status_code == 200
    assert "Choose a category." in resp.get_data(as_text=True)
    assert _snapshot(owned_id) == before


def test_missing_category_rejected(client, login, empty_user_id, owned_id):
    login(empty_user_id)
    before = _snapshot(owned_id)
    resp = _post(client, owned_id, category=None)
    assert resp.status_code == 200
    assert "Choose a category." in resp.get_data(as_text=True)
    assert _snapshot(owned_id) == before


@pytest.mark.parametrize(
    "bad_date", ["2026-13-45", "abc", "", TOMORROW, "1999-12-31"]
)
def test_bad_date_rejected_and_row_unchanged(
    client, login, empty_user_id, owned_id, bad_date
):
    login(empty_user_id)
    before = _snapshot(owned_id)
    resp = _post(client, owned_id, date=bad_date)
    assert resp.status_code == 200
    assert (
        "Enter a valid date that is not in the future."
        in resp.get_data(as_text=True)
    )
    assert _snapshot(owned_id) == before


def test_description_201_chars_rejected_and_row_unchanged(
    client, login, empty_user_id, owned_id
):
    login(empty_user_id)
    before = _snapshot(owned_id)
    resp = _post(client, owned_id, description="x" * 201)
    assert resp.status_code == 200
    assert "Description must be 200 characters or fewer." in resp.get_data(as_text=True)
    assert _snapshot(owned_id) == before


def test_failed_submit_repopulates_form_in_edit_mode(
    client, login, empty_user_id, owned_id
):
    login(empty_user_id)
    resp = _post(
        client, owned_id, amount="oops", category="Health",
        date="2024-05-06", description='<b>"quoted"</b>',
    )
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert 'value="oops"' in html
    assert '<option value="Health" selected>' in html
    assert 'value="2024-05-06"' in html
    assert "&lt;b&gt;" in html
    assert "<b>" not in html
    assert 'role="alert"' in html
    # still the edit form, posting back to the same expense
    assert "Edit expense" in html
    assert f'action="{_url(owned_id)}"' in html


# ----------------------------------------------------------- not found

def test_nonexistent_expense_returns_404(client, login, demo_user_id):
    login(demo_user_id)
    assert client.get(_url(9999)).status_code == 404
    assert _post(client, 9999).status_code == 404


# ----------------------------------------------------------- ownership

def test_other_users_expense_get_returns_404(
    client, login, other_user_id, groceries_id
):
    login(other_user_id)
    resp = client.get(_url(groceries_id))
    assert resp.status_code == 404
    assert "Weekly groceries" not in resp.get_data(as_text=True)


def test_other_users_expense_post_returns_404_and_unchanged(
    client, login, other_user_id, groceries_id
):
    before = _snapshot(groceries_id)
    login(other_user_id)
    resp = _post(client, groceries_id, amount="1", description="hijacked")
    assert resp.status_code == 404
    assert _snapshot(groceries_id) == before


def test_foreign_and_missing_expense_responses_match(
    client, login, other_user_id, groceries_id
):
    login(other_user_id)
    assert (
        client.get(_url(groceries_id)).status_code
        == client.get(_url(9999)).status_code
        == 404
    )


def test_forged_user_id_field_does_not_transfer_ownership(
    client, login, empty_user_id, owned_id, demo_user_id
):
    login(empty_user_id)
    client.post(
        _url(owned_id),
        data={
            "amount": "10", "category": "Food", "date": TODAY,
            "description": "forged", "user_id": str(demo_user_id),
        },
    )
    assert _fetch_row(owned_id)["user_id"] == empty_user_id


def test_other_users_profile_has_no_edit_link_for_foreign_expense(
    client, login, other_user_id, groceries_id
):
    login(other_user_id)
    html = client.get("/profile").get_data(as_text=True)
    assert f'href="{_url(groceries_id)}"' not in html


# --------------------------------------------------------- navigation

def test_cancel_link_goes_to_profile_without_saving(
    client, login, empty_user_id, owned_id
):
    login(empty_user_id)
    before = _snapshot(owned_id)
    html = client.get(_url(owned_id)).get_data(as_text=True)
    assert 'href="/profile"' in html
    resp = client.get("/profile")
    assert resp.status_code == 200
    assert _snapshot(owned_id) == before


def test_add_expense_page_still_shows_add_wording(client, login, demo_user_id):
    login(demo_user_id)
    resp = client.get("/expenses/add")
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "Add expense" in html
    assert "Edit expense" not in html
    assert "Save changes" not in html
    assert 'action="/expenses/add"' in html or "action=" in html


def test_add_expense_still_creates_row(client, login, empty_user_id):
    login(empty_user_id)
    resp = client.post(
        "/expenses/add",
        data={"amount": "10", "category": "Food", "date": TODAY,
              "description": "new"},
    )
    assert resp.status_code == 302
    assert _count_user(empty_user_id) == 1


def test_delete_get_not_allowed(client):
    assert client.get("/expenses/1/delete").status_code == 405


# ----------------------------------------------------------------- SQL

def test_sql_looking_description_stored_literally(
    client, login, empty_user_id, owned_id
):
    login(empty_user_id)
    payload = "'); DROP TABLE expenses;--"
    before = _count_all()
    resp = _post(client, owned_id, description=payload)
    assert resp.status_code == 302
    assert _fetch_row(owned_id)["description"] == payload
    assert _count_all() == before


# ------------------------------------------------------ helper-level

class TestGetExpenseHelper:
    def test_returns_dict_for_owner(self, empty_user_id, owned_id):
        result = db.get_expense(empty_user_id, owned_id)
        assert result is not None
        assert result["id"] == owned_id
        assert result["amount"] == pytest.approx(200.0)
        assert result["category"] == "Food"
        assert result["date"] == "2024-03-10"
        assert result["description"] == "Original"

    def test_returns_none_for_other_user(self, other_user_id, owned_id):
        assert db.get_expense(other_user_id, owned_id) is None

    def test_returns_none_for_missing_id(self, empty_user_id):
        assert db.get_expense(empty_user_id, 9999) is None


class TestUpdateExpenseHelper:
    def test_updates_and_returns_true(self, empty_user_id, owned_id):
        ok = db.update_expense(
            empty_user_id, owned_id, 55.25, "Bills", "2024-06-01", "Power"
        )
        assert ok is True
        got = db.get_expense(empty_user_id, owned_id)
        assert got["amount"] == pytest.approx(55.25)
        assert got["category"] == "Bills"
        assert got["date"] == "2024-06-01"
        assert got["description"] == "Power"

    def test_other_user_returns_false_and_unchanged(
        self, empty_user_id, other_user_id, owned_id
    ):
        before = _snapshot(owned_id)
        ok = db.update_expense(
            other_user_id, owned_id, 1.0, "Bills", "2024-06-01", "x"
        )
        assert ok is False
        assert _snapshot(owned_id) == before

    def test_missing_id_returns_false(self, empty_user_id):
        assert db.update_expense(
            empty_user_id, 9999, 1.0, "Food", "2024-06-01", "x"
        ) is False

    def test_does_not_add_rows(self, empty_user_id, owned_id):
        before = _count_all()
        db.update_expense(empty_user_id, owned_id, 1.0, "Food", "2024-06-01", "x")
        assert _count_all() == before
