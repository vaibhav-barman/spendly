"""Tests for Step 9: delete expense (POST /expenses/<id>/delete).

Written from .claude/specs/09-delete-expense.md (Definition of done), not from
the implementation. All money in test data is INR.
"""
import re
from datetime import date
from pathlib import Path

import pytest
from werkzeug.security import generate_password_hash

from database import db

TODAY = date.today().isoformat()
PROJECT_ROOT = Path(__file__).resolve().parent.parent


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
    return f"/expenses/{expense_id}/delete"


def _stat(html, label):
    """Return the text of the profile stat card with the given label."""
    match = re.search(
        r'<span class="stat-label">' + re.escape(label)
        + r'</span>\s*<span class="stat-value">([^<]*)</span>',
        html,
    )
    assert match, f"Stat card {label!r} not found on profile page"
    return match.group(1).strip()


def _breakdown_names(html):
    return re.findall(r'<span class="breakdown-name">([^<]*)</span>', html)


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
def owned_id(empty_user_id):
    """A single expense with fully controlled values owned by empty_user_id."""
    return db.create_expense(empty_user_id, 200.0, "Food", TODAY, "Original lunch")


@pytest.fixture
def three_ids(empty_user_id):
    """Three expenses in three categories for empty_user_id (total 1350.50)."""
    food = db.create_expense(empty_user_id, 200.0, "Food", TODAY, "Dhaba lunch")
    transport = db.create_expense(
        empty_user_id, 150.5, "Transport", TODAY, "Metro card top-up"
    )
    bills = db.create_expense(empty_user_id, 1000.0, "Bills", TODAY, "Broadband bill")
    return {"food": food, "transport": transport, "bills": bills}


# ------------------------------------------------- GET is never allowed

class TestGetNotAllowed:
    def test_get_logged_in_returns_405_and_deletes_nothing(
        self, client, login, empty_user_id, owned_id
    ):
        login(empty_user_id)
        before = _count_all()
        resp = client.get(_url(owned_id))
        assert resp.status_code == 405, "GET must not be served for delete"
        assert _fetch_row(owned_id) is not None, "GET must not delete the row"
        assert _count_all() == before

    def test_get_logged_out_returns_405_and_deletes_nothing(self, client, owned_id):
        before = _count_all()
        resp = client.get(_url(owned_id))
        assert resp.status_code == 405, "405 must apply regardless of session"
        assert _fetch_row(owned_id) is not None
        assert _count_all() == before

    def test_get_nonexistent_id_returns_405(self, client, login, demo_user_id):
        login(demo_user_id)
        before = _count_all()
        resp = client.get(_url(9999))
        assert resp.status_code == 405
        assert _count_all() == before

    def test_get_logged_out_nonexistent_id_returns_405(self, client):
        assert client.get(_url(9999)).status_code == 405


# ---------------------------------------------------------------- auth

class TestAuthGuard:
    def test_post_logged_out_redirects_to_login_and_deletes_nothing(
        self, client, owned_id
    ):
        before_all = _count_all()
        before_row = _snapshot(owned_id)
        resp = client.post(_url(owned_id))
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/login")
        assert _count_all() == before_all
        assert _snapshot(owned_id) == before_row

    def test_post_stale_session_redirects_to_login_and_clears_session(
        self, client, login, owned_id
    ):
        login(99999)
        before = _count_all()
        resp = client.post(_url(owned_id))
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/login")
        assert _count_all() == before
        assert _fetch_row(owned_id) is not None
        with client.session_transaction() as sess:
            assert "user_id" not in sess, "Stale session should be cleared"


# ------------------------------------------------------------- success

