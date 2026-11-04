from app import inr_filter


def test_logged_out_redirects_to_login(client):
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_demo_profile_shows_real_data(client, login, demo_user_id):
    login(demo_user_id)
    resp = client.get("/profile")
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "Demo User" in html
    assert "demo@spendly.com" in html
    assert "₹6,398.00" in html
    assert "Shopping" in html
    assert html.index("Dinner out") < html.index("Weekly groceries")
    assert "$" not in html
    assert "style=" not in html


def test_stale_session_clears_and_redirects(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 99999
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_empty_user_sees_empty_state(client, login, empty_user_id):
    login(empty_user_id)
    resp = client.get("/profile")
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "₹0.00" in html
    assert "—" in html
    assert "No transactions yet." in html
    assert "Dinner out" not in html


def test_expense_stubs_unchanged(client):
    assert b"Step 7" in client.get("/expenses/add").data
    assert b"Step 8" in client.get("/expenses/1/edit").data
    assert b"Step 9" in client.get("/expenses/1/delete").data


def test_inr_filter_indian_grouping():
    assert inr_filter(6398) == "₹6,398.00"
    assert inr_filter(123456) == "₹1,23,456.00"
    assert inr_filter(12345678.5) == "₹1,23,45,678.50"
    assert inr_filter(0) == "₹0.00"
