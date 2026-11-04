# Spec: Edit Expense

## Overview
Step 8 turns the `/expenses/<id>/edit` stub into a working feature. A logged-in
user opens an edit form pre-filled with one of their existing expenses (amount in
₹, category, date, description), changes any field and saves. On success they are
redirected to `/profile`, where the updated expense, summary stats and category
breakdown reflect the change. Step 7 let users create expenses; this step lets
them correct mistakes. It reuses the Step 7 validation and form styling so the
add and edit pages behave identically.

## Depends on
- Step 1: Database setup (`expenses` table and `get_db()`)
- Step 3: Login and logout (`session["user_id"]`)
- Step 4/5: Profile page and its queries (entry point and redirect target)
- Step 7: Add expense (`_validate_expense_form`, `add_expense.html`,
  `add_expense.css`, `CATEGORIES`)

## Routes
- `GET /expenses/<int:id>/edit` — render the form pre-filled with the expense's
  current values — logged-in
- `POST /expenses/<int:id>/edit` — validate the form, update the expense,
  redirect to `/profile` on success or re-render with errors on failure —
  logged-in

Behaviour:
- No `session["user_id"]` (or a stale one) → redirect to `/login`, via
  `_current_user_row()` like the other routes.
- An expense that does not exist, or that belongs to another user → `abort(404)`
  (the same response for both, so ids of other users' expenses are not revealed).
- `/expenses/<id>/delete` stays a stub (Step 9) and must not be touched.

## Database changes
No schema changes.

New helpers in `database/db.py` (parameterised queries, `get_db()`, close in
`finally`, like existing helpers):
- `get_expense(user_id, expense_id)` — returns the row as a dict
  (`id, amount, category, date, description`) only if it belongs to `user_id`,
  else `None`.
- `update_expense(user_id, expense_id, amount, category, expense_date, description)`
  — `UPDATE ... WHERE id = ? AND user_id = ?`, commits, returns `True` if a row
  was changed and `False` otherwise.
- Modify `get_recent_expenses()` to also `SELECT id` so the profile page can link
  to each expense's edit page. Existing callers/tests must keep working.

## Templates
- **Create:** none — reuse `templates/add_expense.html` for both add and edit.
- **Modify:** `templates/add_expense.html` — accept an `expense_id` (or
  `is_edit`) variable: heading becomes "Edit expense", submit button "Save
  changes", and the form `action` is `url_for('edit_expense', id=expense_id)`
  when editing, otherwise `url_for('add_expense')`. Cancel still links to
  `url_for('profile')`.
- **Modify:** `templates/profile.html` — add an "Edit" link per transaction row
  using `url_for('edit_expense', id=t.id)`, with an accessible label.

## Files to change
- `app.py` — implement `edit_expense`; import `get_expense`, `update_expense`,
  `abort`; keep `delete_expense` stub as-is
- `database/db.py` — add `get_expense`, `update_expense`; add `id` to
  `get_recent_expenses`
- `templates/add_expense.html` — add/edit mode
- `templates/profile.html` — per-row Edit link
- `static/css/profile.css` — style the Edit link (CSS variables only)
- `tests/test_add_expense.py` / other existing tests — update
  `test_expense_stubs_unchanged` so only the delete stub remains asserted

## Files to create
- `tests/test_edit_expense.py`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never f-strings in SQL
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- DB logic lives in `database/db.py` only; the route fetches, validates, renders
- Reuse `_validate_expense_form`; do not duplicate validation rules
- Ownership is enforced in SQL (`AND user_id = ?`) as well as in the route
- Use `abort(404)` for missing/foreign expenses, not a returned string
- Use `url_for()` for every link; port stays 5001
- Do not implement the delete route (Step 9)
- Currency is ₹/INR everywhere in UI and test data

## Definition of done
- [ ] Logged out, `GET` and `POST` `/expenses/1/edit` redirect to `/login`
- [ ] Each row on `/profile` has an Edit link that opens that expense's edit page
- [ ] The edit form is pre-filled with the expense's amount, category, date and
  description, and the heading says "Edit expense"
- [ ] Changing fields and saving redirects to `/profile`, which shows the new
  values, updated total and category breakdown
- [ ] Editing does not create a new row (transaction count unchanged)
- [ ] Clearing the description saves successfully and shows blank, not "None"
- [ ] Invalid amount (`0`, negative, `abc`, `nan`, `inf`, empty) re-shows the form
  with the error and leaves the stored expense unchanged
- [ ] Invalid/missing category, malformed or future date, date before
  `2000-01-01`, and a 201-character description are each rejected with the
  matching error and change nothing
- [ ] After a failed submit, what the user typed is still in the form
- [ ] `12.345` is saved as `12.35`
- [ ] `/expenses/9999/edit` returns 404
- [ ] Logged in as user B, `/expenses/<A's id>/edit` returns 404 on GET and POST,
  and A's expense is unchanged
- [ ] "Cancel" returns to `/profile` without saving
- [ ] `/expenses/add` still works and still shows "Add expense" wording
- [ ] `/expenses/1/delete` still returns its stub response
- [ ] A SQL-looking description is stored literally and the table is unaffected
- [ ] `pytest` passes, including the new `tests/test_edit_expense.py`
