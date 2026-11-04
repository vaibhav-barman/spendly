"""Tests for Step 6: date-range filter on GET /profile.

Written from .claude/specs/06-date-filter-profile-page.md.

Seed facts relied upon (from the task notes): the demo user has 8 expenses on
days 1, 4, 7, 10, 13, 16, 20 and 25 of the CURRENT month, totalling 6398.00.
Tests that need rows in other months insert them for the empty user using
dates computed relative to date.today().
"""
import calendar
import html as html_lib
import re
from datetime import date, timedelta

import pytest
from flask import url_for

from database import db

ERROR_MSG = "Start date must be before end date."
DEMO_TOTAL = "₹6,398.00"

PRESET_LABELS = ["This Month", "Last 3 Months", "Last 6 Months", "All Time"]


# --------------------------------------------------------------------------
# Date helpers (calendar-aligned, computed independently of the app)
# --------------------------------------------------------------------------

def month_start(months_back, today=None):
    """First day of the month `months_back` months before today's month."""
    today = today or date.today()
    year, month = today.year, today.month - months_back
    while month < 1:
        month += 12
        year -= 1
    return date(year, month, 1)


def month_end(today=None):
    today = today or date.today()
    return date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])


def demo_day(d):
    """A day of the current month, matching how the demo expenses are seeded."""
    return date.today().replace(day=d).isoformat()


# --------------------------------------------------------------------------
# HTML helpers
# --------------------------------------------------------------------------

def preset_links(page):
    """Return [(label, href, is_active)] for the quick-select preset links."""
    links = []
    for match in re.finditer(r"(<a\b[^>]*>)\s*(.*?)\s*</a>", page, re.DOTALL):
        tag, label = match.group(1), match.group(2)
        if "filter-preset" not in tag:
            continue
        href = re.search(r'href="([^"]*)"', tag).group(1)
        cls = re.search(r'class="([^"]*)"', tag).group(1).split()
        links.append((re.sub(r"<[^>]+>", "", label).strip(), html_lib.unescape(href), "is-active" in cls))
    return links


def active_preset_labels(page):
    return [label for label, _href, active in preset_links(page) if active]


def preset_href(page, label):
    for lbl, href, _active in preset_links(page):
        if lbl == label:
            return href
    raise AssertionError("Preset %r not found in page" % label)


def input_value(page, name):
    """Value attribute of <input name=...> ('' if absent); None if no such input."""
    tag = re.search(r'<input\b[^>]*\bname="%s"[^>]*>' % re.escape(name), page)
    if tag is None:
        return None
    value = re.search(r'\bvalue="([^"]*)"', tag.group(0))
    return html_lib.unescape(value.group(1)) if value else ""


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

@pytest.fixture
def profile_url(app):
    """Build /profile URLs via url_for (None params are omitted)."""
    def _build(**params):
        with app.test_request_context():
            return url_for("profile", **params)
    return _build


def insert_expense(user_id, amount, category, on_date, description):
    conn = db.get_db()
    try:
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, on_date, description),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def spread_user_id(empty_user_id):
    """Empty user given one expense per calendar-boundary bucket.

    Bucket (distinct amounts so totals identify the included rows):
      Zeta-m0    1st of this month          10   Food
      Zeta-mEnd  last day of this month      5   Food
      Zeta-m1    last day of previous month 20   Transport   (3-month window only)
      Zeta-m2    1st of month 2 back        40   Bills       (first day of 3-month window)
      Zeta-m3    day before that            80   Health      (6-month window only)
      Zeta-m5    1st of month 5 back       160   Entertainment (first day of 6-month window)
      Zeta-m6    day before that           320   Shopping    (All Time only)
    """
    rows = [
        (10, "Food", month_start(0), "Zeta-m0"),
        (5, "Food", month_end(), "Zeta-mEnd"),
        (20, "Transport", month_start(0) - timedelta(days=1), "Zeta-m1"),
        (40, "Bills", month_start(2), "Zeta-m2"),
        (80, "Health", month_start(2) - timedelta(days=1), "Zeta-m3"),
        (160, "Entertainment", month_start(5), "Zeta-m5"),
        (320, "Shopping", month_start(5) - timedelta(days=1), "Zeta-m6"),
    ]
    for amount, category, on_date, description in rows:
        insert_expense(empty_user_id, amount, category, on_date.isoformat(), description)
    return empty_user_id


# preset label -> (months back for start, descriptions shown, descriptions hidden,
#                  categories hidden, expected total)
ALL_DESCS = ["Zeta-m0", "Zeta-mEnd", "Zeta-m1", "Zeta-m2", "Zeta-m3", "Zeta-m5", "Zeta-m6"]
PRESET_CASES = [
    pytest.param("This Month", 0, ["Zeta-m0", "Zeta-mEnd"],
                 ["Transport", "Bills", "Health", "Entertainment", "Shopping"],
                 "₹15.00", id="this-month"),
    pytest.param("Last 3 Months", 2, ["Zeta-m0", "Zeta-mEnd", "Zeta-m1", "Zeta-m2"],
                 ["Health", "Entertainment", "Shopping"],
                 "₹75.00", id="last-3-months"),
    pytest.param("Last 6 Months", 5,
                 ["Zeta-m0", "Zeta-mEnd", "Zeta-m1", "Zeta-m2", "Zeta-m3", "Zeta-m5"],
                 ["Shopping"],
                 "₹315.00", id="last-6-months"),
    pytest.param("All Time", None, ALL_DESCS, [], "₹635.00", id="all-time"),
]


