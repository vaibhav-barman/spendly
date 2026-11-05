import calendar
import os
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from flask import Flask, abort, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from database.db import (
    CATEGORIES,
    create_expense,
    delete_expense as delete_expense_row,
    get_category_breakdown,
    get_db,
    get_expense,
    get_expense_summary,
    get_recent_expenses,
    get_user_by_id,
    init_db,
    seed_db,
    update_expense,
)

app = Flask(__name__)
# The fallback is for local development only; set SECRET_KEY in any real deployment.
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")
# Reject oversized request bodies (HTTP 413) before a form is parsed. Every form
# in the app is a handful of short fields, so 16 KiB is generous.
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024

# Add-expense limits. Dates are compared as ISO strings, which sort correctly.
MAX_AMOUNT = Decimal("10000000")
MAX_DESCRIPTION_LENGTH = 200
MIN_EXPENSE_DATE = "2000-01-01"

with app.app_context():
    init_db()
    seed_db()


@app.template_filter("inr")
def inr_filter(value):
    """Format a number as rupees with Indian digit grouping, e.g. ₹1,23,456.00."""
    amount = float(value or 0)
    sign = "-" if amount < 0 else ""
    whole, frac = f"{abs(amount):.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    return f"{sign}₹{whole}.{frac}"


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register")
def register():
    if session.get("user_id"):
        return redirect(url_for("profile"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    conn = get_db()
    try:
        user = conn.execute(
            "SELECT id, password_hash FROM users WHERE email = ?", (email,)
        ).fetchone()
    finally:
        conn.close()

    if user is None or not check_password_hash(user["password_hash"], password):
        return render_template(
            "login.html", error="Invalid email or password", email=email
        )

    session.clear()
    session["user_id"] = user["id"]
    return redirect(url_for("profile"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

def _parse_iso_date(value):
    """Return value as a normalised YYYY-MM-DD string, or None if missing/invalid."""
    try:
        return datetime.strptime(value or "", "%Y-%m-%d").date().isoformat()
    except ValueError:
        return None


def _parse_date_range(args):
    """Read date_from / date_to from the query string.

    Each bound is validated on its own; a missing or malformed one is an open
    bound. Returns (date_from, date_to, error). An inverted range clears both
    bounds and reports an error.
    """
    date_from = _parse_iso_date(args.get("date_from"))
    date_to = _parse_iso_date(args.get("date_to"))
    if date_from and date_to and date_from > date_to:
        return None, None, "Start date must be before end date."
    return date_from, date_to, None


def _build_presets(today):
    """Quick-pick ranges, aligned to calendar months and ending on the last day
    of the current month. All Time has no bounds (a clean /profile URL)."""
    def month_start(months_back):
        year, month = divmod(today.year * 12 + today.month - 1 - months_back, 12)
        return date(year, month + 1, 1).isoformat()

    month_end = date(
        today.year, today.month, calendar.monthrange(today.year, today.month)[1]
    ).isoformat()

    presets = [
        {"key": key, "label": label, "date_from": month_start(back), "date_to": month_end}
        for key, label, back in (
            ("month", "This Month", 0),
            ("3m", "Last 3 Months", 2),
            ("6m", "Last 6 Months", 5),
        )
    ]
    presets.append({"key": "all", "label": "All Time", "date_from": None, "date_to": None})
    return presets


def _build_profile_user(row):
    parts = row["name"].split()
    initials = "".join(p[0] for p in parts[:2]).upper() or "?"
    try:
        member_since = datetime.strptime(
            row["created_at"], "%Y-%m-%d %H:%M:%S"
        ).strftime("%B %Y")
    except (TypeError, ValueError):
        member_since = "—"
    return {
        "initials": initials,
        "name": row["name"],
        "email": row["email"],
        "member_since": member_since,
    }


def _current_user_row():
    """Return the logged-in user's row, or None.

    None means "send them to /login": either nobody is logged in, or the
    session points at a user that no longer exists (the session is cleared).
    """
    user_id = session.get("user_id")
    if not user_id:
        return None
    user_row = get_user_by_id(user_id)
    if user_row is None:
        session.clear()
    return user_row


@app.route("/profile")
def profile():
    user_row = _current_user_row()
    if user_row is None:
        return redirect(url_for("login"))
    user_id = user_row["id"]

    date_from, date_to, filter_error = _parse_date_range(request.args)
    presets = _build_presets(date.today())
    active_key = next(
        (
            p["key"]
            for p in presets
            if (p["date_from"], p["date_to"]) == (date_from, date_to)
        ),
        None,
    )

    return render_template(
        "profile.html",
        user=_build_profile_user(user_row),
        stats=get_expense_summary(user_id, date_from=date_from, date_to=date_to),
        transactions=get_recent_expenses(user_id, date_from=date_from, date_to=date_to),
        categories=get_category_breakdown(user_id, date_from=date_from, date_to=date_to),
        date_from=date_from,
        date_to=date_to,
        is_filtered=bool(date_from or date_to),
        presets=presets,
        active_key=active_key,
        filter_error=filter_error,
    )


@app.route("/analytics")
def analytics():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return render_template("analytics.html")


def _parse_amount(raw):
    """Return raw as a float rounded half-up to 2 places, or None if invalid.

    Decimal (not float) so 12.345 becomes 12.35 deterministically. inf, sNaN and
    absurd exponents raise InvalidOperation in quantize(); a quiet NaN comes
    back as NaN and fails is_finite(), which must be checked before comparing.
    """
    try:
        amount = Decimal(raw).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None
    if amount.is_finite() and 0 < amount <= MAX_AMOUNT:
        return float(amount)
    return None


def _blank_expense_values(today):
    """Form values for a fresh add-expense page (date defaults to today)."""
    return {
        "amount": "",
        "category": "",
        "date": today.isoformat(),
        "description": "",
    }


def _validate_expense_form(form, today):
    """Validate the add-expense form.

    Returns (cleaned, errors, values). `values` holds the stripped raw input so
    a failed submit can re-populate the form. `cleaned` is keyed by the
    parameter names of `create_expense` and is only meaningful when `errors` is
    empty; `errors` maps a field name to its message.
    """
    values = {
        "amount": (form.get("amount") or "").strip(),
        "category": form.get("category") or "",
        "date": (form.get("date") or "").strip(),
        "description": (form.get("description") or "").strip(),
    }
    cleaned = {}
    errors = {}

    amount = _parse_amount(values["amount"])
    if amount is None:
        errors["amount"] = "Enter a valid amount greater than 0."
    else:
        cleaned["amount"] = amount

    if values["category"] in CATEGORIES:
        cleaned["category"] = values["category"]
    else:
        errors["category"] = "Choose a category."

    expense_date = _parse_iso_date(values["date"])
    if expense_date is None or not (
        MIN_EXPENSE_DATE <= expense_date <= today.isoformat()
    ):
        errors["date"] = "Enter a valid date that is not in the future."
    else:
        cleaned["expense_date"] = expense_date

    if len(values["description"]) > MAX_DESCRIPTION_LENGTH:
        errors["description"] = (
            f"Description must be {MAX_DESCRIPTION_LENGTH} characters or fewer."
        )
    else:
        cleaned["description"] = values["description"]

    return cleaned, errors, values


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    user_row = _current_user_row()
    if user_row is None:
        return redirect(url_for("login"))

    today = date.today()
    errors = {}
    values = _blank_expense_values(today)
    if request.method == "POST":
        cleaned, errors, values = _validate_expense_form(request.form, today)
        if not errors:
            create_expense(user_row["id"], **cleaned)
            return redirect(url_for("profile"))

    return render_template(
        "add_expense.html",
        categories=CATEGORIES,
        values=values,
        errors=errors,
        today=today.isoformat(),
        min_date=MIN_EXPENSE_DATE,
        max_description_length=MAX_DESCRIPTION_LENGTH,
    )


@app.route("/expenses/<int:id>/edit", methods=["GET", "POST"])
def edit_expense(id):
    user_row = _current_user_row()
    if user_row is None:
        return redirect(url_for("login"))

    expense = get_expense(user_row["id"], id)
    if expense is None:
        abort(404)

    today = date.today()
    errors = {}
    values = {
        "amount": f"{expense['amount']:.2f}",
        "category": expense["category"],
        "date": expense["date"],
        "description": expense["description"] or "",
    }
    if request.method == "POST":
        cleaned, errors, values = _validate_expense_form(request.form, today)
        if not errors:
            if not update_expense(user_row["id"], id, **cleaned):
                abort(404)
            return redirect(url_for("profile"))

    return render_template(
        "add_expense.html",
        categories=CATEGORIES,
        values=values,
        errors=errors,
        today=today.isoformat(),
        min_date=MIN_EXPENSE_DATE,
        max_description_length=MAX_DESCRIPTION_LENGTH,
        expense_id=id,
    )


@app.route("/expenses/<int:id>/delete", methods=["POST"])
def delete_expense(id):
    user_row = _current_user_row()
    if user_row is None:
        return redirect(url_for("login"))
    if not delete_expense_row(user_row["id"], id):
        abort(404)
    return redirect(url_for("profile"))


if __name__ == "__main__":
    app.run(debug=True, port=5001)