class TestDeleteSuccess:
    def test_post_owner_redirects_to_profile_and_row_is_gone(
        self, client, login, empty_user_id, owned_id
    ):
        login(empty_user_id)
        resp = client.post(_url(owned_id))
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/profile")
        assert _fetch_row(owned_id) is None, "Row should be deleted from the DB"
        assert _count_user(empty_user_id) == 0

    def test_only_target_removed_others_unchanged(
        self, client, login, empty_user_id, three_ids
    ):
        login(empty_user_id)
        keep = {k: _snapshot(v) for k, v in three_ids.items() if k != "transport"}
        before = _count_all()
        resp = client.post(_url(three_ids["transport"]))
        assert resp.status_code == 302
        assert _fetch_row(three_ids["transport"]) is None
        assert _count_all() == before - 1
        for key, snap in keep.items():
            assert _snapshot(three_ids[key]) == snap, f"{key} expense was modified"

    def test_delete_does_not_touch_other_users_rows(
        self, client, login, demo_user_id, empty_user_id, owned_id
    ):
        login(empty_user_id)
        demo_before = _count_user(demo_user_id)
        client.post(_url(owned_id))
        assert _count_user(demo_user_id) == demo_before

    def test_profile_after_delete_shows_updated_total_and_count(
        self, client, login, empty_user_id, three_ids
    ):
        login(empty_user_id)
        html = client.get("/profile").get_data(as_text=True)
        assert _stat(html, "Transactions") == "3"
        assert _stat(html, "Total spent") == "₹1,350.50"
        assert "Dhaba lunch" in html

        client.post(_url(three_ids["food"]))

        html = client.get("/profile").get_data(as_text=True)
        assert "Dhaba lunch" not in html, "Deleted row should be gone"
        assert "Metro card top-up" in html
        assert "Broadband bill" in html
        assert _stat(html, "Transactions") == "2"
        assert _stat(html, "Total spent") == "₹1,150.50"

    def test_following_redirect_lands_on_profile_without_deleted_row(
        self, client, login, empty_user_id, three_ids
    ):
        login(empty_user_id)
        resp = client.post(_url(three_ids["bills"]), follow_redirects=True)
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "Broadband bill" not in html
        assert "Dhaba lunch" in html

    def test_category_disappears_from_breakdown_when_last_expense_deleted(
        self, client, login, empty_user_id, three_ids
    ):
        login(empty_user_id)
        before = _breakdown_names(client.get("/profile").get_data(as_text=True))
        assert {"Food", "Transport", "Bills"} <= set(before)

        client.post(_url(three_ids["transport"]))

        after = _breakdown_names(client.get("/profile").get_data(as_text=True))
        assert "Transport" not in after, "Empty category should leave the breakdown"
        assert "Food" in after
        assert "Bills" in after

    def test_category_stays_in_breakdown_when_other_expenses_remain(
        self, client, login, empty_user_id
    ):
        first = db.create_expense(empty_user_id, 100.0, "Food", TODAY, "Samosa")
        db.create_expense(empty_user_id, 300.0, "Food", TODAY, "Thali")
        login(empty_user_id)
        client.post(_url(first))
        html = client.get("/profile").get_data(as_text=True)
        assert "Food" in _breakdown_names(html)
        assert _stat(html, "Total spent") == "₹300.00"

    def test_deleting_last_expense_shows_empty_state(
        self, client, login, empty_user_id, owned_id
    ):
        login(empty_user_id)
        client.post(_url(owned_id))
        resp = client.get("/profile")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "No transactions yet." in html
        assert _stat(html, "Transactions") == "0"

    def test_deleting_last_expense_via_followed_redirect_is_200(
        self, client, login, empty_user_id, owned_id
    ):
        login(empty_user_id)
        resp = client.post(_url(owned_id), follow_redirects=True)
        assert resp.status_code == 200
        assert b"No transactions yet." in resp.data


# ------------------------------------------------------------- failures