# ==========================================================================
# Auth guard
# ==========================================================================

class TestAuthGuard:
    @pytest.mark.parametrize("params", [
        {},
        {"date_from": "2020-01-01", "date_to": "2030-12-31"},
        {"date_from": "not-a-date"},
        {"date_from": "2030-01-01", "date_to": "2020-01-01"},
    ])
    def test_logged_out_filtered_profile_redirects_to_login(self, client, app, profile_url, params):
        resp = client.get(profile_url(**params))
        with app.test_request_context():
            login_path = url_for("login")
        assert resp.status_code == 302, "Logged-out /profile must redirect"
        assert resp.headers["Location"].endswith(login_path), "Redirect should go to login"
        assert b"Weekly groceries" not in resp.data, "No data may leak to logged-out users"


# ==========================================================================
# Unfiltered behaviour
# ==========================================================================

class TestUnfiltered:
    def test_no_params_shows_all_expenses_and_total(self, client, login, demo_user_id, profile_url):
        login(demo_user_id)
        resp = client.get(profile_url())
        page = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert DEMO_TOTAL in page, "Unfiltered total should be 6,398.00"
        assert "Weekly groceries" in page
        assert "Dinner out" in page
        assert "Shopping" in page

    def test_no_params_highlights_all_time_only(self, client, login, demo_user_id, profile_url):
        login(demo_user_id)
        page = client.get(profile_url()).get_data(as_text=True)
        assert active_preset_labels(page) == ["All Time"], "Only 'All Time' should be active"

    def test_no_params_shows_no_error_and_no_showing_label(self, client, login, demo_user_id, profile_url):
        login(demo_user_id)
        page = client.get(profile_url()).get_data(as_text=True)
        assert ERROR_MSG not in page
        assert "Showing" not in page, "'Showing ...' label is only for active filters"
        assert 'role="alert"' not in page

    def test_no_params_date_inputs_are_empty(self, client, login, demo_user_id, profile_url):
        login(demo_user_id)
        page = client.get(profile_url()).get_data(as_text=True)
        assert input_value(page, "date_from") == ""
        assert input_value(page, "date_to") == ""

    def test_empty_user_unfiltered_keeps_existing_empty_wording(self, client, login, empty_user_id, profile_url):
        login(empty_user_id)
        page = client.get(profile_url()).get_data(as_text=True)
        assert "No transactions yet." in page
        assert "in this date range" not in page


# ==========================================================================
# Filter bar structure
# ==========================================================================

class TestFilterBar:
    def test_four_presets_in_spec_order(self, client, login, demo_user_id, profile_url):
        login(demo_user_id)
        page = client.get(profile_url()).get_data(as_text=True)
        assert [label for label, _h, _a in preset_links(page)] == PRESET_LABELS

    def test_custom_form_is_get_with_two_date_inputs_and_apply(self, client, login, demo_user_id, profile_url):
        login(demo_user_id)
        page = client.get(profile_url()).get_data(as_text=True)
        assert re.search(r'<form\b[^>]*method="get"', page, re.IGNORECASE), "Custom range form must use GET"
        assert len(re.findall(r'<input\b[^>]*type="date"', page)) == 2
        assert input_value(page, "date_from") is not None
        assert input_value(page, "date_to") is not None
        assert "Apply" in page
        assert re.search(r'type="submit"', page), "Apply must be a submit control"

    def test_filter_bar_sits_between_user_card_and_summary_stats(self, client, login, demo_user_id, profile_url):
        login(demo_user_id)
        page = client.get(profile_url()).get_data(as_text=True)
        assert page.index("demo@spendly.com") < page.index("This Month") < page.index(DEMO_TOTAL)

    def test_all_time_preset_href_is_clean_profile_url(self, client, login, demo_user_id, profile_url):
        login(demo_user_id)
        page = client.get(profile_url()).get_data(as_text=True)
        href = preset_href(page, "All Time")
        assert "?" not in href, "All Time must pass no query params"
        assert href.endswith(profile_url())

    @pytest.mark.parametrize("label,months_back", [
        ("This Month", 0), ("Last 3 Months", 2), ("Last 6 Months", 5),
    ])
    def test_preset_hrefs_are_calendar_aligned_and_end_on_month_end(
            self, client, login, demo_user_id, label, months_back):
        login(demo_user_id)
        href = preset_href(client.get("/profile").get_data(as_text=True), label)
        assert "date_from=%s" % month_start(months_back).isoformat() in href, (
            "%s should start on the 1st of the month %d month(s) back" % (label, months_back))
        assert "date_to=%s" % month_end().isoformat() in href, (
            "%s should end on the last day of the current month" % label)


# ==========================================================================
# Presets (calendar aligned ranges + highlight)
# ==========================================================================

