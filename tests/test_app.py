"""End-to-end checks for LeadBoard. Run with:  python -m pytest -q"""

import os
import re
import sqlite3

import pytest
from fastapi.testclient import TestClient

import demo_data as dd

DEMO = "DEMO DATA — SIMULATED RESULTS"
SNAP = "DAY 4 — SIMULATED SNAPSHOT"
PAGES = ["/lead-kit", "/leaderboard", "/register", "/admin"]


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LEADBOARD_DB", str(tmp_path / "test.sqlite"))
    import server

    with TestClient(server.app) as c:
        c.server = server
        yield c


def form(**over):
    data = {
        "name": "Test Person", "college": "Riverbend Institute of Technology",
        "branch": "CSE", "year": "Final year", "mobile": "9876501234", "referral": "",
    }
    data.update(over)
    return data


# 1-4. Every page works and carries the disclosure ---------------------------
@pytest.mark.parametrize("path", PAGES)
def test_pages_load_with_disclosure(client, path):
    r = client.get(path)
    assert r.status_code == 200
    assert DEMO in r.text


def test_home_redirects_to_lead_kit(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 307 and r.headers["location"] == "/lead-kit"


def test_navigation_on_every_page(client):
    for path in PAGES:
        html = client.get(path).text
        for label in ("Lead Kit", "Leaderboard", "Register", "Admin Dashboard"):
            assert f">{label}</a>" in html


def test_snapshot_label_on_leaderboard_and_admin(client):
    assert SNAP in client.get("/admin").text
    assert SNAP in client.get("/leaderboard").text


# Lead Kit contents -----------------------------------------------------------
def test_lead_kit_contents(client):
    html = client.get("/lead-kit").text
    for needle in (
        "Registrations generated", "goal", "Groups posted", "Current rank",
        "Lead code", "Copy referral link", "Copy WhatsApp message", "Open WhatsApp",
        "https://wa.me/?text=",
    ):
        assert needle in html, needle
    assert "Build Your First AI Project in 60 Minutes" in html
    assert "a free hands-on AI workshop. No prior AI experience required. Register here: http" in html


def test_every_lead_kit_renders(client):
    for code, name, *_ in dd.LEADS:
        html = client.get(f"/lead-kit?lead={code}").text
        assert name in html and code in html and f"/r/{code}" in html


def test_whatsapp_link_carries_personal_link(client):
    html = client.get("/lead-kit?lead=LDMEKR07").text
    assert "%2Fr%2FLDMEKR07" in html


# 5. Referral links ------------------------------------------------------------
def test_referral_link_redirects_and_credits(client):
    r = client.get("/r/ldmekr07", follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == "/register?ref=LDMEKR07"
    page = client.get(r.headers["location"]).text
    assert "Meera Krishnan" in page


def test_lead_referral_attribution(client):
    before = client.get("/api/stats").json()
    r = client.post("/register", data=form(referral="LDMEKR07"), follow_redirects=False)
    assert r.status_code == 303
    row = sqlite3.connect(os.environ["LEADBOARD_DB"]).execute(
        "SELECT source, lead_code, is_demo FROM students WHERE mobile='9876501234'"
    ).fetchone()
    assert row == ("campus_lead", "LDMEKR07", 0)
    after = client.get("/api/stats").json()
    assert after["live_signups"] == 1
    assert after["total_simulated"] == before["total_simulated"]  # live != simulated
    assert "1 live test sign-up" in client.get("/lead-kit?lead=LDMEKR07").text


def test_student_referral_attribution(client):
    client.post("/register", data=form(referral="ANRA21"))
    row = sqlite3.connect(os.environ["LEADBOARD_DB"]).execute(
        "SELECT source, referred_by FROM students WHERE mobile='9876501234'"
    ).fetchone()
    assert row == ("student_referral", "ANRA21")


def test_unknown_code_credits_nobody(client):
    r = client.post("/register", data=form(referral="NOSUCH1"), follow_redirects=True)
    assert "not recognised" in r.text
    row = sqlite3.connect(os.environ["LEADBOARD_DB"]).execute(
        "SELECT lead_code, referred_by FROM students WHERE mobile='9876501234'"
    ).fetchone()
    assert row == (None, None)


# 6. Registration flow ----------------------------------------------------------
def test_success_page(client):
    r = client.post("/register", data=form(), follow_redirects=True)
    assert r.status_code == 200
    html = r.text
    assert "You're registered" in html
    assert "Share with 2 friends" in html
    assert "Share on WhatsApp" in html and "https://wa.me/?text=" in html
    assert re.search(r"/r/[A-Z0-9]{5}", html)


def test_final_year_validation(client):
    r = client.post("/register", data=form(year="3rd year"))
    assert r.status_code == 400 and "final-year" in r.text


@pytest.mark.parametrize("mobile", ["12345", "5876543210", "98765abcde", ""])
def test_mobile_validation(client, mobile):
    r = client.post("/register", data=form(mobile=mobile))
    assert r.status_code == 400 and "10-digit Indian mobile" in r.text


def test_mobile_accepts_country_code(client):
    r = client.post("/register", data=form(mobile="+91 98765 01234"), follow_redirects=False)
    assert r.status_code == 303


def test_duplicate_prevention(client):
    assert client.post("/register", data=form(), follow_redirects=False).status_code == 303
    r = client.post("/register", data=form(name="Someone Else"))
    assert r.status_code == 400 and "already registered" in r.text


def test_demo_numbers_are_taken(client):
    r = client.post("/register", data=form(mobile="9000000001"))
    assert r.status_code == 400


def test_branch_and_required_fields(client):
    assert client.post("/register", data=form(branch="")).status_code == 400
    assert client.post("/register", data=form(name="")).status_code == 400
    assert client.post("/register", data=form(college="")).status_code == 400


def test_source_param_for_untracked_signups(client):
    client.post("/register", data=form(src="reel"))
    client.post("/register", data=form(mobile="9876509999", src="placement"))
    rows = sqlite3.connect(os.environ["LEADBOARD_DB"]).execute(
        "SELECT source FROM students WHERE is_demo = 0 ORDER BY id"
    ).fetchall()
    assert rows == [("demo_reel",), ("college_placement",)]


# 7-9. Simulation numbers and consistency --------------------------------------
def test_planning_targets():
    assert dd.TARGETS == {
        "campus_lead": 300, "college_placement": 100, "student_referral": 70, "demo_reel": 30,
    }
    assert sum(dd.TARGETS.values()) == dd.GOAL == 500


def test_day4_snapshot(client):
    s = client.get("/api/stats").json()
    assert s["simulated"] is True and s["goal"] == 500
    assert 285 <= s["total_simulated"] <= 300
    assert s["total_simulated"] == sum(v["count"] for v in s["sources"].values())
    for key, v in s["sources"].items():
        assert 0 < v["count"] < v["target"], key  # never reaches the 7-day target


def test_ten_leads_and_lead_totals(client):
    s = client.get("/api/stats").json()
    assert s["total_leads"] == 10
    assert sum(l[3] for l in dd.LEADS) == s["sources"]["campus_lead"]["count"]
    assert all(l[3] < dd.LEAD_GOAL for l in dd.LEADS)


def test_daily_trend_adds_up(client):
    assert [sum(col) for col in zip(*dd.DAY_MATRIX.values())] == [39, 63, 84, 106]
    html = client.get("/admin").text
    for n in (39, 63, 84, 106):
        assert f">{n}</span>" in html


def test_ab_test_content(client):
    html = client.get("/admin").text
    assert "Build Your First AI Project in 60 Minutes" in html
    assert "Ship a Live AI Project in 60 Minutes — No AI Experience Required" in html
    assert "Conversion" in html and "Views" in html and "Registrations" in html
    assert sum(v[3] for v in dd.AB_VARIANTS) == 292


def test_admin_sections(client):
    html = client.get("/admin").text
    for needle in (
        "Total registrations", "Progress toward 500", "Active campus leads", "Top referrer",
        "Registrations by source", "Campus Lead", "College / Placement", "Student Referral",
        "Demo Reel", "Leads needing follow-up", "A/B variant performance",
        "Daily registration trend", "Live test sign-ups",
    ):
        assert needle in html, needle


def test_leaderboard_sections(client):
    html = client.get("/leaderboard").text
    for needle in (
        "Top campus leads", "College leaderboard", "Student referral leaderboard",
        "of 500", 'role="progressbar"',
    ):
        assert needle in html, needle


def test_rankings_are_ordered(client):
    html = client.get("/leaderboard").text
    first = html.index("Meera Krishnan")
    assert first < html.index("Rohan Desai") < html.index("Kavya Reddy")


def test_follow_up_leads(client):
    html = client.get("/admin").text
    for name in ("Arvind Pillai", "Nisha Thomas", "Dev Malhotra"):
        assert name in html
    assert "Send WhatsApp nudge" in html


# 11-12. No placeholders, no "real" claims --------------------------------------
BANNED = ["example.com", "your-link", "yourdomain", "lorem", "[personal referral link]",
          "TODO", "placeholder.", "href=\"#\"", "javascript:void"]


def test_no_placeholder_text_or_urls(client):
    client.post("/register", data=form())
    for path in PAGES + ["/leaderboard"]:
        html = client.get(path).text.lower()
        for bad in BANNED:
            assert bad.lower() not in html, (path, bad)
    for fname in ("templates", "static"):
        for root, _d, files in os.walk(os.path.join(os.path.dirname(dd.__file__), fname)):
            for f in files:
                text = open(os.path.join(root, f), encoding="utf-8").read().lower()
                for bad in ("example.com", "your-link", "lorem"):
                    assert bad not in text, (f, bad)


def test_no_real_registration_claims(client):
    risky = re.compile(r"\b(real registrations|actual registrations|verified registrations)\b", re.I)
    for path in PAGES + ["/leaderboard"]:
        for m in risky.finditer(client.get(path).text):
            ctx = client.get(path).text[max(0, m.start() - 30): m.start()].lower()
            assert "not " in ctx or "no" in ctx, (path, m.group(0))


def test_demo_data_is_fictional():
    rows = dd.build_demo_students()
    assert len(rows) == 292
    assert len({r["mobile"] for r in rows}) == 292
    assert all(r["mobile"].startswith("90000") for r in rows)
    assert all(not r["college"].lower().startswith(("iit", "nit", "bits")) for r in rows)


def test_old_database_is_backed_up(tmp_path, monkeypatch):
    path = tmp_path / "old.sqlite"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE students (id INTEGER PRIMARY KEY, name TEXT, whatsapp TEXT)")
    conn.commit(); conn.close()
    monkeypatch.setenv("LEADBOARD_DB", str(path))
    import server

    with TestClient(server.app) as c:
        assert c.get("/api/stats").json()["total_simulated"] == 292
    assert any(p.name.startswith("old.sqlite.bak-") for p in tmp_path.iterdir())


def test_base_url_follows_proxy_headers(client):
    html = client.get("/lead-kit", headers={"x-forwarded-proto": "https", "host": "leadboard.example.org"}).text
    assert "https://leadboard.example.org/r/" in html
