"""Tests for Step 7: Add expense (GET/POST /expenses/add).

Written from .claude/specs/07-add-expense.md. Fixtures (app, client, login,
demo_user_id, empty_user_id) come from tests/conftest.py.
"""
import re
from datetime import date, timedelta
from types import SimpleNamespace
from urllib.parse import urlparse

import pytest
from flask import url_for

from database import db

CATEGORY_LIST = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]

AMOUNT_ERROR = b"Enter a valid amount greater than 0."
CATEGORY_ERROR = b"Choose a category."
DATE_ERROR = b"Enter a valid date that is not in the future."
DESCRIPTION_ERROR = b"Description must be 200 characters or fewer."


# ------------------------------------------------------------------ #
# Helpers / fixtures                                                  #
# ------------------------------------------------------------------ #

@pytest.fixture
def urls(app):
    with app.test_request_context():
        return SimpleNamespace(
            add=url_for("add_expense"),
            profile=url_for("profile"),
            login=url_for("login"),
        )


@pytest.fixture
def user_client(client, login, empty_user_id):
    """Client logged in as the (expense-less) second user."""
    login(empty_user_id)
    return client


def today_iso():
    return date.today().isoformat()


def days_ago_iso(n):
    return (date.today() - timedelta(days=n)).isoformat()


def form_data(**overrides):
    """A valid form payload; pass key=None to omit that field entirely."""
    data = {
        "amount": "50",
        "category": "Food",
        "date": today_iso(),
        "description": "Lunch",
    }
    data.update(overrides)
    return {k: v for k, v in data.items() if v is not None}


def count_expenses(user_id=None):
    conn = db.get_db()
    try:
        if user_id is None:
            return conn.execute("SELECT COUNT(*) AS c FROM expenses").fetchone()["c"]
        return conn.execute(
            "SELECT COUNT(*) AS c FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchone()["c"]
    finally:
        conn.close()


def last_expense():
    conn = db.get_db()
    try:
        return conn.execute("SELECT * FROM expenses ORDER BY id DESC LIMIT 1").fetchone()
    finally:
        conn.close()


def insert_expense(user_id, amount, category, date_str, description):
    conn = db.get_db()
    try:
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description)"
            " VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, date_str, description),
        )
        conn.commit()
    finally:
        conn.close()


def option_selected(data, value):
    pattern = (
        rb'<option(?=[^>]*value="' + value.encode() + rb'")(?=[^>]*\bselected\b)[^>]*>'
    )
    return re.search(pattern, data) is not None


# ------------------------------------------------------------------ #
# Auth guard                                                          #
# ------------------------------------------------------------------ #

class TestAuthGuard:
    def test_get_logged_out_redirects_to_login(self, client, urls):
        response = client.get(urls.add)
        assert response.status_code == 302, "Logged-out GET should redirect"
        assert urlparse(response.headers["Location"]).path == urls.login

    def test_post_logged_out_redirects_to_login_and_inserts_nothing(self, client, urls):
        before = count_expenses()
        response = client.post(urls.add, data=form_data())
        assert response.status_code == 302, "Logged-out POST should redirect"
        assert urlparse(response.headers["Location"]).path == urls.login
        assert count_expenses() == before, "Logged-out POST must not insert a row"

    def test_get_with_stale_session_clears_session_and_redirects(self, client, login, urls):
        login(999999)
        response = client.get(urls.add)
        assert response.status_code == 302
        assert urlparse(response.headers["Location"]).path == urls.login
        with client.session_transaction() as sess:
            assert "user_id" not in sess, "Stale session should be cleared"

    def test_post_with_stale_session_inserts_nothing_and_redirects(self, client, login, urls):
        login(999999)
        before = count_expenses()
        response = client.post(urls.add, data=form_data())
        assert response.status_code == 302
        assert urlparse(response.headers["Location"]).path == urls.login
        assert count_expenses() == before
        with client.session_transaction() as sess:
            assert "user_id" not in sess


# ------------------------------------------------------------------ #
# GET form                                                            #
# ------------------------------------------------------------------ #