class TestPresets:
    @pytest.mark.parametrize("label,months_back,shown,hidden_cats,total", PRESET_CASES)
    def test_clicking_preset_filters_all_sections(
            self, client, login, spread_user_id, label, months_back, shown, hidden_cats, total):
        login(spread_user_id)
        href = preset_href(client.get("/profile").get_data(as_text=True), label)
        resp = client.get(href)
        page = resp.get_data(as_text=True)
        assert resp.status_code == 200
        for desc in shown:
            assert desc in page, "%s: expected %s to be listed" % (label, desc)
        for desc in set(ALL_DESCS) - set(shown):
            assert desc not in page, "%s: %s is outside the range" % (label, desc)
        assert total in page, "%s: summary total should be %s" % (label, total)
        for cat in hidden_cats:
            assert cat not in page, "%s: category %s should not appear anywhere" % (label, cat)

    @pytest.mark.parametrize("label,months_back,shown,hidden_cats,total", PRESET_CASES)
    def test_clicked_preset_is_the_only_one_highlighted(
            self, client, login, spread_user_id, label, months_back, shown, hidden_cats, total):
        login(spread_user_id)
        href = preset_href(client.get("/profile").get_data(as_text=True), label)
        page = client.get(href).get_data(as_text=True)
        assert active_preset_labels(page) == [label]

    @pytest.mark.parametrize("label,months_back", [
        ("This Month", 0), ("Last 3 Months", 2), ("Last 6 Months", 5),
    ])
    def test_explicit_query_equal_to_preset_range_highlights_that_preset(
            self, client, login, demo_user_id, profile_url, label, months_back):
        login(demo_user_id)
        url = profile_url(date_from=month_start(months_back).isoformat(),
                          date_to=month_end().isoformat())
        page = client.get(url).get_data(as_text=True)
        assert active_preset_labels(page) == [label]

    @pytest.mark.parametrize("label,months_back", [
        ("This Month", 0), ("Last 3 Months", 2), ("Last 6 Months", 5),
    ])
    def test_preset_prefills_date_inputs_with_active_range(
            self, client, login, demo_user_id, profile_url, label, months_back):
        login(demo_user_id)
        url = profile_url(date_from=month_start(months_back).isoformat(),
                          date_to=month_end().isoformat())
        page = client.get(url).get_data(as_text=True)
        assert input_value(page, "date_from") == month_start(months_back).isoformat()
        assert input_value(page, "date_to") == month_end().isoformat()

    def test_this_month_includes_first_and_last_day_of_month(self, client, login, spread_user_id, profile_url):
        login(spread_user_id)
        page = client.get(profile_url(date_from=month_start(0).isoformat(),
                                      date_to=month_end().isoformat())).get_data(as_text=True)
        assert "Zeta-m0" in page, "1st of month must be included"
        assert "Zeta-mEnd" in page, "last day of month must be included"
        assert "Zeta-m1" not in page, "last day of previous month must be excluded"

    def test_demo_user_this_month_shows_all_seeded_expenses(self, client, login, demo_user_id, profile_url):
        login(demo_user_id)
        page = client.get(profile_url(date_from=month_start(0).isoformat(),
                                      date_to=month_end().isoformat())).get_data(as_text=True)
        assert DEMO_TOTAL in page
        assert "Weekly groceries" in page and "Dinner out" in page
        assert "Showing" in page, "A 'Showing ...' label is expected when filtered"
        assert active_preset_labels(page) == ["This Month"]

    def test_all_time_link_removes_active_filter(self, client, login, spread_user_id, profile_url):
        login(spread_user_id)
        filtered = client.get(profile_url(date_from=month_start(0).isoformat(),
                                          date_to=month_end().isoformat())).get_data(as_text=True)
        assert "Zeta-m6" not in filtered
        page = client.get(preset_href(filtered, "All Time")).get_data(as_text=True)
        assert "Zeta-m6" in page and "Zeta-m0" in page
        assert "₹635.00" in page
        assert "Showing" not in page
        assert active_preset_labels(page) == ["All Time"]
        assert input_value(page, "date_from") == "" and input_value(page, "date_to") == ""


# ==========================================================================
# Custom ranges
# ==========================================================================

