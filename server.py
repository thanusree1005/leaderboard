#!/usr/bin/env python3
"""LeadBoard: FastAPI + SQLite referral tracker for the workshop campaign.

Pages: Lead Kit, Leaderboard, Register, Admin Dashboard.
Python packages: fastapi, uvicorn, python-multipart, jinja2.

Data lives in registrations.sqlite beside this file (override with the
LEADBOARD_DB environment variable). On first start the database is filled with
a fictional, clearly labelled Day-4 simulation (see demo_data.py). Anything
submitted through the Register form is stored as a *live test sign-up* and is
always counted separately from the simulation.
"""

import os
import secrets
import shutil
import sqlite3
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlencode

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ValidationError, field_validator, model_validator

import demo_data as dd

HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8765"))
ROOT = os.path.dirname(os.path.abspath(__file__))
IST = timezone(timedelta(hours=5, minutes=30))
CODE_ALPHABET = dd.CODE_ALPHABET

DEMO_LABEL = "DEMO DATA — SIMULATED RESULTS"
SNAPSHOT_LABEL = "DAY 4 — SIMULATED SNAPSHOT"
SHARE_TEXT = (
    "Build Your First AI Project in 60 Minutes — a free hands-on AI workshop. "
    "No prior AI experience required. Register here: {link}"
)
NUDGE_TEXT = (
    "Hi {first}, quick check-in on the AI workshop campaign. You are at "
    "{regs} of {goal} registrations. Could you post your Lead Kit message in "
    "two more WhatsApp groups today? Your link: {link}"
)

templates = Jinja2Templates(directory=os.path.join(ROOT, "templates"))


# ---------------------------------------------------------------- validation
def normalize_mobile(raw):
    digits = "".join(ch for ch in raw if ch.isdigit())
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    if len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return digits


class Registration(BaseModel):
    name: str
    college: str
    branch: str
    year: str
    mobile: str
    referral: str = ""
    variant: str = "A"
    src: str = ""

    @field_validator(
        "name", "college", "branch", "year", "mobile", "referral", "variant", "src",
        mode="before",
    )
    @classmethod
    def strip_text(cls, value):
        if value is None:
            return ""
        return str(value).strip()

    @field_validator("referral")
    @classmethod
    def upper_referral(cls, value):
        return value.upper()

    @model_validator(mode="after")
    def check_fields(self):
        if not self.name or len(self.name) > 80:
            raise ValueError("Enter a name.")
        if not self.college or len(self.college) > 120:
            raise ValueError("Enter a college.")
        if self.branch not in dd.BRANCHES:
            raise ValueError("Choose a branch from the list.")
        if not self.year:
            raise ValueError("Choose your year of study.")
        if self.year != "Final year":
            raise ValueError("This workshop registration is for final-year students.")
        phone = normalize_mobile(self.mobile)
        if len(phone) != 10 or phone[0] not in "6789":
            raise ValueError("Enter a 10-digit Indian mobile number.")
        self.mobile = phone
        if self.referral and not self.referral.isalnum():
            raise ValueError("Referral codes are letters and digits only.")
        if len(self.referral) > 12:
            raise ValueError("That referral code is too long.")
        self.variant = self.variant.upper() if self.variant.upper() in ("A", "B") else "A"
        self.src = self.src.lower()
        return self


def validation_message(exc):
    msg = exc.errors()[0]["msg"]
    prefix = "Value error, "
    if msg.startswith(prefix):
        msg = msg[len(prefix):]
    return msg


# ------------------------------------------------------------------ database
SCHEMA = """
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    college TEXT NOT NULL,
    branch TEXT NOT NULL DEFAULT 'Other',
    year TEXT NOT NULL,
    mobile TEXT NOT NULL UNIQUE,
    code TEXT NOT NULL UNIQUE,
    referred_by TEXT,
    lead_code TEXT,
    source TEXT NOT NULL DEFAULT 'direct',
    variant TEXT NOT NULL DEFAULT 'A',
    is_demo INTEGER NOT NULL DEFAULT 0,
    campaign_day INTEGER,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS leads (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    college TEXT NOT NULL,
    goal INTEGER NOT NULL,
    groups_posted INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS ab_variants (
    variant TEXT PRIMARY KEY,
    headline TEXT NOT NULL,
    views INTEGER NOT NULL
);
"""