class TestAddForm:
    def test_get_logged_in_returns_form(self, user_client, urls):
        response = user_client.get(urls.add)
        assert response.status_code == 200
        assert b"<form" in response.data
        assert b'method="post"' in response.data.lower()
        assert b"Save expense" in response.data

    def test_get_form_posts_back_to_add_url(self, user_client, urls):
        response = user_client.get(urls.add)
        assert re.search(rb"<form[^>]*>", response.data)
        form_tag = re.search(rb"<form[^>]*>", response.data).group(0)
        # action is either omitted (posts to same URL) or equals the add URL
        assert b"action=" not in form_tag or urls.add.encode() in form_tag

    def test_get_form_lists_all_seven_categories(self, user_client, urls):
        response = user_client.get(urls.add)
        assert b"<select" in response.data
        for category in CATEGORY_LIST:
            assert (
                f'value="{category}"'.encode() in response.data
            ), f"Missing category option {category}"

    def test_get_form_prefills_date_with_today_and_caps_max(self, user_client, urls):
        response = user_client.get(urls.add)
        assert b'type="date"' in response.data
        assert f'value="{today_iso()}"'.encode() in response.data, "Date not prefilled"
        assert f'max="{today_iso()}"'.encode() in response.data, "Date max not today"

    def test_get_form_amount_input_attributes(self, user_client, urls):
        response = user_client.get(urls.add)
        assert b'type="number"' in response.data
        assert b'step="0.01"' in response.data
        assert b'min="0.01"' in response.data

    def test_get_form_description_maxlength_200(self, user_client, urls):
        response = user_client.get(urls.add)
        assert b'maxlength="200"' in response.data

    def test_get_form_uses_rupee_not_dollar(self, user_client, urls):
        response = user_client.get(urls.add)
        assert "₹".encode() in response.data, "Amount label should use the rupee sign"
        assert b"$" not in response.data, "Dollar sign must not appear"
        assert b"USD" not in response.data

    def test_get_form_has_cancel_link_to_profile(self, user_client, urls):
        response = user_client.get(urls.add)
        assert b"Cancel" in response.data
        assert f'href="{urls.profile}"'.encode() in response.data

    def test_get_form_has_no_error_block(self, user_client, urls):
        response = user_client.get(urls.add)
        for message in (AMOUNT_ERROR, CATEGORY_ERROR, DATE_ERROR, DESCRIPTION_ERROR):
            assert message not in response.data

    def test_cancel_target_profile_loads_without_saving(self, user_client, urls, empty_user_id):
        before = count_expenses(empty_user_id)
        response = user_client.get(urls.profile)
        assert response.status_code == 200
        assert count_expenses(empty_user_id) == before


# ------------------------------------------------------------------ #
# Navigation links                                                    #
# ------------------------------------------------------------------ #

class TestNavigation:
    def test_profile_page_has_add_expense_link(self, user_client, urls):
        response = user_client.get(urls.profile)
        assert b"Add expense" in response.data
        assert f'href="{urls.add}"'.encode() in response.data

    def test_nav_bar_has_add_expense_link_on_other_page(self, user_client, urls):
        response = user_client.get(urls.profile)
        assert f'href="{urls.add}"'.encode() in response.data

    def test_nav_bar_has_add_expense_link_on_form_page(self, user_client, urls):
        response = user_client.get(urls.add)
        assert b"Add expense" in response.data
        assert f'href="{urls.add}"'.encode() in response.data

    def test_nav_link_not_shown_when_logged_out(self, client, urls):
        response = client.get(urls.login)
        assert response.status_code == 200
        assert f'href="{urls.add}"'.encode() not in response.data


# ------------------------------------------------------------------ #
# Happy path and DB side effects                                      #
# ------------------------------------------------------------------ #