class TestDeleteFailures:
    def test_post_nonexistent_id_returns_404(self, client, login, demo_user_id):
        login(demo_user_id)
        before = _count_all()
        resp = client.post(_url(9999))
        assert resp.status_code == 404
        assert _count_all() == before

    def test_post_other_users_expense_returns_404_and_row_survives(
        self, client, login, other_user_id, owned_id
    ):
        login(other_user_id)
        before_row = _snapshot(owned_id)
        before = _count_all()
        resp = client.post(_url(owned_id))
        assert resp.status_code == 404
        assert _fetch_row(owned_id) is not None, "Foreign expense must survive"
        assert _snapshot(owned_id) == before_row
        assert _count_all() == before

    def test_foreign_and_missing_ids_give_same_status(
        self, client, login, other_user_id, owned_id
    ):
        login(other_user_id)
        foreign = client.post(_url(owned_id))
        missing = client.post(_url(owned_id + 1000))
        assert foreign.status_code == missing.status_code == 404

    def test_double_delete_first_redirects_then_404(
        self, client, login, empty_user_id, owned_id
    ):
        login(empty_user_id)
        first = client.post(_url(owned_id))
        assert first.status_code == 302
        assert first.headers["Location"].endswith("/profile")
        second = client.post(_url(owned_id))
        assert second.status_code == 404

    @pytest.mark.parametrize("bad_id", ["abc", "-1", "1.5", "0x1"])
    def test_post_non_integer_or_negative_id_returns_404(
        self, client, login, empty_user_id, owned_id, bad_id
    ):
        login(empty_user_id)
        before = _count_all()
        resp = client.post(f"/expenses/{bad_id}/delete")
        assert resp.status_code == 404
        assert _count_all() == before
        assert _fetch_row(owned_id) is not None

    def test_sql_injection_style_id_is_rejected_and_nothing_deleted(
        self, client, login, empty_user_id, owned_id
    ):
        login(empty_user_id)
        before = _count_all()
        resp = client.post("/expenses/1%20OR%201=1/delete")
        assert resp.status_code == 404
        assert _count_all() == before


# ---------------------------------------------------- db.delete_expense

class TestDbDeleteExpense:
    def test_owner_delete_returns_true_and_removes_row(
        self, empty_user_id, owned_id
    ):
        assert db.delete_expense(empty_user_id, owned_id) is True
        assert _fetch_row(owned_id) is None

    def test_repeat_delete_returns_false(self, empty_user_id, owned_id):
        assert db.delete_expense(empty_user_id, owned_id) is True
        assert db.delete_expense(empty_user_id, owned_id) is False

    def test_wrong_user_returns_false_and_row_intact(
        self, other_user_id, owned_id
    ):
        before = _snapshot(owned_id)
        assert db.delete_expense(other_user_id, owned_id) is False
        assert _fetch_row(owned_id) is not None
        assert _snapshot(owned_id) == before

    def test_missing_expense_returns_false(self, empty_user_id):
        assert db.delete_expense(empty_user_id, 9999) is False

    def test_only_target_row_deleted(self, empty_user_id, three_ids):
        assert db.delete_expense(empty_user_id, three_ids["food"]) is True
        assert _fetch_row(three_ids["food"]) is None
        assert _fetch_row(three_ids["transport"]) is not None
        assert _fetch_row(three_ids["bills"]) is not None
        assert _count_user(empty_user_id) == 2


# ------------------------------------------------------ profile markup

