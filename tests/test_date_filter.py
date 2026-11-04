import re
from datetime import date

import pytest

from app import _build_presets, _parse_date_range, _parse_iso_date
from database import db

EMPTY_SUMMARY = {"total_spent": 0.0, "transaction_count": 0, "top_category": None}
ERROR_TEXT = "Start date must be before end date."


def _add_expenses(user_id, rows):
    """rows: (date, amount, category, description)."""
    conn = db.get_db()
    try:
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            [(user_id, amount, cat, d, desc) for d, amount, cat, desc in rows],
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def dated_user_id(empty_user_id):
    """The empty user, given three expenses on fixed dates."""
    _add_expenses(
        empty_user_id,
        [
            ("2026-01-10", 150.00, "Food", "Jan lunch"),
            ("2026-02-15", 300.00, "Bills", "Feb rent"),
            ("2026-03-20", 200.00, "Food", "Mar dinner"),
        ],
    )
    return empty_user_id


def _demo_day(day):
    return date.today().replace(day=day).isoformat()


# ------------------------------------------------------------------ #
# Database layer                                                      #
# ------------------------------------------------------------------ #

def test_no_bounds_matches_unfiltered_behaviour(demo_user_id):
    summary = db.get_expense_summary(demo_user_id)
    assert summary["total_spent"] == 6398.00
    assert summary["transaction_count"] == 8
    assert summary == db.get_expense_summary(demo_user_id, date_from=None, date_to=None)
    assert len(db.get_recent_expenses(demo_user_id)) == 8


def test_range_is_inclusive_at_both_ends(dated_user_id):
    summary = db.get_expense_summary(
        dated_user_id, date_from="2026-01-10", date_to="2026-02-15"
    )
    assert summary == {"total_spent": 450.0, "transaction_count": 2, "top_category": "Bills"}


def test_single_day_range_returns_that_expense(dated_user_id):
    rows = db.get_recent_expenses(
        dated_user_id, date_from="2026-02-15", date_to="2026-02-15"
    )
    assert [r["description"] for r in rows] == ["Feb rent"]


def test_from_only_is_open_ended(dated_user_id):
    summary = db.get_expense_summary(dated_user_id, date_from="2026-02-15")
    assert summary["transaction_count"] == 2
    assert summary["total_spent"] == 500.0


def test_to_only_is_open_ended(dated_user_id):
    rows = db.get_recent_expenses(dated_user_id, date_to="2026-01-10")
    assert [r["description"] for r in rows] == ["Jan lunch"]


def test_empty_range_returns_empty_results(dated_user_id):
    kwargs = {"date_from": "2025-01-01", "date_to": "2025-12-31"}
    assert db.get_expense_summary(dated_user_id, **kwargs) == EMPTY_SUMMARY
    assert db.get_recent_expenses(dated_user_id, **kwargs) == []
    assert db.get_category_breakdown(dated_user_id, **kwargs) == []


def test_breakdown_percent_is_over_the_filtered_total(dated_user_id):
    rows = db.get_category_breakdown(
        dated_user_id, date_from="2026-01-01", date_to="2026-02-28"
    )
    assert [(r["name"], r["total"], r["percent"]) for r in rows] == [
        ("Bills", 300.0, 67),
        ("Food", 150.0, 33),
    ]


def test_limit_still_works_with_a_range(dated_user_id):
    rows = db.get_recent_expenses(dated_user_id, limit=2, date_from="2026-01-01")
    assert [r["description"] for r in rows] == ["Mar dinner", "Feb rent"]


def test_filter_never_leaks_other_users_rows(demo_user_id, dated_user_id):
    wide = {"date_from": "2000-01-01", "date_to": "2999-12-31"}
    rows = db.get_recent_expenses(dated_user_id, **wide)
    assert len(rows) == 3
    assert "Dinner out" not in [r["description"] for r in rows]
    assert db.get_expense_summary(demo_user_id, **wide)["transaction_count"] == 8


# ------------------------------------------------------------------ #
# app.py helpers                                                      #
# ------------------------------------------------------------------ #