class TestCreateExpense:
    def test_valid_post_redirects_to_profile(self, user_client, urls):
        response = user_client.post(urls.add, data=form_data())
        assert response.status_code == 302, "Valid POST should redirect (PRG)"
        assert urlparse(response.headers["Location"]).path == urls.profile

    def test_valid_post_inserts_row_with_submitted_values(self, user_client, urls, empty_user_id):
        user_client.post(
            urls.add,
            data=form_data(
                amount="123.45",
                category="Transport",
                date=days_ago_iso(2),
                description="Cab ride",
            ),
        )
        assert count_expenses(empty_user_id) == 1
        row = last_expense()
        assert row["user_id"] == empty_user_id
        assert row["amount"] == pytest.approx(123.45)
        assert row["category"] == "Transport"
        assert row["date"] == days_ago_iso(2)
        assert row["description"] == "Cab ride"

    def test_row_belongs_to_logged_in_user_not_other_users(
        self, user_client, urls, empty_user_id, demo_user_id
    ):
        demo_before = count_expenses(demo_user_id)
        user_client.post(urls.add, data=form_data())
        assert count_expenses(empty_user_id) == 1
        assert count_expenses(demo_user_id) == demo_before

    def test_posted_user_id_field_is_ignored(
        self, user_client, urls, empty_user_id, demo_user_id
    ):
        demo_before = count_expenses(demo_user_id)
        payload = form_data()
        payload["user_id"] = str(demo_user_id)
        user_client.post(urls.add, data=payload)
        assert last_expense()["user_id"] == empty_user_id, "user_id must come from session"
        assert count_expenses(demo_user_id) == demo_before

    def test_demo_user_post_is_saved_for_demo_user(self, client, login, urls, demo_user_id):
        login(demo_user_id)
        before = count_expenses(demo_user_id)
        client.post(urls.add, data=form_data())
        assert count_expenses(demo_user_id) == before + 1
        assert last_expense()["user_id"] == demo_user_id

    @pytest.mark.parametrize("category", CATEGORY_LIST)
    def test_every_listed_category_is_accepted(self, user_client, urls, category):
        response = user_client.post(urls.add, data=form_data(category=category))
        assert response.status_code == 302, f"{category} should be accepted"
        assert last_expense()["category"] == category

    def test_date_today_is_accepted(self, user_client, urls):
        response = user_client.post(urls.add, data=form_data(date=today_iso()))
        assert response.status_code == 302
        assert last_expense()["date"] == today_iso()

    def test_past_date_is_accepted(self, user_client, urls):
        response = user_client.post(urls.add, data=form_data(date="2020-01-15"))
        assert response.status_code == 302
        assert last_expense()["date"] == "2020-01-15"

    def test_post_does_not_render_profile_directly(self, user_client, urls):
        response = user_client.post(urls.add, data=form_data())
        assert response.status_code == 302
        assert b"Transaction history" not in response.data


# ------------------------------------------------------------------ #
# Amount validation and rounding                                      #
# ------------------------------------------------------------------ #

class TestAmount:
    @pytest.mark.parametrize(
        "bad_amount",
        ["0", "0.00", "-5", "-0.01", "abc", "nan", "NaN", "inf", "-inf", "Infinity", "", "   ", "10000000.01", "1e9"],
    )
    def test_invalid_amount_rerenders_form_with_error_and_saves_nothing(
        self, user_client, urls, bad_amount
    ):
        before = count_expenses()
        response = user_client.post(urls.add, data=form_data(amount=bad_amount))
        assert response.status_code == 200, f"{bad_amount!r} should re-render the form"
        assert AMOUNT_ERROR in response.data, f"Missing amount error for {bad_amount!r}"
        assert count_expenses() == before, f"{bad_amount!r} must not insert a row"

    def test_missing_amount_field_is_rejected(self, user_client, urls):
        before = count_expenses()
        response = user_client.post(urls.add, data=form_data(amount=None))
        assert response.status_code == 200
        assert AMOUNT_ERROR in response.data
        assert count_expenses() == before

    def test_amount_12_345_is_rounded_to_12_35(self, user_client, urls):
        response = user_client.post(urls.add, data=form_data(amount="12.345"))
        assert response.status_code == 302
        assert round(last_expense()["amount"], 2) == 12.35
        assert last_expense()["amount"] == pytest.approx(12.35, abs=1e-9)

    def test_amount_with_more_precision_is_stored_at_two_decimals(self, user_client, urls):
        user_client.post(urls.add, data=form_data(amount="99.994"))
        assert last_expense()["amount"] == pytest.approx(99.99, abs=1e-9)

    def test_whole_number_amount_is_accepted(self, user_client, urls):
        response = user_client.post(urls.add, data=form_data(amount="250"))
        assert response.status_code == 302
        assert last_expense()["amount"] == pytest.approx(250.0)

    def test_smallest_valid_amount_is_accepted(self, user_client, urls):
        response = user_client.post(urls.add, data=form_data(amount="0.01"))
        assert response.status_code == 302
        assert last_expense()["amount"] == pytest.approx(0.01)

    def test_maximum_amount_ten_million_is_accepted(self, user_client, urls):
        response = user_client.post(urls.add, data=form_data(amount="10000000"))
        assert response.status_code == 302
        assert last_expense()["amount"] == pytest.approx(10_000_000)


