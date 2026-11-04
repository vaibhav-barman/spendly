from datetime import date, timedelta

import pytest

from database import db

TODAY = date.today().isoformat()
TOMORROW = (date.today() + timedelta(days=1)).isoformat()


def _count_expenses(user_id):
    conn = db.get_db()
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
    finally:
        conn.close()


def _latest_expense(user_id):
    conn = db.get_db()
    try:
        return conn.execute(
            "SELECT * FROM expenses WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()


def _post(client, **overrides):
    data = {
        "amount": "250.50",
        "category": "Food",
        "date": TODAY,
        "description": "Lunch",
    }
    data.update(overrides)
    # A None override means "leave this field out of the form entirely".
    data = {k: v for k, v in data.items() if v is not None}
    return client.post("/expenses/add", data=data)


# ---------------------------------------------------------------- auth

def test_get_logged_out_redirects_to_login(client):
    resp = client.get("/expenses/add")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_post_logged_out_redirects_and_inserts_nothing(client, demo_user_id):
    before = _count_expenses(demo_user_id)
    resp = _post(client)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")
    assert _count_expenses(demo_user_id) == before


def test_stale_session_is_cleared_on_get_and_post(client, login):
    login(99999)
    resp = client.get("/expenses/add")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")
    with client.session_transaction() as sess:
        assert "user_id" not in sess

    login(99999)
    resp = _post(client)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")
    with client.session_transaction() as sess:
        assert "user_id" not in sess


# ---------------------------------------------------------------- form

def test_get_form_renders(client, login, demo_user_id):
    login(demo_user_id)
    resp = client.get("/expenses/add")
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert f'value="{TODAY}"' in html
    assert f'max="{TODAY}"' in html
    for category in db.CATEGORIES:
        assert f'<option value="{category}"' in html
    assert "₹" in html
    assert "$" not in html
    assert "style=" not in html
    assert 'href="/profile"' in html  # Cancel link


# ------------------------------------------------------------- success

def test_valid_post_redirects_and_shows_on_profile(client, login, demo_user_id):
    login(demo_user_id)
    resp = _post(client, description="Zebra lunch", amount="777.25")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/profile")

    html = client.get("/profile").get_data(as_text=True)
    assert "Zebra lunch" in html
    assert "₹777.25" in html
    assert TODAY in html


def test_history_orders_by_date_so_today_sorts_above_older(
    client, login, empty_user_id
):
    # Seeded demo rows are spread across the current month (some after today),
    # so compare against a row we control instead of seed data.
    db.create_expense(empty_user_id, 5.0, "Other", "2000-01-01", "Ancient purchase")
    login(empty_user_id)
    _post(client, description="Fresh purchase")
    html = client.get("/profile").get_data(as_text=True)
    assert html.index("Fresh purchase") < html.index("Ancient purchase")


def test_stats_reflect_new_expense_for_empty_user(client, login, empty_user_id):
    login(empty_user_id)
    _post(client, amount="1234.50", category="Transport")
    html = client.get("/profile").get_data(as_text=True)
    assert "₹1,234.50" in html
    assert "No transactions yet." not in html
    assert "Transport" in html
    assert "100%" in html  # sole category in the breakdown


def test_stats_reflect_new_expense_for_demo_user(client, login, demo_user_id):
    login(demo_user_id)
    _post(client, amount="102.00")
    html = client.get("/profile").get_data(as_text=True)
    assert "₹6,500.00" in html  # 6,398.00 seeded + 102.00


def test_row_belongs_to_session_user_and_is_private(
    client, login, demo_user_id, empty_user_id
):
    login(demo_user_id)
    _post(client, description="Private purchase")
    row = _latest_expense(demo_user_id)
    assert row["description"] == "Private purchase"
    assert row["user_id"] == demo_user_id

    login(empty_user_id)
    html = client.get("/profile").get_data(as_text=True)
    assert "Private purchase" not in html


def test_forged_user_id_field_is_ignored(client, login, demo_user_id, empty_user_id):
    login(demo_user_id)
    before_empty = _count_expenses(empty_user_id)
    client.post(
        "/expenses/add",
        data={
            "amount": "10",
            "category": "Food",
            "date": TODAY,
            "description": "forged",
            "user_id": str(empty_user_id),
        },
    )
    assert _count_expenses(empty_user_id) == before_empty
    assert _latest_expense(demo_user_id)["description"] == "forged"


def test_blank_description_saved_as_empty_string(client, login, empty_user_id):
    login(empty_user_id)
    resp = _post(client, description="   ")
    assert resp.status_code == 302
    assert _latest_expense(empty_user_id)["description"] == ""
    assert "None" not in client.get("/profile").get_data(as_text=True)


def test_missing_description_field_is_ok(client, login, empty_user_id):
    login(empty_user_id)
    resp = _post(client, description=None)
    assert resp.status_code == 302
    assert _latest_expense(empty_user_id)["description"] == ""


def test_description_is_stripped(client, login, empty_user_id):
    login(empty_user_id)
    _post(client, description="  padded  ")
    assert _latest_expense(empty_user_id)["description"] == "padded"


# ---------------------------------------------------------- validation

@pytest.mark.parametrize(
    "amount",
    ["0", "-5", "abc", "nan", "inf", "-inf", "", "10000000.01", "0.004", "1e999999"],
)
def test_bad_amount_rejected(client, login, empty_user_id, amount):
    login(empty_user_id)
    resp = _post(client, amount=amount)
    assert resp.status_code == 200
    assert "Enter a valid amount greater than 0." in resp.get_data(as_text=True)
    assert _count_expenses(empty_user_id) == 0


def test_missing_amount_field_rejected(client, login, empty_user_id):
    login(empty_user_id)
    resp = _post(client, amount=None)
    assert resp.status_code == 200
    assert _count_expenses(empty_user_id) == 0


def test_amount_rounds_half_up_to_two_places(client, login, empty_user_id):
    login(empty_user_id)
    _post(client, amount="12.345")
    assert _latest_expense(empty_user_id)["amount"] == 12.35


def test_amount_at_upper_limit_accepted(client, login, empty_user_id):
    login(empty_user_id)
    resp = _post(client, amount="10000000")
    assert resp.status_code == 302
    assert _latest_expense(empty_user_id)["amount"] == 10000000.0


@pytest.mark.parametrize("category", ["Travel", "food", ""])
def test_bad_category_rejected(client, login, empty_user_id, category):
    login(empty_user_id)
    resp = _post(client, category=category)
    assert resp.status_code == 200
    assert "Choose a category." in resp.get_data(as_text=True)
    assert _count_expenses(empty_user_id) == 0


def test_missing_category_field_rejected(client, login, empty_user_id):
    login(empty_user_id)
    resp = _post(client, category=None)
    assert resp.status_code == 200
    assert "Choose a category." in resp.get_data(as_text=True)
    assert _count_expenses(empty_user_id) == 0


@pytest.mark.parametrize("bad_date", ["2026-13-45", "abc", "", TOMORROW])
def test_bad_date_rejected(client, login, empty_user_id, bad_date):
    login(empty_user_id)
    resp = _post(client, date=bad_date)
    assert resp.status_code == 200
    assert (
        "Enter a valid date that is not in the future."
        in resp.get_data(as_text=True)
    )
    assert _count_expenses(empty_user_id) == 0


def test_today_is_accepted(client, login, empty_user_id):
    login(empty_user_id)
    assert _post(client, date=TODAY).status_code == 302


def test_unpadded_date_is_normalised(client, login, empty_user_id):
    login(empty_user_id)
    d = date.today().replace(day=1)
    _post(client, date=f"{d.year}-{d.month}-{d.day}")
    assert _latest_expense(empty_user_id)["date"] == d.isoformat()


def test_description_length_limit(client, login, empty_user_id):
    login(empty_user_id)
    resp = _post(client, description="x" * 201)
    assert resp.status_code == 200
    assert "Description must be 200 characters or fewer." in resp.get_data(as_text=True)
    assert _count_expenses(empty_user_id) == 0

    resp = _post(client, description="x" * 200)
    assert resp.status_code == 302
    assert _count_expenses(empty_user_id) == 1


def test_failed_submit_repopulates_form(client, login, empty_user_id):
    login(empty_user_id)
    resp = _post(
        client,
        amount="oops",
        category="Health",
        date=TODAY,
        description='<b>"quoted"</b>',
    )
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert 'value="oops"' in html
    assert '<option value="Health" selected>' in html
    assert f'value="{TODAY}"' in html
    assert "&lt;b&gt;" in html  # description is escaped, not rendered
    assert "<b>" not in html
    assert 'role="alert"' in html


def test_sql_looking_description_stored_literally(client, login, demo_user_id):
    login(demo_user_id)
    before = _count_expenses(demo_user_id)
    payload = "'); DROP TABLE expenses;--"
    resp = _post(client, description=payload)
    assert resp.status_code == 302
    assert _latest_expense(demo_user_id)["description"] == payload
    assert _count_expenses(demo_user_id) == before + 1


# --------------------------------------------------------- navigation

def test_profile_and_nav_link_to_add_expense(client, login, demo_user_id):
    login(demo_user_id)
    html = client.get("/profile").get_data(as_text=True)
    assert html.count('href="/expenses/add"') == 2  # nav link + profile button


def test_nav_marks_add_expense_active(client, login, demo_user_id):
    login(demo_user_id)
    html = client.get("/expenses/add").get_data(as_text=True)
    assert 'href="/expenses/add" class="active" aria-current="page"' in html


# ------------------------------------------------- review hardening

@pytest.mark.parametrize("old_date", ["1999-12-31", "0001-01-01"])
def test_date_before_minimum_rejected(client, login, empty_user_id, old_date):
    login(empty_user_id)
    resp = _post(client, date=old_date)
    assert resp.status_code == 200
    assert "Enter a valid date that is not in the future." in resp.get_data(as_text=True)
    assert _count_expenses(empty_user_id) == 0


def test_minimum_date_accepted(client, login, empty_user_id):
    login(empty_user_id)
    resp = _post(client, date="2000-01-01")
    assert resp.status_code == 302
    assert _latest_expense(empty_user_id)["date"] == "2000-01-01"


def test_form_date_input_has_min_attribute(client, login, demo_user_id):
    login(demo_user_id)
    html = client.get("/expenses/add").get_data(as_text=True)
    assert 'min="2000-01-01"' in html


def test_oversized_request_body_rejected(client, login, empty_user_id):
    login(empty_user_id)
    resp = _post(client, description="x" * (20 * 1024))
    assert resp.status_code == 413
    assert _count_expenses(empty_user_id) == 0


def test_error_banner_uses_shared_auth_error_class(client, login, empty_user_id):
    login(empty_user_id)
    html = _post(client, amount="0").get_data(as_text=True)
    assert 'class="auth-error" role="alert"' in html


def test_edit_and_delete_stubs_untouched(client):
    assert b"Step 8" in client.get("/expenses/1/edit").data
    assert b"Step 9" in client.get("/expenses/1/delete").data
