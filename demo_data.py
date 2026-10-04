"""Fictional demo data for LeadBoard.

Everything in this file is invented. The students, campus leads, colleges and
mobile numbers do not belong to real people or institutions, and the numbers
describe a *simulated* Day-4 snapshot of a 7-day campaign. They are never real
registrations.

The data is generated with a fixed random seed, so every fresh database gets
exactly the same snapshot.
"""

import random

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

GOAL = 500
CAMPAIGN_DAYS = 7
SNAPSHOT_DAY = 4
LEAD_GOAL = 30  # 10 campus leads x 30 = the 300 Campus Lead Network target

WORKSHOP_TITLE = "Build Your First AI Project in 60 Minutes"

# 7-day planning targets (they add up to GOAL)
SOURCES = [
    # key, label, 7-day target, colour, tint
    ("campus_lead", "Campus Lead", 300, "#3B3BD6", "#E5E5FA"),
    ("college_placement", "College / Placement", 100, "#0F8A8A", "#DDF1F1"),
    ("student_referral", "Student Referral", 70, "#DB6414", "#FBE9DB"),
    ("demo_reel", "Demo Reel", 30, "#B0307A", "#F6E1EE"),
]
TARGETS = {key: target for key, _l, target, _c, _t in SOURCES}
SOURCE_LABELS = {key: label for key, label, _t, _c, _ti in SOURCES}

# Simulated registrations per campaign day (Day 1..4) for each source.
# Column sums: 39 + 63 + 84 + 106 = 292 total.
# Row sums: 172 + 52 + 47 + 21. Each is below its 7-day target.
DAY_MATRIX = {
    "campus_lead": [24, 36, 48, 64],
    "college_placement": [8, 13, 15, 16],
    "student_referral": [3, 10, 15, 19],
    "demo_reel": [4, 4, 6, 7],
}

BRANCHES = [
    "CSE",
    "IT",
    "AI & Data Science",
    "ECE",
    "EEE",
    "Mechanical",
    "Civil",
    "Other",
]
BRANCH_WEIGHTS = [34, 15, 10, 20, 8, 8, 3, 2]

# Fictional colleges (one per campus lead).
COLLEGES = [
    "Riverbend Institute of Technology",
    "Sunrise College of Engineering",
    "Greenfield University",
    "Lakeview Engineering College",
    "Hillcrest Institute of Technology",
    "Meridian College of Engineering",
    "Cedar Valley Institute of Technology",
    "Brightwater Engineering College",
    "Summit School of Engineering",
    "Oakridge Institute of Technology",
]

# code, name, college, simulated registrations on Day 4, groups posted
# 26+25+23+22+20+19+18+13+6+0 = 172 campus-lead registrations
LEADS = [
    ("LDMEKR07", "Meera Krishnan", COLLEGES[0], 26, 9),
    ("LDRODE12", "Rohan Desai", COLLEGES[1], 25, 8),
    ("LDKARE03", "Kavya Reddy", COLLEGES[2], 23, 8),
    ("LDIMSH19", "Imran Sheikh", COLLEGES[3], 22, 7),
    ("LDTAKU05", "Tanvi Kulkarni", COLLEGES[4], 20, 6),
    ("LDSINA22", "Siddharth Nair", COLLEGES[5], 19, 6),
    ("LDPOBA09", "Pooja Bansal", COLLEGES[6], 18, 5),
    ("LDARPI14", "Arvind Pillai", COLLEGES[7], 13, 3),
    ("LDNITH11", "Nisha Thomas", COLLEGES[8], 6, 1),
    ("LDDEMA16", "Dev Malhotra", COLLEGES[9], 0, 0),
]

# The six students that shipped with the original tracker keep their names and
# codes. (Their colleges are now fictional.) day, source, lead, referred_by
ORIGINAL_STUDENTS = [
    ("Ananya Rao", "ANRA21", COLLEGES[0], "campus_lead", "LDMEKR07", None),
    ("Karthik Menon", "KRMN08", COLLEGES[1], "campus_lead", "LDRODE12", None),
    ("Sneha Gupta", "SNGP14", COLLEGES[2], "college_placement", None, None),
    ("Arjun Nair", "ARJN33", COLLEGES[0], "student_referral", None, "ANRA21"),
    ("Divya Shah", "DVSH55", COLLEGES[0], "student_referral", None, "ANRA21"),
    ("Farhan Ali", "FRHN77", COLLEGES[1], "student_referral", None, "KRMN08"),
]

# A/B headline test (simulated). Registrations are split 118 / 174 = 292.
AB_VARIANTS = [
    ("A", "Build Your First AI Project in 60 Minutes", 1420, 118),
    ("B", "Ship a Live AI Project in 60 Minutes — No AI Experience Required", 1390, 174),
]