class TestProfileMarkup:
    def _delete_forms(self, html):
        forms = re.findall(r"<form\b[^>]*>.*?</form>", html, flags=re.DOTALL | re.I)
        return [f for f in forms if re.search(r'action="[^"]*/delete"', f)]

    def test_row_has_post_form_with_delete_action(
        self, client, login, empty_user_id, owned_id
    ):
        login(empty_user_id)
        html = client.get("/profile").get_data(as_text=True)
        forms = [f for f in self._delete_forms(html)
                 if f'action="/expenses/{owned_id}/delete"' in f]
        assert len(forms) == 1, "Expected exactly one delete form for the row"
        open_tag = re.match(r"<form\b[^>]*>", forms[0], flags=re.I).group(0)
        assert re.search(r'method="post"', open_tag, flags=re.I), \
            "Delete form must use method=post"

    def test_form_has_data_confirm_attribute(
        self, client, login, empty_user_id, owned_id
    ):
        login(empty_user_id)
        html = client.get("/profile").get_data(as_text=True)
        form = next(f for f in self._delete_forms(html)
                    if f'action="/expenses/{owned_id}/delete"' in f)
        open_tag = re.match(r"<form\b[^>]*>", form, flags=re.I).group(0)
        match = re.search(r'data-confirm="([^"]+)"', open_tag)
        assert match, "Delete form needs a non-empty data-confirm message"

    def test_form_has_submit_button_with_accessible_label(
        self, client, login, empty_user_id, owned_id
    ):
        login(empty_user_id)
        html = client.get("/profile").get_data(as_text=True)
        form = next(f for f in self._delete_forms(html)
                    if f'action="/expenses/{owned_id}/delete"' in f)
        button = re.search(r"<button\b[^>]*>", form, flags=re.I)
        assert button, "Delete form needs a <button>"
        tag = button.group(0)
        assert re.search(r'type="submit"', tag), "Button must be type=submit"
        assert re.search(r'aria-label="Delete expense', tag), \
            "Button needs an aria-label starting with 'Delete expense'"

    def test_every_listed_row_has_a_delete_form(
        self, client, login, empty_user_id, three_ids
    ):
        login(empty_user_id)
        html = client.get("/profile").get_data(as_text=True)
        for expense_id in three_ids.values():
            assert f'action="/expenses/{expense_id}/delete"' in html

    def test_delete_is_never_an_anchor_link(
        self, client, login, empty_user_id, three_ids
    ):
        login(empty_user_id)
        html = client.get("/profile").get_data(as_text=True)
        assert not re.search(r'<a\b[^>]*href="[^"]*/delete"', html, flags=re.I), \
            "Delete must never be a plain link"

    def test_demo_profile_has_no_delete_anchor_links(
        self, client, login, demo_user_id
    ):
        login(demo_user_id)
        html = client.get("/profile").get_data(as_text=True)
        assert self._delete_forms(html), "Demo profile should show delete forms"
        assert not re.search(r'<a\b[^>]*href="[^"]*/delete"', html, flags=re.I)

    def test_empty_profile_has_no_delete_forms(
        self, client, login, empty_user_id
    ):
        login(empty_user_id)
        html = client.get("/profile").get_data(as_text=True)
        assert not self._delete_forms(html)


# ------------------------------------------------------ static assets

class TestStaticAssets:
    def test_main_js_has_confirm_handler(self):
        js = (PROJECT_ROOT / "static" / "js" / "main.js").read_text(encoding="utf-8")
        assert "data-confirm" in js, "main.js should read the data-confirm attribute"
        assert "confirm(" in js, "main.js should call confirm()"

    def test_delete_button_css_has_no_hex_colours(self):
        css = (PROJECT_ROOT / "static" / "css" / "profile.css").read_text(
            encoding="utf-8"
        )
        blocks = re.findall(r"[^{}]*\.txn-action-delete[^{}]*\{([^}]*)\}", css)
        assert blocks, "Expected a .txn-action-delete rule in profile.css"
        for body in blocks:
            assert not re.search(r"#[0-9a-fA-F]{3,8}\b", body), \
                f"Hardcoded hex colour in .txn-action-delete block: {body!r}"
            assert "var(--" in body or "color" not in body

    def test_base_template_loads_main_js(self, client):
        html = client.get("/").get_data(as_text=True)
        assert "main.js" in html


# ---------------------------------------------------------------- smoke

class TestOtherExpenseRoutesStillWork:
    def test_add_expense_page_still_returns_200(self, client, login, demo_user_id):
        login(demo_user_id)
        assert client.get("/expenses/add").status_code == 200

    def test_edit_expense_page_still_returns_200(
        self, client, login, empty_user_id, owned_id
    ):
        login(empty_user_id)
        assert client.get(f"/expenses/{owned_id}/edit").status_code == 200

    def test_profile_still_returns_200(self, client, login, demo_user_id):
        login(demo_user_id)
        assert client.get("/profile").status_code == 200