def db_path():
    return os.environ.get("LEADBOARD_DB") or os.path.join(ROOT, "registrations.sqlite")


@contextmanager
def db():
    conn = sqlite3.connect(db_path(), timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _is_current_schema(path):
    conn = sqlite3.connect(path)
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(students)")}
    finally:
        conn.close()
    return not cols or {"mobile", "is_demo", "lead_code"} <= cols


def now_ist():
    return datetime.now(IST).isoformat(timespec="seconds")


def init_db():
    path = db_path()
    if os.path.exists(path) and not _is_current_schema(path):
        # Database from the original tracker: keep it as a backup, start fresh.
        shutil.move(path, f"{path}.bak-{datetime.now(IST).strftime('%Y%m%d%H%M%S')}")
    with db() as conn:
        conn.executescript(SCHEMA)
        if conn.execute("SELECT COUNT(*) FROM students").fetchone()[0] == 0:
            seed(conn)


def seed(conn):
    conn.execute("DELETE FROM leads")
    conn.execute("DELETE FROM ab_variants")
    conn.executemany(
        "INSERT INTO leads (code, name, college, goal, groups_posted) VALUES (?, ?, ?, ?, ?)",
        [(c, n, col, dd.LEAD_GOAL, g) for c, n, col, _r, g in dd.LEADS],
    )
    conn.executemany(
        "INSERT INTO ab_variants (variant, headline, views) VALUES (?, ?, ?)",
        [(v, h, views) for v, h, views, _r in dd.AB_VARIANTS],
    )
    conn.executemany(
        """
        INSERT INTO students
            (name, college, branch, year, mobile, code, referred_by, lead_code,
             source, variant, is_demo, campaign_day, created_at)
        VALUES (?, ?, ?, 'Final year', ?, ?, ?, ?, ?, ?, 1, ?, ?)
        """,
        [
            (
                s["name"], s["college"], s["branch"], s["mobile"], s["code"],
                s["referred_by"], s["lead_code"], s["source"], s["variant"],
                s["day"], s["created_at"],
            )
            for s in dd.build_demo_students()
        ],
    )


def new_code(conn):
    while True:
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(5))
        taken = conn.execute(
            "SELECT 1 FROM students WHERE code = ? UNION SELECT 1 FROM leads WHERE code = ?",
            (code, code),
        ).fetchone()
        if not taken:
            return code


def resolve_code(conn, code):
    """Find who a referral code belongs to: a campus lead or a student."""
    if not code:
        return None
    lead = conn.execute(
        "SELECT code, name, college FROM leads WHERE code = ?", (code,)
    ).fetchone()
    if lead:
        return {"kind": "lead", "code": lead["code"], "name": lead["name"], "college": lead["college"]}
    student = conn.execute(
        "SELECT code, name, college FROM students WHERE code = ?", (code,)
    ).fetchone()
    if student:
        return {"kind": "student", "code": student["code"], "name": student["name"], "college": student["college"]}
    return None


# ------------------------------------------------------------------- queries
def sim_total(conn):
    return conn.execute("SELECT COUNT(*) FROM students WHERE is_demo = 1").fetchone()[0]


def live_total(conn):
    return conn.execute("SELECT COUNT(*) FROM students WHERE is_demo = 0").fetchone()[0]


def pct(part, whole):
    return round(part * 100 / whole) if whole else 0


def source_breakdown(conn):
    counts = {
        r["source"]: r["n"]
        for r in conn.execute(
            "SELECT source, COUNT(*) AS n FROM students WHERE is_demo = 1 GROUP BY source"
        )
    }
    rows = []
    for key, label, target, color, tint in dd.SOURCES:
        n = counts.get(key, 0)
        rows.append(
            {
                "key": key, "label": label, "count": n, "target": target,
                "pct": pct(n, target), "fill": min(100, n * 100 / target),
                "width": target * 100 / dd.GOAL, "color": color, "tint": tint,
            }
        )
    return rows