# ------------------------------------------------------------------ #
# Category validation                                                 #
# ------------------------------------------------------------------ #

class TestCategory:
    @pytest.mark.parametrize("bad_category", ["Travel", "food", "FOOD", "", "  ", "Food; DROP TABLE expenses"])
    def test_invalid_category_is_rejected(self, user_client, urls, bad_category):
        before = count_expenses()
        response = user_client.post(urls.add, data=form_data(category=bad_category))
        assert response.status_code == 200
        assert CATEGORY_ERROR in response.data, f"Missing category error for {bad_category!r}"
        assert count_expenses() == before

    def test_missing_category_field_is_rejected(self, user_client, urls):
        before = count_expenses()
        response = user_client.post(urls.add, data=form_data(category=None))
        assert response.status_code == 200
        assert CATEGORY_ERROR in response.data
        assert count_expenses() == before


# ------------------------------------------------------------------ #
# Date validation                                                     #
# ------------------------------------------------------------------ #

class TestDate:
    @pytest.mark.parametrize(
        "bad_date",
        ["", "   ", "abc", "2026-13-01", "2026-02-30", "05-11-2026", "2026/11/05", "20261105"],
    )
    def test_malformed_or_empty_date_is_rejected(self, user_client, urls, bad_date):
        before = count_expenses()
        response = user_client.post(urls.add, data=form_data(date=bad_date))
        assert response.status_code == 200
        assert DATE_ERROR in response.data, f"Missing date error for {bad_date!r}"
        assert count_expenses() == before

    def test_unpadded_date_is_accepted_and_normalised(self, user_client, urls):
        # The spec reuses _parse_iso_date, whose strptime accepts unpadded
        # fields; the stored value is the zero-padded ISO date.
        first = date.today().replace(day=1)
        unpadded = f"{first.year}-{first.month}-{first.day}"
        before = count_expenses()
        response = user_client.post(urls.add, data=form_data(date=unpadded))
        assert response.status_code == 302
        assert count_expenses() == before + 1
        assert last_expense()["date"] == first.isoformat()

    def test_missing_date_field_is_rejected(self, user_client, urls):
        before = count_expenses()
        response = user_client.post(urls.add, data=form_data(date=None))
        assert response.status_code == 200
        assert DATE_ERROR in response.data
        assert count_expenses() == before

    @pytest.mark.parametrize("days_ahead", [1, 30, 3650])
    def test_future_date_is_rejected(self, user_client, urls, days_ahead):
        future = (date.today() + timedelta(days=days_ahead)).isoformat()
        before = count_expenses()
        response = user_client.post(urls.add, data=form_data(date=future))
        assert response.status_code == 200
        assert DATE_ERROR in response.data, f"{future} should be rejected as future"
        assert count_expenses() == before


# ------------------------------------------------------------------ #
# Description handling                                                #
# ------------------------------------------------------------------ #

class TestDescription:
    def test_blank_description_saved_as_empty_string_not_null(self, user_client, urls):
        response = user_client.post(urls.add, data=form_data(description=""))
        assert response.status_code == 302
        row = last_expense()
        assert row["description"] is not None, "Blank description must not be NULL"
        assert row["description"] == ""

    def test_missing_description_field_saved_as_empty_string(self, user_client, urls):
        response = user_client.post(urls.add, data=form_data(description=None))
        assert response.status_code == 302
        assert last_expense()["description"] == ""

    def test_whitespace_only_description_saved_as_empty_string(self, user_client, urls):
        response = user_client.post(urls.add, data=form_data(description="    "))
        assert response.status_code == 302
        assert last_expense()["description"] == ""

    def test_description_is_stripped(self, user_client, urls):
        user_client.post(urls.add, data=form_data(description="   Dinner out  "))
        assert last_expense()["description"] == "Dinner out"

    def test_description_of_200_chars_is_accepted(self, user_client, urls):
        text = "a" * 200
        response = user_client.post(urls.add, data=form_data(description=text))
        assert response.status_code == 302
        assert last_expense()["description"] == text

    def test_description_of_201_chars_is_rejected(self, user_client, urls):
        before = count_expenses()
        response = user_client.post(urls.add, data=form_data(description="a" * 201))
        assert response.status_code == 200
        assert DESCRIPTION_ERROR in response.data
        assert count_expenses() == before

    def test_very_long_description_is_rejected(self, user_client, urls):
        before = count_expenses()
        response = user_client.post(urls.add, data=form_data(description="x" * 5000))
        assert response.status_code == 200
        assert DESCRIPTION_ERROR in response.data
        assert count_expenses() == before

    def test_sql_looking_description_is_stored_literally(self, user_client, urls, empty_user_id):
        payload = "'); DROP TABLE expenses;--"
        total_before = count_expenses()
        response = user_client.post(urls.add, data=form_data(description=payload))
        assert response.status_code == 302
        assert count_expenses() == total_before + 1, "expenses table must survive"
        assert last_expense()["description"] == payload

    def test_sql_looking_description_on_profile_does_not_break_page(self, user_client, urls):
        user_client.post(urls.add, data=form_data(description="'); DROP TABLE expenses;--"))
        response = user_client.get(urls.profile)
        assert response.status_code == 200


