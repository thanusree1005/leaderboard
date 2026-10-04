---
title: LeadBoard
emoji: 📊
colorFrom: indigo
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
---

# LeadBoard

Campus lead kit, public leaderboard, admin dashboard and referral-tracked registration for the free workshop **"Build Your First AI Project in 60 Minutes"**. FastAPI + SQLite, server-rendered pages, no build step.

**All campaign data is fictional and simulated.** Every page shows `DEMO DATA — SIMULATED RESULTS`, and the leaderboard and admin pages also show `DAY 4 — SIMULATED SNAPSHOT`. Students, campus leads, colleges and mobile numbers are invented (mobile numbers run 9000000001 to 9000000292).

## Pages

| Page | URL | What it does |
|---|---|---|
| Lead Kit | `/lead-kit` (also `/`) | Per-lead card: lead code, personal referral URL, registrations, goal, progress, groups posted, rank, status. Copy link, copy WhatsApp message, open WhatsApp. Switch between the 10 demo leads at the top. |
| Leaderboard | `/leaderboard` | 292 of 500 simulated registrations with a per-source progress bar, top campus leads, college ranking, student referral ranking. |
| Register | `/register` | Name, college, branch, year, mobile, referral code. Final-year and Indian-mobile validation, duplicate prevention, referral attribution. Success page has the referral link, "Share with 2 friends" and a WhatsApp share button. |
| Admin Dashboard | `/admin` | KPI cards, registrations by source vs 7-day targets, daily trend, A/B variant performance, leads needing follow-up, and live test sign-ups. |
| Referral link | `/r/<code>` | Redirects to `/register?ref=<code>`. Works for lead codes and student codes. |
| JSON | `/api/stats`, `/healthz` | Machine-readable summary and a health check. |

## Simulated Day-4 snapshot

| Source | Day 4 (simulated) | 7-day target |
|---|---|---|
| Campus Lead | 172 | 300 |
| College / Placement | 52 | 100 |
| Student Referral | 47 | 70 |
| Demo Reel | 21 | 30 |
| **Total** | **292** | **500** |

Daily trend: 39, 63, 84, 106 (Days 1 to 4). Ten campus leads have a goal of 30 each (10 x 30 = the 300 Campus Lead target). The A/B test is simulated: Variant A 1,420 views and 118 registrations (8.3%), Variant B 1,390 views and 174 registrations (12.5%).

Test sign-ups made through the Register form are stored as **live** rows and are kept apart from the simulation: they never change the 292, the source counts or the lead totals. They show in Admin under "Live test sign-ups", in the "Live" column of the student leaderboard, and as a separate note on a lead's kit.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python server.py
```

Open http://127.0.0.1:8765/. The database `registrations.sqlite` is created and seeded on first start. Delete it and restart to reset the demo.

If you have the earlier version of this tracker, its database is renamed to `registrations.sqlite.bak-<timestamp>` and a new one is created.

## Test

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

39 checks: every page, navigation, disclosure labels, Lead Kit contents and WhatsApp links, referral redirects and attribution, registration validation and duplicates, the 292 / 500 numbers and per-source targets, no placeholder URLs, and the migration of the old database.

## Deploy for free

GitHub Pages cannot run FastAPI (static files only). Use one of these instead.

**Render (Web Service, free).** Push this folder to a GitHub repo, then in Render choose New > Web Service, connect the repo and set:
- Runtime: Python 3
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn server:app --host 0.0.0.0 --port $PORT`
- Health check path: `/healthz`
- Instance type: Free

`render.yaml` holds the same settings if you prefer New > Blueprint.

**Hugging Face Spaces (Docker, free).** Create a Space with the Docker SDK, then upload or push these files. The front matter at the top of this README and the `Dockerfile` already set the port to 7860.

On both, the disk is temporary: the database is rebuilt and re-seeded from `demo_data.py` after a restart, so the simulation is always there but live test sign-ups are lost. Free instances also sleep when idle, so the first request after a quiet period can take 30 to 60 seconds. Open the URL yourself shortly before you submit.

Set `PUBLIC_BASE_URL` (for example to your final site address) only if referral links show the wrong host. Normally the host is read from the request.

## Files

- `server.py`: routes, validation, SQLite access, queries
- `demo_data.py`: fictional leads, colleges, students, targets and A/B figures
- `templates/`: `base.html`, `_macros.html`, `leadkit.html`, `leaderboard.html`, `register.html`, `success.html`, `admin.html`
- `static/`: `style.css`, `app.js`, `favicon.svg`
- `tests/test_app.py`
- `Dockerfile`, `render.yaml`, `.dockerignore`, `.gitignore`, `requirements.txt`, `requirements-dev.txt`, `pytest.ini`