class TestCustomRange:
    def test_range_is_inclusive_at_both_ends(self, client, login, demo_user_id, profile_url):
        login(demo_user_id)
        page = client.get(profile_url(date_from=demo_day(4), date_to=demo_day(13))).get_data(as_text=True)
        # Days 4, 7, 10, 13 -> 120 + 1850 + 600 + 499 = 3069
        for desc in ("Auto rickshaw to office", "Electricity bill", "Pharmacy", "Movie tickets"):
            assert desc in page, "%s lies within the inclusive range" % desc
        for desc in ("Weekly groceries", "New shirt", "Birthday gift", "Dinner out"):
            assert desc not in page, "%s lies outside the range" % desc
        assert "₹3,069.00" in page
        assert DEMO_TOTAL not in page

    def test_category_breakdown_respects_range(self, client, login, demo_user_id, profile_url):
        login(demo_user_id)
        page = client.get(profile_url(date_from=demo_day(4), date_to=demo_day(13))).get_data(as_text=True)
        # Shopping (day 16) and Food (days 1, 25) are entirely outside the range.
        assert "Shopping" not in page
        assert "Food" not in page
        assert "Bills" in page, "Bills (day 7) is the top category in range"

    def test_single_day_range_includes_that_day(self, client, login, demo_user_id, profile_url):
        login(demo_user_id)
        page = client.get(profile_url(date_from=demo_day(7), date_to=demo_day(7))).get_data(as_text=True)
        assert "Electricity bill" in page
        assert "₹1,850.00" in page
        assert "Auto rickshaw to office" not in page and "Pharmacy" not in page
        assert ERROR_MSG not in page, "from == to is a valid range"

    def test_from_only_is_open_ended_upwards(self, client, login, demo_user_id, profile_url):
        login(demo_user_id)
        page = client.get(profile_url(date_from=demo_day(20))).get_data(as_text=True)
        assert "Birthday gift" in page and "Dinner out" in page
        assert "New shirt" not in page and "Weekly groceries" not in page
        assert "₹580.00" in page  # 300 + 280

    def test_to_only_is_open_ended_downwards(self, client, login, demo_user_id, profile_url):
        login(demo_user_id)
        page = client.get(profile_url(date_to=demo_day(4))).get_data(as_text=True)
        assert "Weekly groceries" in page and "Auto rickshaw to office" in page
        assert "Electricity bill" not in page and "Dinner out" not in page
        assert "₹570.00" in page  # 450 + 120

    def test_from_only_reaches_future_dates_in_other_months(self, client, login, spread_user_id, profile_url):
        login(spread_user_id)
        page = client.get(profile_url(date_from=month_start(2).isoformat())).get_data(as_text=True)
        assert "Zeta-m2" in page and "Zeta-mEnd" in page
        assert "Zeta-m3" not in page

    def test_to_only_includes_old_expenses(self, client, login, spread_user_id, profile_url):
        login(spread_user_id)
        page = client.get(profile_url(date_to=(month_start(0) - timedelta(days=1)).isoformat())).get_data(as_text=True)
        assert "Zeta-m1" in page and "Zeta-m6" in page
        assert "Zeta-m0" not in page and "Zeta-mEnd" not in page

    def test_custom_range_prefills_inputs_and_shows_label(self, client, login, demo_user_id, profile_url):
        login(demo_user_id)
        page = client.get(profile_url(date_from=demo_day(4), date_to=demo_day(13))).get_data(as_text=True)
        assert input_value(page, "date_from") == demo_day(4)
        assert input_value(page, "date_to") == demo_day(13)
        assert "Showing" in page

    def test_one_sided_range_prefills_only_the_given_input(self, client, login, demo_user_id, profile_url):
        login(demo_user_id)
        page = client.get(profile_url(date_from=demo_day(20))).get_data(as_text=True)
        assert input_value(page, "date_from") == demo_day(20)
        assert input_value(page, "date_to") == ""
        assert "Showing" in page

    def test_custom_range_matching_no_preset_highlights_no_preset(self, client, login, demo_user_id, profile_url):
        login(demo_user_id)
        page = client.get(profile_url(date_from=demo_day(4), date_to=demo_day(13))).get_data(as_text=True)
        assert active_preset_labels(page) == [], "No quick preset equals this custom range"
        assert "is-active" in page, "The custom range controls must show an active state"

    def test_one_sided_range_does_not_highlight_all_time(self, client, login, demo_user_id, profile_url):
        login(demo_user_id)
        page = client.get(profile_url(date_from=demo_day(20))).get_data(as_text=True)
        assert "All Time" not in active_preset_labels(page)

    def test_form_submission_with_both_fields_empty_is_unfiltered(self, client, login, demo_user_id, profile_url):
        login(demo_user_id)
        resp = client.get(profile_url(date_from="", date_to=""))
        page = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert DEMO_TOTAL in page
        assert ERROR_MSG not in page
        assert active_preset_labels(page) == ["All Time"]

    def test_range_not_changing_across_year_boundaries(self, client, login, empty_user_id, profile_url):
        login(empty_user_id)
        insert_expense(empty_user_id, 11, "Food", "2023-12-31", "Boundary-A")
        insert_expense(empty_user_id, 22, "Food", "2024-01-01", "Boundary-B")
        insert_expense(empty_user_id, 33, "Food", "2024-01-31", "Boundary-C")
        insert_expense(empty_user_id, 44, "Food", "2024-02-01", "Boundary-D")
        page = client.get(profile_url(date_from="2024-01-01", date_to="2024-01-31")).get_data(as_text=True)
        assert "Boundary-B" in page and "Boundary-C" in page
        assert "Boundary-A" not in page and "Boundary-D" not in page
        assert "₹55.00" in page

    def test_recent_list_keeps_limit_of_ten_while_stats_count_all(self, client, login, empty_user_id, profile_url):
        login(empty_user_id)
        for i in range(1, 13):
            insert_expense(empty_user_id, 10, "Food", "2024-02-%02d" % i, "Bulk-%02d" % i)
        page = client.get(profile_url(date_from="2024-02-01", date_to="2024-02-29")).get_data(as_text=True)
        assert "₹120.00" in page, "Stats must total all 12 expenses in range"
        for i in range(3, 13):
            assert "Bulk-%02d" % i in page, "Newest 10 rows should be listed"
        assert "Bulk-01" not in page and "Bulk-02" not in page, "List is capped at 10 rows"