# ------------------------------------------------------------------ #
# Error display and form re-population                                #
# ------------------------------------------------------------------ #

class TestFailureRendering:
    def test_failed_submit_shows_alert_block(self, user_client, urls):
        response = user_client.post(urls.add, data=form_data(amount="0"))
        assert response.status_code == 200
        assert b'role="alert"' in response.data

    def test_failed_submit_repopulates_all_fields(self, user_client, urls):
        past = days_ago_iso(4)
        response = user_client.post(
            urls.add,
            data=form_data(
                amount="-5",
                category="Health",
                date=past,
                description="Pharmacy run",
            ),
        )
        assert response.status_code == 200
        assert b'value="-5"' in response.data, "Amount not re-populated"
        assert option_selected(response.data, "Health"), "Category not re-selected"
        assert f'value="{past}"'.encode() in response.data, "Date not re-populated"
        assert b'value="Pharmacy run"' in response.data, "Description not re-populated"

    def test_failed_submit_on_bad_category_keeps_other_fields(self, user_client, urls):
        past = days_ago_iso(6)
        response = user_client.post(
            urls.add,
            data=form_data(
                amount="42.5", category="Travel", date=past, description="Flight snack"
            ),
        )
        assert CATEGORY_ERROR in response.data
        assert b'value="42.5"' in response.data
        assert f'value="{past}"'.encode() in response.data
        assert b'value="Flight snack"' in response.data
        assert not option_selected(response.data, "Travel")

    def test_failed_submit_on_future_date_keeps_typed_date(self, user_client, urls):
        future = (date.today() + timedelta(days=10)).isoformat()
        response = user_client.post(urls.add, data=form_data(date=future, amount="77"))
        assert DATE_ERROR in response.data
        assert f'value="{future}"'.encode() in response.data, "Typed date should be kept"
        assert b'value="77"' in response.data

    def test_failed_submit_on_long_description_keeps_category_and_amount(self, user_client, urls):
        response = user_client.post(
            urls.add,
            data=form_data(amount="19.99", category="Shopping", description="b" * 201),
        )
        assert DESCRIPTION_ERROR in response.data
        assert b'value="19.99"' in response.data
        assert option_selected(response.data, "Shopping")

    def test_multiple_errors_are_all_shown(self, user_client, urls):
        before = count_expenses()
        response = user_client.post(
            urls.add, data=form_data(amount="abc", category="Travel", date="nope")
        )
        assert response.status_code == 200
        assert AMOUNT_ERROR in response.data
        assert CATEGORY_ERROR in response.data
        assert DATE_ERROR in response.data
        assert count_expenses() == before

    def test_empty_post_shows_required_field_errors_and_saves_nothing(self, user_client, urls):
        before = count_expenses()
        response = user_client.post(urls.add, data={})
        assert response.status_code == 200
        assert AMOUNT_ERROR in response.data
        assert CATEGORY_ERROR in response.data
        assert DATE_ERROR in response.data
        assert count_expenses() == before

    def test_user_input_is_html_escaped_when_repopulated(self, user_client, urls):
        response = user_client.post(
            urls.add,
            data=form_data(amount="0", description="<script>alert(1)</script>"),
        )
        assert response.status_code == 200
        assert b"<script>alert(1)</script>" not in response.data, "Input must be escaped"

    def test_failed_submit_still_uses_rupee_not_dollar(self, user_client, urls):
        response = user_client.post(urls.add, data=form_data(amount="0"))
        assert "₹".encode() in response.data
        assert b"$" not in response.data