FIRST_NAMES = [
    "Aditi", "Akash", "Alisha", "Amit", "Anika", "Anirudh", "Bhavna", "Chaitra",
    "Deepak", "Devika", "Eshan", "Farah", "Gautam", "Harini", "Harsh", "Isha",
    "Jayesh", "Jiya", "Kabir", "Lakshmi", "Madhav", "Mahima", "Naveen", "Neha",
    "Omkar", "Pranav", "Priya", "Rahul", "Riya", "Sahil", "Sanjana", "Tarun",
    "Uma", "Varun", "Vidya", "Yash", "Zoya", "Charan", "Ritika", "Mohit",
]
LAST_NAMES = [
    "Agarwal", "Bhat", "Chopra", "Das", "Gill", "Hegde", "Joshi", "Kapoor",
    "Lal", "Mehta", "Naidu", "Patil", "Quraishi", "Rastogi", "Saxena", "Trivedi",
    "Uppal", "Varma", "Wadhwa", "Yadav", "Banerjee", "Chauhan", "Dubey", "Gowda",
    "Kamath", "Nambiar", "Rathore", "Shetty", "Tiwari", "Verma",
]

PLACEMENT_WEIGHTS = [10, 12, 14, 9, 11, 8, 7, 6, 5, 4]
REEL_WEIGHTS = [6, 6, 7, 8, 6, 7, 6, 5, 5, 6]


def lead_status(regs, goal=LEAD_GOAL):
    """Return (label, css key) for a lead, judged against Day-4 pace."""
    pace = goal * SNAPSHOT_DAY / CAMPAIGN_DAYS
    if regs >= pace * 1.2:
        return "Ahead of pace", "ahead"
    if regs >= pace:
        return "On track", "track"
    if regs >= pace * 0.5:
        return "Behind pace", "behind"
    return "Needs follow-up", "follow"


def expected_by_snapshot(goal=LEAD_GOAL):
    return round(goal * SNAPSHOT_DAY / CAMPAIGN_DAYS)


def build_demo_students():
    """Return the 292 simulated students in creation order (list of dicts)."""
    rng = random.Random(20261004)
    lead_college = {code: college for code, _n, college, _r, _g in LEADS}

    used_codes = {o[1] for o in ORIGINAL_STUDENTS} | set(lead_college)
    used_names = {o[0] for o in ORIGINAL_STUDENTS} | {l[1] for l in LEADS}

    def fresh_code():
        while True:
            code = "".join(rng.choice(CODE_ALPHABET) for _ in range(5))
            if code not in used_codes:
                used_codes.add(code)
                return code

    def fresh_name():
        while True:
            name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
            if name not in used_names:
                used_names.add(name)
                return name

    def pick_branch():
        return rng.choices(BRANCHES, weights=BRANCH_WEIGHTS)[0]

    rows = []

    # Lead pool: one entry per simulated lead registration, minus the two
    # that the original students already account for.
    lead_pool = []
    for code, _name, _college, regs, _groups in LEADS:
        lead_pool += [code] * regs
    for _n, _c, _col, source, lead, _ref in ORIGINAL_STUDENTS:
        if source == "campus_lead":
            lead_pool.remove(lead)
    rng.shuffle(lead_pool)

    # Remaining slots per day/source after the originals (all on Day 1).
    remaining = {k: list(v) for k, v in DAY_MATRIX.items()}
    for _n, _c, _col, source, _lead, _ref in ORIGINAL_STUDENTS:
        remaining[source][0] -= 1

    referral_counts = {}

    def add(day, name, code, college, source, lead_code, referred_by):
        rows.append(
            {
                "name": name,
                "code": code,
                "college": college,
                "branch": pick_branch(),
                "source": source,
                "lead_code": lead_code,
                "referred_by": referred_by,
                "day": day,
            }
        )
        if referred_by:
            referral_counts[referred_by] = referral_counts.get(referred_by, 0) + 1

    for name, code, college, source, lead, ref in ORIGINAL_STUDENTS:
        add(1, name, code, college, source, lead, ref)

    for day in range(1, 5):
        slots = []
        for source in DAY_MATRIX:
            slots += [source] * remaining[source][day - 1]
        rng.shuffle(slots)
        for source in slots:
            if source == "campus_lead":
                lead = lead_pool.pop()
                add(day, fresh_name(), fresh_code(), lead_college[lead], source, lead, None)
            elif source == "college_placement":
                college = rng.choices(COLLEGES, weights=PLACEMENT_WEIGHTS)[0]
                add(day, fresh_name(), fresh_code(), college, source, None, None)
            elif source == "demo_reel":
                college = rng.choices(COLLEGES, weights=REEL_WEIGHTS)[0]
                add(day, fresh_name(), fresh_code(), college, source, None, None)
            else:  # student_referral: a student created earlier shares their code
                candidates = list(rows)
                weights = [(1 + referral_counts.get(s["code"], 0)) ** 2 for s in candidates]
                referrer = rng.choices(candidates, weights=weights)[0]
                add(day, fresh_name(), fresh_code(), referrer["college"], source, None, referrer["code"])

    assert not lead_pool

    # Variant split and tidy fields.
    variants = ["A"] * AB_VARIANTS[0][3] + ["B"] * AB_VARIANTS[1][3]
    assert len(variants) == len(rows)
    rng.shuffle(variants)

    per_day_index = {}
    for i, row in enumerate(rows, start=1):
        row["variant"] = variants[i - 1]
        row["mobile"] = f"9{i:09d}"  # 9000000001 ... 9000000292, obviously synthetic
        per_day_index[row["day"]] = per_day_index.get(row["day"], 0) + 1
        minute = 8 * 60 + (per_day_index[row["day"]] * 7) % (14 * 60)
        row["created_at"] = f"Day {row['day']} {minute // 60:02d}:{minute % 60:02d}"
    return rows