# ==========================================================================
# Inverted range
# ==========================================================================

class TestInvertedRange:
    def test_inverted_range_shows_error_message(self, client, login, demo_user_id, profile_url):
        login(demo_user_id)
        resp = client.get(profile_url(date_from=demo_day(25), date_to=demo_day(1)))
        page = resp.get_data(as_text=True)
        assert resp.status_code == 200, "Bad input must never cause an HTTP error"
        assert ERROR_MSG in page
        assert 'role="alert"' in page

    def test_inverted_range_falls_back_to_unfiltered_data(self, client, login, demo_user_id, profile_url):
        login(demo_user_id)
        page = client.get(profile_url(date_from=demo_day(25), date_to=demo_day(1))).get_data(as_text=True)
        assert DEMO_TOTAL in page
        for desc in ("Weekly groceries", "Dinner out", "New shirt", "Pharmacy"):
            assert desc in page, "Fallback view must show all expenses (%s)" % desc
        assert "Showing" not in page, "No filter is active after fallback"
        assert active_preset_labels(page) == ["All Time"]

    def test_inverted_range_across_months_with_spread_data(self, client, login, spread_user_id, profile_url):
        login(spread_user_id)
        page = client.get(profile_url(date_from=month_end().isoformat(),
                                      date_to=month_start(5).isoformat())).get_data(as_text=True)
        assert ERROR_MSG in page
        assert "₹635.00" in page
        assert "Zeta-m6" in page and "Zeta-m0" in page

    def test_one_day_apart_inverted_range_is_error(self, client, login, demo_user_id, profile_url):
        login(demo_user_id)
        page = client.get(profile_url(date_from=demo_day(8), date_to=demo_day(7))).get_data(as_text=True)
        assert ERROR_MSG in page

    @pytest.mark.parametrize("params", [
        {},
        {"date_from": "2020-01-01", "date_to": "2030-12-31"},
        {"date_from": "2020-01-01"},
        {"date_to": "2030-12-31"},
    ])
    def test_error_message_absent_for_valid_input(self, client, login, demo_user_id, profile_url, params):
        login(demo_user_id)
        page = client.get(profile_url(**params)).get_data(as_text=True)
        assert ERROR_MSG not in page
        assert 'role="alert"' not in page


# ==========================================================================
# Malformed input
# ==========================================================================

MALFORMED = [
    "not-a-date",
    "2025-13-01",
    "2025-02-30",
    "01-02-2025",
    "2025/01/01",
    "20250101",
    "   ",
    "'; DROP TABLE expenses; --",
    "' OR '1'='1",
    "<script>alert(1)</script>",
    "9" * 500,
]


class TestMalformedInput:
    @pytest.mark.parametrize("value", MALFORMED)
    def test_malformed_date_from_is_ignored(self, client, login, demo_user_id, profile_url, value):
        login(demo_user_id)
        resp = client.get(profile_url(date_from=value))
        page = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert DEMO_TOTAL in page, "Malformed date_from must be treated as an open bound"
        assert "Weekly groceries" in page and "Dinner out" in page
        assert ERROR_MSG not in page

    @pytest.mark.parametrize("value", MALFORMED)
    def test_malformed_date_to_is_ignored(self, client, login, demo_user_id, profile_url, value):
        login(demo_user_id)
        resp = client.get(profile_url(date_to=value))
        page = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert DEMO_TOTAL in page
        assert "Weekly groceries" in page and "Dinner out" in page
        assert ERROR_MSG not in page

    def test_both_malformed_is_unfiltered_with_all_time_active(self, client, login, demo_user_id, profile_url):
        login(demo_user_id)
        resp = client.get(profile_url(date_from="foo", date_to="bar"))
        page = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert DEMO_TOTAL in page
        assert active_preset_labels(page) == ["All Time"]
        assert "Showing" not in page

    def test_malformed_from_with_valid_to_filters_by_to_only(self, client, login, demo_user_id, profile_url):
        login(demo_user_id)
        page = client.get(profile_url(date_from="not-a-date", date_to=demo_day(4))).get_data(as_text=True)
        assert "₹570.00" in page
        assert "Weekly groceries" in page and "Electricity bill" not in page

    def test_valid_from_with_malformed_to_filters_by_from_only(self, client, login, demo_user_id, profile_url):
        login(demo_user_id)
        page = client.get(profile_url(date_from=demo_day(20), date_to="2025-02-30")).get_data(as_text=True)
        assert "₹580.00" in page
        assert "Dinner out" in page and "New shirt" not in page

    def test_malformed_values_are_not_echoed_into_date_inputs(self, client, login, demo_user_id, profile_url):
        login(demo_user_id)
        page = client.get(profile_url(date_from="<script>alert(1)</script>")).get_data(as_text=True)
        assert "<script>alert(1)</script>" not in page, "Raw user input must never be reflected"
        assert input_value(page, "date_from") == ""

    def test_sql_injection_attempt_leaves_data_intact(self, client, login, demo_user_id, profile_url):
        login(demo_user_id)
        client.get(profile_url(date_from="'; DROP TABLE expenses; --",
                               date_to="' OR 1=1 --"))
        conn = db.get_db()
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM expenses WHERE user_id = ?", (demo_user_id,)
            ).fetchone()[0]
        finally:
            conn.close()
        assert count == 8, "Expenses table must be untouched by injection attempts"

    def test_unknown_extra_params_are_harmless(self, client, login, demo_user_id, profile_url):
        login(demo_user_id)
        resp = client.get(profile_url(foo="bar", date_from=demo_day(20)))
        assert resp.status_code == 200
        assert "₹580.00" in resp.get_data(as_text=True)