@pytest.mark.parametrize(
    "value, expected",
    [
        ("2026-03-05", "2026-03-05"),
        ("2026-3-5", "2026-03-05"),
        ("not-a-date", None),
        ("2026-13-45", None),
        ("2026-02-30", None),
        ("' OR 1=1 --", None),
        ("", None),
        (None, None),
    ],
)
def test_parse_iso_date(value, expected):
    assert _parse_iso_date(value) == expected


def test_parse_date_range_valid_and_single_bound():
    assert _parse_date_range({"date_from": "2026-01-01", "date_to": "2026-01-31"}) == (
        "2026-01-01", "2026-01-31", None,
    )
    assert _parse_date_range({"date_from": "2026-01-01"}) == ("2026-01-01", None, None)
    assert _parse_date_range({"date_to": "2026-01-31"}) == (None, "2026-01-31", None)
    assert _parse_date_range({}) == (None, None, None)


def test_parse_date_range_equal_dates_are_allowed():
    assert _parse_date_range({"date_from": "2026-01-01", "date_to": "2026-01-01"}) == (
        "2026-01-01", "2026-01-01", None,
    )


def test_parse_date_range_inverted_clears_both_and_errors():
    result = _parse_date_range({"date_from": "2026-02-01", "date_to": "2026-01-01"})
    assert result == (None, None, ERROR_TEXT)


def test_parse_date_range_malformed_is_an_open_bound():
    assert _parse_date_range({"date_from": "junk", "date_to": "2026-01-31"}) == (
        None, "2026-01-31", None,
    )


def _ranges(presets):
    return {p["key"]: (p["date_from"], p["date_to"]) for p in presets}


def test_build_presets_calendar_aligned():
    assert _ranges(_build_presets(date(2026, 11, 4))) == {
        "month": ("2026-11-01", "2026-11-30"),
        "3m": ("2026-09-01", "2026-11-30"),
        "6m": ("2026-06-01", "2026-11-30"),
        "all": (None, None),
    }


def test_build_presets_crosses_year_boundary():
    ranges = _ranges(_build_presets(date(2026, 2, 10)))
    assert ranges["3m"] == ("2025-12-01", "2026-02-28")
    assert ranges["6m"] == ("2025-09-01", "2026-02-28")


def test_build_presets_leap_year_february():
    assert _ranges(_build_presets(date(2028, 2, 10)))["month"] == ("2028-02-01", "2028-02-29")


def test_build_presets_order_and_labels():
    presets = _build_presets(date(2026, 11, 4))
    assert [p["label"] for p in presets] == [
        "This Month", "Last 3 Months", "Last 6 Months", "All Time",
    ]


# ------------------------------------------------------------------ #
# GET /profile                                                        #
# ------------------------------------------------------------------ #

def _get(client, **params):
    resp = client.get("/profile", query_string=params)
    return resp, resp.get_data(as_text=True)


def test_logged_out_with_params_still_redirects(client):
    resp = client.get("/profile?date_from=2026-01-01")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_unfiltered_page_highlights_all_time(client, login, demo_user_id):
    login(demo_user_id)
    resp, html = _get(client)
    assert resp.status_code == 200
    assert "₹6,398.00" in html
    assert html.count("filter-preset is-active") == 1
    assert re.search(r'filter-preset is-active"[^>]*>All Time', html)
    assert re.search(r'href="/profile"[^>]*>All Time', html)
    assert "Showing" not in html


def test_custom_range_filters_all_three_sections(client, login, demo_user_id):
    login(demo_user_id)
    resp, html = _get(client, date_from=_demo_day(1), date_to=_demo_day(10))
    assert resp.status_code == 200
    assert "₹3,020.00" in html
    assert "Pharmacy" in html
    assert "Weekly groceries" in html
    assert "Movie tickets" not in html
    assert "New shirt" not in html
    # Breakdown: Bills is the largest category in this range, Shopping is absent.
    assert "Bills" in html
    assert "Shopping" not in html
    assert "filter-custom is-active" in html
    assert "filter-preset is-active" not in html
    assert f'value="{_demo_day(1)}"' in html
    assert f'value="{_demo_day(10)}"' in html
    assert "Showing" in html