def lead_rows(conn):
    rows = conn.execute(
        """
        SELECT l.code, l.name, l.college, l.goal, l.groups_posted,
               (SELECT COUNT(*) FROM students s WHERE s.lead_code = l.code AND s.is_demo = 1) AS regs,
               (SELECT COUNT(*) FROM students s WHERE s.lead_code = l.code AND s.is_demo = 0) AS live
        FROM leads l
        ORDER BY regs DESC, live DESC, l.name COLLATE NOCASE ASC
        """
    ).fetchall()
    out = []
    for rank, r in enumerate(rows, start=1):
        label, key = dd.lead_status(r["regs"], r["goal"])
        out.append(
            {
                "rank": rank, "code": r["code"], "name": r["name"], "college": r["college"],
                "goal": r["goal"], "groups": r["groups_posted"], "regs": r["regs"],
                "live": r["live"], "pct": pct(r["regs"], r["goal"]),
                "fill": min(100, r["regs"] * 100 / r["goal"]),
                "status": label, "status_key": key,
                "expected": dd.expected_by_snapshot(r["goal"]),
            }
        )
    return out


def college_rows(conn):
    rows = conn.execute(
        """
        SELECT college, COUNT(*) AS n FROM students WHERE is_demo = 1
        GROUP BY college ORDER BY n DESC, college COLLATE NOCASE ASC
        """
    ).fetchall()
    top = rows[0]["n"] if rows else 1
    return [
        {"rank": i, "college": r["college"], "count": r["n"], "fill": r["n"] * 100 / top}
        for i, r in enumerate(rows, start=1)
    ]


