# Spec: Add Expense

## Overview
Step 7 turns the `/expenses/add` stub into a working feature. A logged-in user
opens a form, enters an amount (in ₹), category, date and optional description,
and submits it to save a new row in the `expenses` table. On success they are
redirected to `/profile`, where the new expense appears in the transaction
history, summary stats and category breakdown. Until now the only expenses in
the app come from `seed_db()`, so this is the first step that lets a user create
their own data.

## Depends on
- Step 1: Database setup (`expenses` table and `get_db()` must exist)
- Step 3: Login and logout (`session["user_id"]` identifies the current user)
- Step 4/5: Profile page and its backend queries (the redirect target, and where
  the new expense is displayed)

## Routes
- `GET /expenses/add` — render the empty add-expense form (date pre-filled with
  today) — logged-in
- `POST /expenses/add` — validate the form, insert the expense for the current
  user, redirect to `/profile` on success or re-render the form with errors on
  failure — logged-in

Both methods redirect to `/login` when there is no `session["user_id"]` (same
pattern as `/profile` and `/analytics`). A `session["user_id"]` that no longer
matches a user is handled like `/profile`: clear the session and redirect to
`/login`.

The stub routes `/expenses/<id>/edit` and `/expenses/<id>/delete` are NOT touched
(Steps 8 and 9).

## Database changes
No schema changes. The existing `expenses` table already has every column needed
(`user_id`, `amount REAL`, `category`, `date TEXT`, `description`).

New helper in `database/db.py`:
- `create_expense(user_id, amount, category, date, description)` — inserts one
  row with a parameterised `INSERT`, commits, and returns the new row id.
  Uses `get_db()` and closes the connection in a `finally` block, like the
  existing helpers.

`CATEGORIES` already exists in `database/db.py` and is the single source of truth
for the allowed categories; the route imports it rather than redefining it.

## Templates
- **Create:** `templates/add_expense.html` — extends `base.html`; a card with a
  `method="post"` form containing:
  - Amount (`<input type="number" step="0.01" min="0.01">`, labelled with ₹)
  - Category (`<select>` populated from the `categories` template variable)
  - Date (`<input type="date">`, default today, `max` set to today)
  - Description (optional text input, `maxlength="200"`)
  - "Save expense" submit button and a "Cancel" link back to `url_for('profile')`
  - A form-level error block (`role="alert"`) and per-field error messages
  - On a failed submit, every field is re-populated with the user's input
- **Modify:** `templates/profile.html` — add an "Add expense" button/link
  (`url_for('add_expense')`) near the Transaction history panel title so the page
  is reachable from the UI.
- **Modify:** `templates/base.html` — add an "Add expense" link to the logged-in
  nav links, using `url_for('add_expense')`, with the same `active` /
  `aria-current` handling the Analytics link uses.