def test_from_only_filters_onwards(client, login, demo_user_id):
    login(demo_user_id)
    resp, html = _get(client, date_from=_demo_day(20))
    assert resp.status_code == 200
    assert "₹580.00" in html
    assert "Birthday gift" in html
    assert "Dinner out" in html
    assert "Weekly groceries" not in html


def test_to_only_filters_up_to(client, login, demo_user_id):
    login(demo_user_id)
    resp, html = _get(client, date_to=_demo_day(4))
    assert resp.status_code == 200
    assert "₹570.00" in html
    assert "Weekly groceries" in html
    assert "Auto rickshaw to office" in html
    assert "Electricity bill" not in html


def test_this_month_preset_link_works_and_is_highlighted(client, login, demo_user_id):
    login(demo_user_id)
    month = _build_presets(date.today())[0]
    resp, html = _get(client, date_from=month["date_from"], date_to=month["date_to"])
    assert resp.status_code == 200
    assert "₹6,398.00" in html
    assert re.search(r'filter-preset is-active"[^>]*>This Month', html)
    assert html.count("filter-preset is-active") == 1


def test_inverted_range_shows_error_and_is_unfiltered(client, login, demo_user_id):
    login(demo_user_id)
    resp, html = _get(client, date_from=_demo_day(10), date_to=_demo_day(1))
    assert resp.status_code == 200
    assert ERROR_TEXT in html
    assert 'role="alert"' in html
    assert "₹6,398.00" in html
    assert re.search(r'filter-preset is-active"[^>]*>All Time', html)


@pytest.mark.parametrize(
    "params",
    [
        {"date_from": "not-a-date"},
        {"date_to": "2026-13-45"},
        {"date_from": "' OR 1=1 --"},
        {"date_from": "", "date_to": ""},
    ],
)
def test_malformed_dates_are_ignored(client, login, demo_user_id, params):
    login(demo_user_id)
    resp, html = _get(client, **params)
    assert resp.status_code == 200
    assert "₹6,398.00" in html
    assert ERROR_TEXT not in html


def test_empty_range_shows_zeroes_and_range_empty_states(client, login, empty_user_id):
    login(empty_user_id)
    resp, html = _get(client, date_from="2020-01-01", date_to="2020-01-31")
    assert resp.status_code == 200
    assert "₹0.00" in html
    assert "—" in html
    assert "No transactions in this date range." in html
    assert "No spending in this date range." in html


def test_unfiltered_empty_user_keeps_original_empty_state(client, login, empty_user_id):
    login(empty_user_id)
    _, html = _get(client)
    assert "No transactions yet." in html
    assert "in this date range" not in html


def test_fixed_date_range_through_the_route(client, login, dated_user_id):
    login(dated_user_id)
    resp, html = _get(client, date_from="2026-02-01", date_to="2026-03-31")
    assert resp.status_code == 200
    assert "₹500.00" in html
    assert "Feb rent" in html
    assert "Mar dinner" in html
    assert "Jan lunch" not in html


def test_other_users_expenses_never_appear(client, login, dated_user_id):
    login(dated_user_id)
    _, html = _get(client, date_from="2000-01-01", date_to="2999-12-31")
    assert "Jan lunch" in html
    assert "Dinner out" not in html
    assert "Weekly groceries" not in html


def test_filter_form_is_a_get_form(client, login, demo_user_id):
    login(demo_user_id)
    _, html = _get(client)
    assert re.search(r'<form[^>]*method="get"', html)
    assert 'name="date_from"' in html
    assert 'name="date_to"' in html


def test_filtered_page_has_no_dollar_or_inline_style(client, login, demo_user_id):
    login(demo_user_id)
    _, html = _get(client, date_from=_demo_day(1), date_to=_demo_day(10))
    assert "$" not in html
    assert "style=" not in html