# ------------------------------------------------------------------ #
# Effect on the profile page                                          #
# ------------------------------------------------------------------ #

class TestProfileReflectsExpense:
    def test_new_expense_appears_in_transaction_history(self, user_client, urls):
        user_client.post(
            urls.add,
            data=form_data(
                amount="4321.09",
                category="Shopping",
                date=days_ago_iso(1),
                description="Unique headphones purchase",
            ),
        )
        response = user_client.get(urls.profile, follow_redirects=False)
        assert response.status_code == 200
        assert b"Unique headphones purchase" in response.data
        assert "₹4,321.09".encode() in response.data, "Amount should use INR formatting"
        assert b"Shopping" in response.data

    def test_following_redirect_lands_on_profile_with_new_expense(self, user_client, urls):
        response = user_client.post(
            urls.add,
            data=form_data(description="Redirect check item", amount="321.00"),
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"Redirect check item" in response.data
        assert "₹321.00".encode() in response.data

    def test_total_spent_reflects_added_expenses(self, user_client, urls):
        user_client.post(urls.add, data=form_data(amount="100", category="Food"))
        user_client.post(urls.add, data=form_data(amount="250.50", category="Bills"))
        response = user_client.get(urls.profile)
        assert "₹350.50".encode() in response.data, "Total spent should be 350.50"

    def test_category_breakdown_reflects_added_expense(self, user_client, urls):
        user_client.post(urls.add, data=form_data(amount="800", category="Entertainment"))
        response = user_client.get(urls.profile)
        assert b"Entertainment" in response.data
        assert "₹800.00".encode() in response.data

    def test_today_dated_expense_appears_above_older_user_expense(
        self, user_client, urls, empty_user_id
    ):
        insert_expense(empty_user_id, 10.0, "Food", days_ago_iso(5), "Older zzz item")
        user_client.post(
            urls.add, data=form_data(date=today_iso(), description="Newest aaa item")
        )
        response = user_client.get(urls.profile)
        body = response.data
        assert b"Newest aaa item" in body and b"Older zzz item" in body
        assert body.index(b"Newest aaa item") < body.index(
            b"Older zzz item"
        ), "Today-dated expense should be listed above older expense"

    def test_blank_description_does_not_render_none_on_profile(self, user_client, urls):
        user_client.post(urls.add, data=form_data(description="", amount="888.88"))
        response = user_client.get(urls.profile)
        assert response.status_code == 200
        assert "₹888.88".encode() in response.data
        assert b"None" not in response.data, "Blank description must not render as 'None'"

    def test_other_users_profile_does_not_show_new_expense(
        self, client, login, urls, empty_user_id, demo_user_id
    ):
        login(empty_user_id)
        client.post(
            urls.add,
            data=form_data(amount="4321.09", description="Private empty-user purchase"),
        )
        login(demo_user_id)
        response = client.get(urls.profile)
        assert response.status_code == 200
        assert b"Private empty-user purchase" not in response.data
        assert "₹4,321.09".encode() not in response.data

    def test_failed_submit_does_not_change_profile_total(self, user_client, urls):
        user_client.post(urls.add, data=form_data(amount="100"))
        user_client.post(urls.add, data=form_data(amount="-999", description="Rejected row"))
        response = user_client.get(urls.profile)
        assert b"Rejected row" not in response.data
        assert "₹100.00".encode() in response.data


# ------------------------------------------------------------------ #
# Other stub routes untouched                                         #
# ------------------------------------------------------------------ #

class TestOtherStubsUnchanged:
    def test_edit_route_requires_login(self, client):
        with client.application.test_request_context():
            edit_url = url_for("edit_expense", id=1)
        response = client.get(edit_url)
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")

    def test_delete_stub_still_returns_stub_response(self, client):
        with client.application.test_request_context():
            delete_url = url_for("delete_expense", id=1)
        response = client.get(delete_url)
        assert response.status_code == 200
        assert b"Step 9" in response.data