# ==========================================================================
# Currency and empty results
# ==========================================================================

class TestCurrencyAndEmptyRange:
    @pytest.mark.parametrize("params", [
        {},
        {"date_from": "this-is-bad"},
        {"date_from": "2000-01-01", "date_to": "2000-01-31"},
        {"date_from": "demo-day-4", "date_to": "demo-day-13"},
        {"date_from": "demo-day-25", "date_to": "demo-day-1"},
    ])
    def test_rupee_symbol_always_shown_and_no_dollar(self, client, login, demo_user_id, profile_url, params):
        login(demo_user_id)
        resolved = {
            k: demo_day(int(v.rsplit("-", 1)[1])) if v.startswith("demo-day-") else v
            for k, v in params.items()
        }
        page = client.get(profile_url(**resolved)).get_data(as_text=True)
        assert "₹" in page, "Amounts must keep the rupee symbol under any filter"
        assert "$" not in page
        assert "style=" not in page, "No inline styles"

    def test_rupee_symbol_on_rows_in_filtered_view(self, client, login, demo_user_id, profile_url):
        login(demo_user_id)
        page = client.get(profile_url(date_from=demo_day(7), date_to=demo_day(7))).get_data(as_text=True)
        assert page.count("₹") >= 2, "Total and the listed row should both show the rupee symbol"

    def test_empty_range_shows_zero_total_and_range_specific_empty_states(
            self, client, login, demo_user_id, profile_url):
        login(demo_user_id)
        resp = client.get(profile_url(date_from="2000-01-01", date_to="2000-01-31"))
        page = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert "₹0.00" in page
        assert "No transactions in this date range." in page
        assert "No spending in this date range." in page
        assert "No transactions yet." not in page
        assert DEMO_TOTAL not in page
        for desc in ("Weekly groceries", "Dinner out", "New shirt"):
            assert desc not in page
        assert "Showing" in page

    def test_empty_range_for_user_with_data_elsewhere_has_no_error_alert(
            self, client, login, spread_user_id, profile_url):
        login(spread_user_id)
        resp = client.get(profile_url(date_from="1999-01-01", date_to="1999-12-31"))
        page = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert "₹0.00" in page
        assert 'role="alert"' not in page
        assert "Zeta-" not in page

    def test_empty_user_with_filter_gets_range_wording_and_zero_total(
            self, client, login, empty_user_id, profile_url):
        login(empty_user_id)
        resp = client.get(profile_url(date_from="2024-01-01", date_to="2024-12-31"))
        page = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert "₹0.00" in page
        assert "No transactions in this date range." in page
        assert "No spending in this date range." in page

    def test_empty_range_preset_this_month_for_user_with_only_old_data(
            self, client, login, empty_user_id, profile_url):
        login(empty_user_id)
        insert_expense(empty_user_id, 99, "Food", "2001-05-05", "Ancient-lunch")
        page = client.get(profile_url(date_from=month_start(0).isoformat(),
                                      date_to=month_end().isoformat())).get_data(as_text=True)
        assert "Ancient-lunch" not in page
        assert "₹0.00" in page
        assert "No transactions in this date range." in page
        assert active_preset_labels(page) == ["This Month"]


# ==========================================================================
# Per-user isolation
# ==========================================================================

class TestUserIsolation:
    @pytest.fixture
    def other_user_expense(self, empty_user_id):
        insert_expense(empty_user_id, 777, "Other", demo_day(10), "Zeta-Isolation")
        return empty_user_id

    @pytest.mark.parametrize("params", [
        {},
        {"date_from": "demo-day-10", "date_to": "demo-day-10"},
        {"date_from": "demo-day-1"},
        {"date_to": "demo-day-25"},
    ])
    def test_demo_user_never_sees_other_users_expenses(
            self, client, login, demo_user_id, other_user_expense, profile_url, params):
        resolved = {
            k: demo_day(int(v.rsplit("-", 1)[1])) if v.startswith("demo-day-") else v
            for k, v in params.items()
        }
        login(demo_user_id)
        page = client.get(profile_url(**resolved)).get_data(as_text=True)
        assert "Zeta-Isolation" not in page
        assert "₹777.00" not in page
        assert "₹7,175.00" not in page, "Other user's 777 must not be added to the demo total"

    def test_demo_user_filtered_total_unaffected_by_other_user(
            self, client, login, demo_user_id, other_user_expense, profile_url):
        login(demo_user_id)
        page = client.get(profile_url(date_from=demo_day(10), date_to=demo_day(10))).get_data(as_text=True)
        assert "Pharmacy" in page and "₹600.00" in page

    def test_other_user_sees_only_own_expenses_under_filter(
            self, client, login, other_user_expense, profile_url):
        login(other_user_expense)
        page = client.get(profile_url(date_from=demo_day(1), date_to=demo_day(25))).get_data(as_text=True)
        assert "Zeta-Isolation" in page
        assert "₹777.00" in page
        assert "Pharmacy" not in page and "Electricity bill" not in page
        assert DEMO_TOTAL not in page

    def test_switching_session_user_switches_data(
            self, client, login, demo_user_id, other_user_expense, profile_url):
        url = profile_url(date_from=demo_day(10), date_to=demo_day(10))
        login(demo_user_id)
        assert "Pharmacy" in client.get(url).get_data(as_text=True)
        login(other_user_expense)
        page = client.get(url).get_data(as_text=True)
        assert "Zeta-Isolation" in page and "Pharmacy" not in page