## Files to change
- `app.py` — replace the `add_expense` stub with the real view
  (`methods=["GET", "POST"]`) plus private helpers: `_validate_expense_form(form,
  today)` returning `(cleaned, errors, values)` (`values` re-populates the form;
  `cleaned` is keyed by `create_expense`'s parameter names), `_parse_amount(raw)`,
  `_blank_expense_values(today)` and `_current_user_row()` (shared login guard,
  also used by `/profile`); set `MAX_CONTENT_LENGTH`; import `CATEGORIES` and
  `create_expense`
- `database/db.py` — add `create_expense()`
- `templates/profile.html` — add the "Add expense" link
- `templates/base.html` — add the nav link
- `tests/test_profile_route.py` — `test_expense_stubs_unchanged` currently asserts
  `b"Step 7"` in the `/expenses/add` response; remove that assertion (keep the
  Step 8 and Step 9 ones) since the route is no longer a stub
- `CLAUDE.md` — mark `GET /expenses/add` as implemented in the routes table

## Files to create
- `templates/add_expense.html`
- `static/css/add_expense.css` — page-specific styles (not inline `<style>`),
  loaded through the `head` block of `add_expense.html`
- `tests/test_add_expense.py`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — never f-strings in SQL
- Passwords hashed with werkzeug (no changes to auth in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles and no inline `<style>` tags
- DB logic stays in `database/db.py`; the route only validates, calls
  `create_expense()`, and redirects or renders
- Use `url_for()` for every link and for the form `action` — no hardcoded URLs
- The expense is always saved for `session["user_id"]`; never accept a `user_id`
  from the form
- Validation (server-side, regardless of the HTML attributes):
  - **amount** — required; must parse as a finite number (reject `nan`/`inf`),
    be greater than 0, and be at most 10,000,000; round to 2 decimal places
    before saving. Error: "Enter a valid amount greater than 0."
  - **category** — required; must be one of `CATEGORIES`. Error: "Choose a
    category."
  - **date** — required; must match `YYYY-MM-DD` (reuse `_parse_iso_date`, which
    also accepts and normalises unpadded input like `2026-1-5`), must not be in
    the future, and must not be before `2000-01-01`. The date input also carries
    `min="2000-01-01"` and `max=<today>`. Error: "Enter a valid date that is not
    in the future."
  - **description** — optional; stripped; at most 200 characters. Error:
    "Description must be 200 characters or fewer."
- Request bodies larger than 16 KiB are rejected with HTTP 413
  (`app.config["MAX_CONTENT_LENGTH"]`, app-wide)
- The form-level error banner reuses the shared `.auth-error` class
- A blank description is stored as an empty string `""`, not `NULL`, because
  `profile.html` renders `{{ t.description }}` directly and would show "None"
- On any validation error: return HTTP 200 (re-rendered form), do not insert
  anything, and keep the user's input in the form
- On success: redirect (POST/redirect/GET) to `url_for("profile")`; do not render
  the profile directly from the POST
- Amounts are displayed with the existing `inr` filter and the form labels use ₹ —
  never `$` or USD
- There is no CSRF protection in the app and none is added here (it would need a
  new package); do not introduce a half-measure
- Do not implement Step 8 (edit) or Step 9 (delete)

## Definition of done
- [ ] Visiting `/expenses/add` while logged out redirects to `/login`; posting to
  it while logged out redirects to `/login` and inserts nothing
- [ ] Logged in, `/expenses/add` shows the form with the date pre-filled with
  today, a category dropdown listing all seven categories, and a ₹ amount label
- [ ] Submitting valid data redirects to `/profile`, and the new expense appears in
  Transaction history (at the top when dated today, since history is ordered by
  date then id and shows 10 rows) with the right date, description, category and
  ₹ amount
- [ ] After adding an expense, the Total spent, Transactions count and Category
  breakdown on `/profile` reflect it
- [ ] The saved row belongs to the logged-in user, and another user's profile does
  not show it
- [ ] Submitting with the description left blank saves successfully and the
  profile shows an empty description, not the text "None"
- [ ] Amount of `0`, a negative number, `abc`, `nan`, `inf` or an empty value
  re-shows the form with the amount error and saves nothing
- [ ] An amount like `12.345` is saved as `12.35` (rounded to 2 decimals)
- [ ] A category not in the list (e.g. a hand-edited `Travel`) or none at all is
  rejected with the category error and saves nothing
- [ ] A malformed date, an empty date, or a future date is rejected with the date
  error and saves nothing
- [ ] A date before `2000-01-01` is rejected; `2000-01-01` itself is accepted
- [ ] A POST body larger than 16 KiB returns 413 and saves nothing
- [ ] A description of 201 characters is rejected; one of 200 is accepted
- [ ] After a failed submit, the amount, category, date and description the user
  typed are still in the form
- [ ] "Cancel" returns to `/profile` without saving
- [ ] The profile page and the nav bar both have an "Add expense" link that opens
  the form
- [ ] A SQL-looking description such as `'); DROP TABLE expenses;--` is saved
  literally and the table is unaffected
- [ ] `/expenses/1/edit` and `/expenses/1/delete` still return their stub
  responses
- [ ] `pytest` passes, including the updated `test_expense_stubs_unchanged` and the
  new `tests/test_add_expense.py`