def student_board(conn, limit=10):
    rows = conn.execute(
        """
        SELECT s.name, s.college, s.code,
               (SELECT COUNT(*) FROM students r WHERE r.referred_by = s.code AND r.is_demo = 1) AS sim,
               (SELECT COUNT(*) FROM students r WHERE r.referred_by = s.code AND r.is_demo = 0) AS live
        FROM students s
        WHERE sim + live > 0
        ORDER BY sim DESC, live DESC, s.name COLLATE NOCASE ASC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    top = max([r["sim"] for r in rows] + [1])
    return [
        {
            "rank": i, "name": r["name"], "college": r["college"], "code": r["code"],
            "sim": r["sim"], "live": r["live"], "fill": r["sim"] * 100 / top,
        }
        for i, r in enumerate(rows, start=1)
    ]


def daily_trend(conn):
    counts = {
        r["campaign_day"]: r["n"]
        for r in conn.execute(
            "SELECT campaign_day, COUNT(*) AS n FROM students WHERE is_demo = 1 GROUP BY campaign_day"
        )
    }
    days = []
    for day in range(1, dd.CAMPAIGN_DAYS + 1):
        n = counts.get(day) if day <= dd.SNAPSHOT_DAY else None
        days.append({"day": day, "count": n})
    top = max([d["count"] or 0 for d in days] + [1])
    for d in days:
        d["height"] = (d["count"] or 0) * 100 / top
    return days


def ab_rows(conn):
    regs = {
        r["variant"]: r["n"]
        for r in conn.execute(
            "SELECT variant, COUNT(*) AS n FROM students WHERE is_demo = 1 GROUP BY variant"
        )
    }
    out = []
    for r in conn.execute("SELECT variant, headline, views FROM ab_variants ORDER BY variant"):
        n = regs.get(r["variant"], 0)
        out.append(
            {
                "variant": r["variant"], "headline": r["headline"], "views": r["views"],
                "regs": n, "rate": round(n * 100 / r["views"], 1) if r["views"] else 0.0,
            }
        )
    if len(out) == 2:
        best = max(out, key=lambda v: v["rate"])
        for v in out:
            v["leading"] = v is best
        lo = min(out, key=lambda v: v["rate"])
        best["lift"] = round((best["rate"] - lo["rate"]) * 100 / lo["rate"]) if lo["rate"] else 0
    return out


def top_referrer(conn):
    board = student_board(conn, limit=1)
    return board[0] if board else None


def latest_live(conn, limit=8):
    rows = conn.execute(
        """
        SELECT name, college, mobile, source, referred_by, lead_code, variant, created_at
        FROM students WHERE is_demo = 0 ORDER BY id DESC LIMIT ?
        """,
        (limit,),
    ).fetchall()
    out = []
    for r in rows:
        who = resolve_code(conn, r["lead_code"] or r["referred_by"])
        out.append(
            {
                "name": r["name"], "college": r["college"],
                "mobile": "XXXXXX" + r["mobile"][-4:],
                "source": dd.SOURCE_LABELS.get(r["source"], "Direct (no code)"),
                "credited": who["name"] if who else "No one",
                "variant": r["variant"], "when": r["created_at"].replace("T", " ")[:16],
            }
        )
    return out


def stats_payload(conn):
    sources = source_breakdown(conn)
    return {
        "simulated": True,
        "label": DEMO_LABEL,
        "snapshot": SNAPSHOT_LABEL,
        "goal": dd.GOAL,
        "total_simulated": sim_total(conn),
        "progress_pct": pct(sim_total(conn), dd.GOAL),
        "sources": {s["key"]: {"count": s["count"], "target": s["target"]} for s in sources},
        "active_leads": sum(1 for l in lead_rows(conn) if l["regs"] > 0),
        "total_leads": len(dd.LEADS),
        "live_signups": live_total(conn),
    }


# ------------------------------------------------------------------- helpers
def base_url(request):
    env = os.environ.get("PUBLIC_BASE_URL")
    if env:
        return env.rstrip("/")
    proto = request.headers.get("x-forwarded-proto", request.url.scheme).split(",")[0].strip()
    host = (
        request.headers.get("x-forwarded-host")
        or request.headers.get("host")
        or request.url.netloc
    )
    return f"{proto}://{host.split(',')[0].strip()}"


def referral_link(request, code):
    return f"{base_url(request)}/r/{code}"


def whatsapp_url(text):
    return "https://wa.me/?text=" + quote(text, safe="")


def render(request, template, active, status_code=200, **ctx):
    ctx.update(
        active=active, demo_label=DEMO_LABEL, snapshot_label=SNAPSHOT_LABEL,
        goal=dd.GOAL, snapshot_day=dd.SNAPSHOT_DAY, campaign_days=dd.CAMPAIGN_DAYS,
        workshop_title=dd.WORKSHOP_TITLE,
    )
    return templates.TemplateResponse(request, template, ctx, status_code=status_code)


# -------------------------------------------------------------------- the app
@asynccontextmanager
async def lifespan(_app):
    init_db()
    yield


app = FastAPI(title="LeadBoard", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=os.path.join(ROOT, "static")), name="static")


@app.get("/")
def home():
    return RedirectResponse("/lead-kit", status_code=307)


@app.get("/favicon.ico")
def favicon():
    return HTMLResponse("", status_code=204)


@app.get("/healthz")
def healthz():
    with db() as conn:
        return {"ok": True, "simulated_registrations": sim_total(conn)}


@app.get("/api/stats")
def api_stats():
    with db() as conn:
        return JSONResponse(stats_payload(conn))


@app.get("/r/{code}")
def referral_redirect(code: str):
    return RedirectResponse(f"/register?{urlencode({'ref': code.upper()[:12]})}", status_code=302)


@app.get("/lead-kit", response_class=HTMLResponse)
def lead_kit(request: Request, lead: str = ""):
    with db() as conn:
        leads = lead_rows(conn)
        total = sim_total(conn)
    chosen = next((l for l in leads if l["code"] == lead.upper()), leads[0])
    link = referral_link(request, chosen["code"])
    message = SHARE_TEXT.format(link=link)
    return render(
        request, "leadkit.html", "lead-kit",
        leads=leads, lead=chosen, link=link, message=message,
        wa_url=whatsapp_url(message), total=total,
    )


@app.get("/leaderboard", response_class=HTMLResponse)
def leaderboard_page(request: Request):
    with db() as conn:
        sources = source_breakdown(conn)
        total = sim_total(conn)
        return render(
            request, "leaderboard.html", "leaderboard",
            total=total, progress=pct(total, dd.GOAL), sources=sources,
            leads=lead_rows(conn), colleges=college_rows(conn),
            students=student_board(conn),
        )


@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request):
    with db() as conn:
        sources = source_breakdown(conn)
        total = sim_total(conn)
        leads = lead_rows(conn)
        follow_up = []
        for l in leads:
            if l["status_key"] in ("behind", "follow"):
                link = referral_link(request, l["code"])
                nudge = NUDGE_TEXT.format(
                    first=l["name"].split()[0], regs=l["regs"], goal=l["goal"], link=link
                )
                follow_up.append({**l, "nudge_url": whatsapp_url(nudge)})
        follow_up.sort(key=lambda l: (l["regs"], l["name"]))
        return render(
            request, "admin.html", "admin",
            total=total, progress=pct(total, dd.GOAL), sources=sources,
            active_leads=sum(1 for l in leads if l["regs"] > 0), total_leads=len(leads),
            top=top_referrer(conn), follow_up=follow_up, trend=daily_trend(conn),
            ab=ab_rows(conn), live_count=live_total(conn), live=latest_live(conn),
            expected_total=round(dd.GOAL * dd.SNAPSHOT_DAY / dd.CAMPAIGN_DAYS),
        )


# --------------------------------------------------------------- registration
def register_context(conn, request, form, error=""):
    ref = (form.get("referral") or "").strip().upper()
    variant = (form.get("variant") or "A").upper()
    if variant not in ("A", "B"):
        variant = "A"
    headline = next((h for v, h, _views, _r in dd.AB_VARIANTS if v == variant), dd.WORKSHOP_TITLE)
    return {
        "form": form, "error": error, "variant": variant, "headline": headline,
        "referrer": resolve_code(conn, ref), "branches": dd.BRANCHES,
        "years": ["1st year", "2nd year", "3rd year", "Final year"],
        "colleges": dd.COLLEGES,
    }


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request, ref: str = "", v: str = "A", src: str = ""):
    form = {"referral": ref.strip().upper()[:12], "variant": v, "src": src}
    with db() as conn:
        ctx = register_context(conn, request, form)
    return render(request, "register.html", "register", **ctx)


@app.post("/register")
def register(
    request: Request,
    name: str = Form(""),
    college: str = Form(""),
    branch: str = Form(""),
    year: str = Form(""),
    mobile: str = Form(""),
    referral: str = Form(""),
    variant: str = Form("A"),
    src: str = Form(""),
):
    form = {
        "name": name, "college": college, "branch": branch, "year": year,
        "mobile": mobile, "referral": referral, "variant": variant, "src": src,
    }

    def fail(message):
        with db() as conn:
            ctx = register_context(conn, request, form, message)
        return render(request, "register.html", "register", status_code=400, **ctx)

    try:
        reg = Registration(**form)
    except ValidationError as exc:
        return fail(validation_message(exc))

    with db() as conn:
        if conn.execute("SELECT 1 FROM students WHERE mobile = ?", (reg.mobile,)).fetchone():
            return fail("That mobile number is already registered.")
        code = new_code(conn)
        who = resolve_code(conn, reg.referral)
        ref_status = "none"
        referred_by = None
        lead_code = None
        if reg.referral:
            if who:
                ref_status = "credited"
                if who["kind"] == "lead":
                    lead_code = who["code"]
                else:
                    referred_by = who["code"]
            else:
                ref_status = "unknown"
        if lead_code:
            source = "campus_lead"
        elif referred_by:
            source = "student_referral"
        elif reg.src in ("placement", "college"):
            source = "college_placement"
        elif reg.src == "reel":
            source = "demo_reel"
        else:
            source = "direct"
        conn.execute(
            """
            INSERT INTO students
                (name, college, branch, year, mobile, code, referred_by, lead_code,
                 source, variant, is_demo, campaign_day, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, ?)
            """,
            (
                reg.name, reg.college, reg.branch, reg.year, reg.mobile, code,
                referred_by, lead_code, source, reg.variant, now_ist(),
            ),
        )
    query = urlencode(
        {"code": code, "name": reg.name, "ref": reg.referral, "ref_status": ref_status}
    )
    return RedirectResponse("/register/success?" + query, status_code=303)


@app.get("/register/success", response_class=HTMLResponse)
def register_success(
    request: Request, code: str = "", name: str = "", ref: str = "", ref_status: str = "none"
):
    with db() as conn:
        me = resolve_code(conn, code.upper())
        if not me or me["kind"] != "student":
            return RedirectResponse("/register", status_code=303)
        referrer = resolve_code(conn, ref.upper()) if ref_status == "credited" else None
    link = referral_link(request, me["code"])
    message = SHARE_TEXT.format(link=link)
    return render(
        request, "success.html", "register",
        name=name or me["name"], code=me["code"], link=link, message=message,
        wa_url=whatsapp_url(message), referrer=referrer, ref=ref.upper(),
        ref_status=ref_status,
    )


def main():
    import uvicorn

    uvicorn.run("server:app", host=HOST, port=PORT, app_dir=ROOT)


if __name__ == "__main__":
    main()