# ==========================================================================
# database/db.py helpers: optional date_from / date_to
# ==========================================================================

@pytest.fixture
def feb_user_id(empty_user_id):
    """Fixed-date rows around February 2024 for helper-level tests."""
    rows = [
        (1000, "Shopping", "2024-01-31", "before"),
        (100, "Food", "2024-02-01", "feb-first"),
        (200, "Food", "2024-02-15", "feb-mid"),
        (50, "Bills", "2024-02-29", "feb-last"),
        (900, "Shopping", "2024-03-01", "after"),
    ]
    for amount, category, on_date, description in rows:
        insert_expense(empty_user_id, amount, category, on_date, description)
    return empty_user_id


class TestGetExpenseSummary:
    def test_no_bounds_matches_explicit_none(self, demo_user_id):
        assert db.get_expense_summary(demo_user_id) == db.get_expense_summary(
            demo_user_id, date_from=None, date_to=None)

    def test_no_bounds_returns_unfiltered_totals(self, demo_user_id):
        result = db.get_expense_summary(demo_user_id)
        assert result["total_spent"] == pytest.approx(6398.00)
        assert result["transaction_count"] == 8
        assert result["top_category"] == "Shopping"

    def test_return_shape_unchanged_when_filtered(self, feb_user_id):
        result = db.get_expense_summary(feb_user_id, date_from="2024-02-01", date_to="2024-02-29")
        assert set(result) == {"total_spent", "transaction_count", "top_category"}

    def test_both_bounds_are_inclusive(self, feb_user_id):
        result = db.get_expense_summary(feb_user_id, date_from="2024-02-01", date_to="2024-02-29")
        assert result["total_spent"] == pytest.approx(350.00)
        assert result["transaction_count"] == 3

    def test_from_only(self, feb_user_id):
        result = db.get_expense_summary(feb_user_id, date_from="2024-02-15")
        assert result["total_spent"] == pytest.approx(200 + 50 + 900)
        assert result["transaction_count"] == 3

    def test_to_only(self, feb_user_id):
        result = db.get_expense_summary(feb_user_id, date_to="2024-02-01")
        assert result["total_spent"] == pytest.approx(1100.00)
        assert result["transaction_count"] == 2

    def test_top_category_is_computed_within_range(self, feb_user_id):
        overall = db.get_expense_summary(feb_user_id)
        in_range = db.get_expense_summary(feb_user_id, date_from="2024-02-01", date_to="2024-02-29")
        assert overall["top_category"] == "Shopping"
        assert in_range["top_category"] == "Food", "Top category must ignore out-of-range rows"

    def test_empty_range_returns_zeroes(self, feb_user_id):
        result = db.get_expense_summary(feb_user_id, date_from="2000-01-01", date_to="2000-12-31")
        assert result == {"total_spent": 0.0, "transaction_count": 0, "top_category": None}

    def test_only_target_user_counted(self, feb_user_id, demo_user_id):
        result = db.get_expense_summary(feb_user_id, date_from=demo_day(1), date_to=demo_day(25))
        assert result["transaction_count"] == 0, "Demo user's rows must not leak in"
        demo = db.get_expense_summary(demo_user_id, date_from="2024-01-01", date_to="2024-12-31")
        assert demo["transaction_count"] == 0, "Other user's rows must not leak in"

    def test_hostile_string_bound_is_treated_as_data(self, demo_user_id):
        payload = "'; DROP TABLE expenses; --"
        result = db.get_expense_summary(demo_user_id, date_from=payload)
        assert isinstance(result, dict)
        assert db.get_expense_summary(demo_user_id)["transaction_count"] == 8


