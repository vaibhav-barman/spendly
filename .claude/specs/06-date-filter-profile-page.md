# Spec: Date Filter for Profile Page

## Overview
Step 6 adds a date-range filter to the existing `/profile` route so users can
narrow the transaction list, summary stats, and category breakdown to a specific
period. The filter is driven entirely by query-string parameters (`date_from` and
`date_to`) on `GET /profile`, requiring no new routes. A compact filter bar
with four quick-select presets ("This Month", "Last 3 Months", "Last 6 Months",
"All Time") and two `<input type="date">` fields lets users pick any custom range.
All three data sections (summary stats, recent transactions, category breakdown)
must respect the active date filter.

## Depends on
- Step 1: Database setup (`expenses` table with a `date` column must exist)
- Step 4: Profile page UI (template with all four sections must exist)
- Step 5: Backend routes for profile page (`get_expense_summary`,
  `get_recent_expenses`, `get_category_breakdown` in `database/db.py` must exist
  and be wired to the `/profile` route)

## Routes
No new routes. The existing `GET /profile` route is modified to read optional
query parameters:
- `date_from` — ISO date string `YYYY-MM-DD`, inclusive lower bound
- `date_to`   — ISO date string `YYYY-MM-DD`, inclusive upper bound

Each parameter is validated independently. A missing or malformed parameter is
an open bound, so a single valid date still filters (only `date_from` means "from
that date onwards", only `date_to` means "up to that date"). With neither valid,
the view is unfiltered ("All Time"). Bad input never causes an HTTP error.

## Database changes
No schema changes. The `expenses.date` column (`TEXT`, `YYYY-MM-DD`) compares
correctly as a string in SQLite.

## Templates
- **Modify**: `templates/profile.html`
  - Add a filter bar between the user card and the summary stats row containing:
    - Four quick-select preset links: "This Month", "Last 3 Months",
      "Last 6 Months", "All Time" — each a link to `/profile` with the
      appropriate `date_from`/`date_to` query params
    - A custom range form (`method="get"`) with two `<input type="date">` fields
      (`date_from`, `date_to`) and an "Apply" submit button, pre-filled with the
      active range
    - The currently active preset or custom range must be visually highlighted
      (`is-active` state)
    - A `filter_error` message (`role="alert"`) when the range is invalid
    - A short "Showing …" label when a filter is active
  - When a filter is active and nothing matches, the empty states read "No
    transactions in this date range." and "No spending in this date range.".
    Unfiltered empty states keep their existing wording.
  - No structural changes to any existing section; only Jinja variables fed
    to them change when the filter is active

## Files to change
- `app.py`
  - Private helpers `_parse_iso_date`, `_parse_date_range` and `_build_presets`
  - In the `profile()` view: read and validate `date_from` and `date_to`, pass
    them to each query helper, and pass `date_from`, `date_to`, `is_filtered`,
    `presets`, `active_key` and `filter_error` to the template. The old
    `_profile_*` wrappers are removed; the route calls the db helpers directly.
- `database/db.py`
  - `get_expense_summary(user_id, date_from=None, date_to=None)`
  - `get_recent_expenses(user_id, limit=10, date_from=None, date_to=None)`
  - `get_category_breakdown(user_id, date_from=None, date_to=None)`
  - Each adds the constant fragment
    `AND (? IS NULL OR date >= ?) AND (? IS NULL OR date <= ?)` to its
    `WHERE user_id = ?` queries (both queries in `get_expense_summary`). Return
    shapes are unchanged. Ordering, `LIMIT` and percentage logic are unchanged.
- `templates/profile.html` — add filter bar (see Templates section)
- `static/css/profile.css` — add styles for the filter bar and active state
  using CSS variables only

## Files to create
- `tests/test_date_filter.py`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — never string-format dates into SQL; use `?`
  placeholders even for the date-range bounds
- Passwords hashed with werkzeug (no changes to auth in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles
- Date validation in `app.py`: attempt `datetime.strptime(value, "%Y-%m-%d")`;
  on `ValueError`, treat that parameter as an open bound
- Preset links must be generated with `url_for("profile", date_from=..., date_to=...)`
  — never hardcoded URL strings in the template
- When `date_from` and `date_to` are both absent, all three query helpers must
  behave identically to their Step 5 behaviour (unfiltered)
- If `date_from > date_to` after validation, treat both as absent (no filter)
  and show the message "Start date must be before end date." via the
  `filter_error` template variable (the app has no flash-message support)
- The "All Time" preset must pass no query params (clean `/profile` URL)
- Preset date calculations must be computed in `app.py`, not in the template.
  Presets are calendar-aligned and all end on the last day of the current month:
  - This Month: 1st of the current month
  - Last 3 Months: 1st of the month two months back
  - Last 6 Months: 1st of the month five months back
- A preset is highlighted when the active range equals its range
- The recent transactions list keeps `LIMIT 10`, so for a range with more than
  10 expenses it shows fewer rows than the stats count

## Definition of done
- [ ] Visiting `/profile` with no query params returns the same data as Step 5
  (unfiltered, all expenses) and "All Time" is highlighted
- [ ] Clicking "This Month" filters all three sections to the current calendar
  month only
- [ ] Clicking "Last 3 Months" filters to the current month and the two before it
- [ ] Clicking "Last 6 Months" filters to the current month and the five before it
- [ ] Clicking "All Time" removes any active filter and shows all expenses
- [ ] Submitting a custom date range with valid `date_from` and `date_to` shows
  only expenses within that range (inclusive) in all three sections
- [ ] Submitting only `date_from` or only `date_to` filters with an open end
- [ ] Submitting a range where `date_from > date_to` shows the error message and
  falls back to the unfiltered view
- [ ] Submitting a malformed date string (e.g. `date_from=not-a-date`) does not
  crash the app — it is ignored
- [ ] The active preset or custom-range fields visually indicate which
  filter is currently applied
- [ ] All amounts continue to display the ₹ symbol regardless of the active filter
- [ ] A user with no expenses in the selected range sees ₹0.00 total spent, 0
  transactions, and an empty category breakdown — no errors
- [ ] A user never sees another user's expenses, with or without a filter
- [ ] `pytest` passes, including the existing suites
