# Spec: Delete Expense

## Overview
Step 9 turns the `/expenses/<id>/delete` stub into a working feature. A logged-in
user can remove one of their own expenses from the `/profile` page. Deleting is
destructive and state-changing, so it is done with a `POST` from a small form
next to each transaction (guarded by a browser confirmation), never a plain
link. After deletion the user is redirected to `/profile`, where the
transaction list, total spent, transaction count and category breakdown no
longer include the removed expense. Steps 7 and 8 let users add and correct
expenses; this step completes the expense CRUD cycle.

## Depends on
- Step 1: Database setup (`expenses` table and `get_db()`)
- Step 3: Login and logout (`session["user_id"]`)
- Step 4/5: Profile page and its queries (entry point and redirect target)
- Step 7: Add expense
- Step 8: Edit expense (`get_expense`, per-row actions on `profile.html`,
  `_current_user_row()`)

## Routes
- `POST /expenses/<int:id>/delete` — delete the expense, redirect to `/profile`
  — logged-in
- `GET /expenses/<int:id>/delete` — no longer served; the route accepts `POST`
  only, so a GET returns 405 (deleting must never happen from a link, prefetch
  or crawler) — logged-in/public alike (405 regardless of session)

Behaviour:
- No `session["user_id"]` (or a stale one) → redirect to `/login` via
  `_current_user_row()`, and nothing is deleted.
- An expense that does not exist, or that belongs to another user → `abort(404)`
  (same response for both, so other users' ids are not revealed); nothing is
  deleted.
- Success → redirect to `url_for("profile")`.
- The existing view function name `delete_expense` is kept so `url_for` keeps
  working.
- Date filters on `/profile` are not preserved across the redirect (same as
  add/edit); the user lands on the default profile view.

## Database changes
No schema changes.

New helper in `database/db.py` (parameterised query, `get_db()`, close in
`finally`, like existing helpers):
- `delete_expense(user_id, expense_id)` — `DELETE FROM expenses WHERE id = ? AND
  user_id = ?`, commits, returns `True` if a row was deleted and `False`
  otherwise. Ownership is enforced in SQL as well as in the route.

(Name the DB helper `delete_expense` in `db.py`; in `app.py` import it under an
alias such as `delete_expense as delete_expense_row` to avoid clashing with the
route function of the same name.)

## Templates
- **Create:** none
- **Modify:** `templates/profile.html` — next to each row's Edit link add a
  `<form method="post" action="{{ url_for('delete_expense', id=t.id) }}">`
  with a "Delete" `<button type="submit">` that has an accessible label
  (e.g. `aria-label="Delete expense: <description or category>"`) and a
  `data-confirm` attribute carrying the confirmation message.
- **Modify:** `static/js/main.js` — vanilla JS only: on submit of any form with
  `data-confirm`, call `window.confirm()` with that message and
  `preventDefault()` if the user cancels. The form must still work (submit
  without confirmation) if JS is disabled.

## Files to change
- `app.py` — implement `delete_expense` (POST only); import the new DB helper
- `database/db.py` — add `delete_expense`
- `templates/profile.html` — per-row Delete form
- `static/css/profile.css` — style the Delete button as a destructive but
  low-key action, consistent with the Edit link (CSS variables only)
- `static/js/main.js` — confirm-before-submit handler
- Existing tests — update any test that asserts the old stub response
  (`"Delete expense — coming in Step 9"`, e.g. `test_expense_stubs_unchanged`)
  so it matches the new behaviour

## Files to create
- `tests/test_delete_expense.py`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never f-strings in SQL
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- DB logic lives in `database/db.py` only; the route authenticates, calls the
  helper, redirects
- Deletion is `POST` only — never delete on `GET`
- Ownership is enforced in SQL (`AND user_id = ?`) as well as in the route
- Use `abort(404)` for missing/foreign expenses, not a returned string
- Use `url_for()` for every link and form action; port stays 5001
- Vanilla JS only — no libraries
- Do not implement or modify any other stub route (`/logout`, `/profile` are
  already done; do not touch unrelated routes)
- Currency is ₹/INR everywhere in UI and test data
- `get_db()` must keep `PRAGMA foreign_keys = ON`

## Definition of done
- [ ] Each row on `/profile` has a Delete button (inside a POST form) beside the
  Edit link, with an accessible label
- [ ] Clicking Delete shows a confirmation dialog; cancelling leaves the expense
  in place
- [ ] Confirming deletes the expense and redirects to `/profile`
- [ ] After deletion the row is gone, total spent drops by that amount,
  transaction count drops by 1, and the category breakdown updates (a category
  with no remaining expenses disappears)
- [ ] Only the targeted expense is removed; all other expenses are unchanged
- [ ] Deleting the user's last expense shows the profile's empty state without
  errors
- [ ] `GET /expenses/<id>/delete` returns 405 and deletes nothing
- [ ] Logged out, `POST /expenses/1/delete` redirects to `/login` and deletes
  nothing
- [ ] `POST /expenses/9999/delete` returns 404
- [ ] Logged in as user B, `POST /expenses/<A's id>/delete` returns 404 and A's
  expense still exists
- [ ] Posting the delete twice for the same id: first redirects, second returns
  404
- [ ] `/expenses/add` and `/expenses/<id>/edit` still work unchanged
- [ ] With JS disabled the Delete form still submits
- [ ] No hardcoded hex colours or hardcoded URLs were added
- [ ] `pytest` passes, including the new `tests/test_delete_expense.py`