class TestGetRecentExpenses:
    def test_no_bounds_matches_explicit_none(self, demo_user_id):
        assert db.get_recent_expenses(demo_user_id) == db.get_recent_expenses(
            demo_user_id, date_from=None, date_to=None)

    def test_no_bounds_returns_all_newest_first(self, demo_user_id):
        rows = db.get_recent_expenses(demo_user_id)
        assert len(rows) == 8
        assert rows[0]["description"] == "Dinner out"
        assert rows[-1]["description"] == "Weekly groceries"

    def test_row_shape_unchanged_when_filtered(self, feb_user_id):
        rows = db.get_recent_expenses(feb_user_id, date_from="2024-02-01", date_to="2024-02-29")
        assert rows, "Expected rows in range"
        assert set(rows[0]) == {"date", "description", "category", "amount"}

    def test_both_bounds_are_inclusive_and_ordered_newest_first(self, feb_user_id):
        rows = db.get_recent_expenses(feb_user_id, date_from="2024-02-01", date_to="2024-02-29")
        assert [r["description"] for r in rows] == ["feb-last", "feb-mid", "feb-first"]

    def test_from_only(self, feb_user_id):
        rows = db.get_recent_expenses(feb_user_id, date_from="2024-02-29")
        assert [r["description"] for r in rows] == ["after", "feb-last"]

    def test_to_only(self, feb_user_id):
        rows = db.get_recent_expenses(feb_user_id, date_to="2024-02-01")
        assert [r["description"] for r in rows] == ["feb-first", "before"]

    def test_empty_range_returns_empty_list(self, feb_user_id):
        assert db.get_recent_expenses(feb_user_id, date_from="2000-01-01", date_to="2000-01-02") == []

    def test_limit_still_applies_with_filter(self, empty_user_id):
        for i in range(1, 13):
            insert_expense(empty_user_id, 1, "Food", "2024-02-%02d" % i, "row-%02d" % i)
        default = db.get_recent_expenses(empty_user_id, date_from="2024-02-01", date_to="2024-02-29")
        assert len(default) == 10, "Default limit of 10 must be unchanged"
        assert default[0]["description"] == "row-12"
        limited = db.get_recent_expenses(empty_user_id, limit=3, date_from="2024-02-01", date_to="2024-02-29")
        assert [r["description"] for r in limited] == ["row-12", "row-11", "row-10"]

    def test_only_target_user_rows_returned(self, feb_user_id, demo_user_id):
        assert db.get_recent_expenses(feb_user_id, date_from=demo_day(1), date_to=demo_day(25)) == []
        assert db.get_recent_expenses(demo_user_id, date_from="2024-01-01", date_to="2024-12-31") == []

    def test_hostile_string_bound_is_treated_as_data(self, demo_user_id):
        rows = db.get_recent_expenses(demo_user_id, date_to="' OR 1=1; DROP TABLE expenses; --")
        assert isinstance(rows, list)
        assert len(db.get_recent_expenses(demo_user_id)) == 8


class TestGetCategoryBreakdown:
    def test_no_bounds_matches_explicit_none(self, demo_user_id):
        assert db.get_category_breakdown(demo_user_id) == db.get_category_breakdown(
            demo_user_id, date_from=None, date_to=None)

    def test_no_bounds_returns_all_categories(self, demo_user_id):
        result = db.get_category_breakdown(demo_user_id)
        by_name = {c["name"]: c for c in result}
        assert set(by_name) == {"Food", "Transport", "Bills", "Health",
                                "Entertainment", "Shopping", "Other"}
        assert by_name["Food"]["total"] == pytest.approx(730.00)
        assert result[0]["name"] == "Shopping", "Highest total first"

    def test_shape_unchanged_when_filtered(self, feb_user_id):
        result = db.get_category_breakdown(feb_user_id, date_from="2024-02-01", date_to="2024-02-29")
        assert result and set(result[0]) == {"name", "total", "percent"}

    def test_both_bounds_inclusive_and_exclude_outside_rows(self, feb_user_id):
        result = db.get_category_breakdown(feb_user_id, date_from="2024-02-01", date_to="2024-02-29")
        by_name = {c["name"]: c["total"] for c in result}
        assert by_name == {"Food": pytest.approx(300.00), "Bills": pytest.approx(50.00)}

    def test_percentages_are_relative_to_filtered_total(self, feb_user_id):
        result = db.get_category_breakdown(feb_user_id, date_from="2024-02-01", date_to="2024-02-29")
        by_name = {c["name"]: c["percent"] for c in result}
        assert by_name["Food"] == round(300 / 350 * 100)
        assert by_name["Bills"] == round(50 / 350 * 100)

    def test_ordering_by_total_desc_within_range(self, feb_user_id):
        result = db.get_category_breakdown(feb_user_id, date_from="2024-02-01", date_to="2024-02-29")
        assert [c["name"] for c in result] == ["Food", "Bills"]

    def test_from_only(self, feb_user_id):
        result = db.get_category_breakdown(feb_user_id, date_from="2024-03-01")
        assert [c["name"] for c in result] == ["Shopping"]
        assert result[0]["percent"] == 100

    def test_to_only(self, feb_user_id):
        result = db.get_category_breakdown(feb_user_id, date_to="2024-01-31")
        assert [c["name"] for c in result] == ["Shopping"]
        assert result[0]["total"] == pytest.approx(1000.00)

    def test_empty_range_returns_empty_list(self, feb_user_id):
        assert db.get_category_breakdown(feb_user_id, date_from="2000-01-01", date_to="2000-12-31") == []

    def test_only_target_user_rows_counted(self, feb_user_id, demo_user_id):
        assert db.get_category_breakdown(feb_user_id, date_from=demo_day(1), date_to=demo_day(25)) == []
        assert db.get_category_breakdown(demo_user_id, date_from="2024-01-01", date_to="2024-12-31") == []

    def test_hostile_string_bound_is_treated_as_data(self, demo_user_id):
        result = db.get_category_breakdown(demo_user_id, date_from="'; DROP TABLE expenses; --")
        assert isinstance(result, list)
        assert len(db.get_recent_expenses(demo_user_id)) == 8
