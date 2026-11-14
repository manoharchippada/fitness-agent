#!/usr/bin/env python3
"""fit.py - compact data helper for the calorie agent (standard library only).

Every command prints short output so Claude never has to read raw CSVs.
Run `python scripts/fit.py help` for usage.
"""
import csv
import datetime as dt
import glob
import json
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOODS = os.path.join(ROOT, "data", "foods.csv")
ACT = os.path.join(ROOT, "data", "activity.csv")
DAILY = os.path.join(ROOT, "data", "daily.csv")
LOGDIR = os.path.join(ROOT, "data", "log")
PROFILE = os.path.join(ROOT, "profile.json")
GYMDIR = os.path.join(ROOT, "data", "gym")
EXFILE = os.path.join(ROOT, "data", "exercises.csv")

FOOD_H = ["key", "serving", "kcal", "p", "c", "f", "src"]
LOG_H = ["date", "meal", "food", "qty", "kcal", "p", "c", "f"]
ACT_H = ["date", "total", "active", "steps", "sleep_h", "rhr", "weight", "workout"]
DAILY_H = ["date", "in", "out", "net", "p", "c", "f", "steps", "weight", "gym_sets", "gym_vol", "gym_min"]
EX_H = ["key", "group", "type"]  # type: w = weights, bw = bodyweight, c = cardio
GYM_H = ["date", "exercise", "group", "sets", "reps", "kg", "min", "vol"]
GROUPS = ["chest", "back", "legs", "shoulders", "arms", "core", "cardio", "full"]
MEALS = {"B": "breakfast", "L": "lunch", "D": "dinner", "S": "snack"}
ACT_ALIASES = {"sleep": "sleep_h", "sl": "sleep_h", "s": "steps", "a": "active",
               "t": "total", "w": "weight", "hr": "rhr"}


# ---------- io helpers ----------
def read(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def write(path, header, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, header, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def append(path, header, rows):
    new = not os.path.exists(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, header, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerows(rows)


def num(x, default=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def g(x):
    """Format a number compactly (no trailing .0)."""
    if x is None or x == "":
        return "-"
    x = round(float(x), 1)
    return str(int(x)) if x == int(x) else str(x)


def profile():
    try:
        with open(PROFILE, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def norm_key(s):
    return "_".join(s.strip().lower().replace("-", " ").split())


def parse_date(s):
    today = dt.date.today()
    s = (s or "today").strip().lower()
    if s in ("today", "t"):
        return today.isoformat()
    if s in ("y", "yesterday"):
        return (today - dt.timedelta(days=1)).isoformat()
    if s.startswith("-") and s[1:].isdigit():
        return (today - dt.timedelta(days=int(s[1:]))).isoformat()
    if len(s) == 5 and s[2] == "-":  # MM-DD
        s = f"{today.year}-{s}"
    return dt.date.fromisoformat(s).isoformat()


def is_date(s):
    try:
        parse_date(s)
        return True
    except ValueError:
        return False


def log_path(date):
    return os.path.join(LOGDIR, date[:7] + ".csv")


def all_logs():
    rows = []
    for p in sorted(glob.glob(os.path.join(LOGDIR, "*.csv"))):
        rows += read(p)
    return rows


def foods_map():
    return {r["key"]: r for r in read(FOODS)}


def gym_path(date):
    return os.path.join(GYMDIR, date[:7] + ".csv")


def all_gym():
    rows = []
    for p in sorted(glob.glob(os.path.join(GYMDIR, "*.csv"))):
        rows += read(p)
    return rows


# ---------- rollup ----------
def rollup(quiet=False):
    days = defaultdict(lambda: {"in": 0.0, "p": 0.0, "c": 0.0, "f": 0.0})
    for r in all_logs():
        d = days[r["date"]]
        for k, src in (("in", "kcal"), ("p", "p"), ("c", "c"), ("f", "f")):
            d[k] += num(r[src], 0)
    gym = defaultdict(lambda: [0.0, 0.0, 0.0])  # sets, volume, minutes
    for r in all_gym():
        gd = gym[r["date"]]
        gd[0] += num(r["sets"], 0)
        gd[1] += num(r["vol"], 0)
        gd[2] += num(r["min"], 0)
    act = {r["date"]: r for r in read(ACT)}
    out = []
    for date in sorted(set(days) | set(act) | set(gym)):
        a = act.get(date, {})
        food = days.get(date)
        total = num(a.get("total"))
        row = {"date": date, "steps": a.get("steps", ""), "weight": a.get("weight", ""),
               "out": g(total) if total is not None else ""}
        if date in gym:
            row.update(gym_sets=g(gym[date][0]), gym_vol=g(gym[date][1]), gym_min=g(gym[date][2]))
        if food:
            row.update({k: g(v) for k, v in food.items()})
            if total is not None:
                row["net"] = g(food["in"] - total)
        out.append(row)
    write(DAILY, DAILY_H, out)
    months = lambda d: sorted(os.path.basename(p)[:7] for p in glob.glob(os.path.join(d, "*.csv")))
    with open(os.path.join(ROOT, "data", "index.json"), "w", encoding="utf-8") as fh:
        json.dump({"log": months(LOGDIR), "gym": months(GYMDIR)}, fh)
    if not quiet:
        print(f"daily.csv: {len(out)} days")


def day_line(date):
    """One-line summary for a date vs targets."""
    pr = profile()
    rows = [r for r in read(log_path(date)) if r["date"] == date]
    kin = sum(num(r["kcal"], 0) for r in rows)
    p = sum(num(r["p"], 0) for r in rows)
    act = {r["date"]: r for r in read(ACT)}.get(date, {})
    out = num(act.get("total"))
    tgt = pr.get("kcal_target")
    s = f"{date}: in {g(kin)}"
    if tgt:
        s += f"/{g(tgt)} (left {g(tgt - kin)})"
    s += f" | P {g(p)}"
    if pr.get("protein_g"):
        s += f"/{g(pr['protein_g'])}g"
    if out is not None:
        s += f" | out {g(out)} | net {g(kin - out)}"
    return s


# ---------- commands ----------
def cmd_find(args):
    term = norm_key(" ".join(args))
    hits = [r for r in read(FOODS) if term in r["key"]]
    if not hits:
        print(f"no match: {term}")
    for r in hits[:15]:
        print(f"{r['key']} | {r['serving']} | {r['kcal']}kcal P{r['p']} C{r['c']} F{r['f']} ({r['src']})")


def cmd_food(args):
    if len(args) < 6:
        sys.exit('usage: food KEY "SERVING" KCAL P C F [src]')
    key = norm_key(args[0])
    vals = [num(v) for v in args[2:6]]
    if None in vals:
        sys.exit("KCAL P C F must be numbers")
    row = {"key": key, "serving": args[1], "kcal": g(vals[0]), "p": g(vals[1]),
           "c": g(vals[2]), "f": g(vals[3]), "src": args[6] if len(args) > 6 else "est"}
    rows = read(FOODS)
    existed = any(r["key"] == key for r in rows)
    rows = [r for r in rows if r["key"] != key] + [row]
    rows.sort(key=lambda r: r["key"])
    write(FOODS, FOOD_H, rows)
    print(("updated " if existed else "added ") + f"{key} {row['serving']} {row['kcal']}kcal")


def parse_items(text):
    items = []
    for part in text.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        sep = ":" if ":" in part else ("*" if "*" in part else None)
        if sep:
            k, q = part.rsplit(sep, 1)
            qty = num(q)
            if qty is None:
                sys.exit(f"bad qty in '{part}'")
        else:
            k, qty = part, 1.0
        items.append((norm_key(k), qty))
    return items


def cmd_add(args):
    date = parse_date("today")
    if args and is_date(args[0]) and args[0].upper() not in MEALS:
        date, args = parse_date(args[0]), args[1:]
    if len(args) < 2 or args[0].upper() not in MEALS:
        sys.exit('usage: add [DATE] B|L|D|S "key:qty, key:qty"')
    meal = args[0].upper()
    items = parse_items(" ".join(args[1:]))
    fm = foods_map()
    unknown = [k for k, _ in items if k not in fm]
    if unknown:
        print("UNKNOWN: " + ", ".join(unknown))
        print('add each: fit.py food KEY "SERVING" KCAL P C F est  (nothing was logged)')
        sys.exit(1)
    rows = []
    for k, q in items:
        f = fm[k]
        rows.append({"date": date, "meal": meal, "food": k, "qty": g(q),
                     **{m: g(num(f[m], 0) * q) for m in ("kcal", "p", "c", "f")}})
    append(log_path(date), LOG_H, rows)
    rollup(quiet=True)
    added = sum(num(r["kcal"]) for r in rows)
    print(f"+{g(added)} kcal {MEALS[meal]} | " + day_line(date))


def cmd_del(args):
    if len(args) < 3:
        sys.exit("usage: del DATE MEAL KEY")
    date, meal, key = parse_date(args[0]), args[1].upper(), norm_key(args[2])
    path = log_path(date)
    rows = read(path)
    for i in range(len(rows) - 1, -1, -1):
        r = rows[i]
        if r["date"] == date and r["meal"] == meal and r["food"] == key:
            del rows[i]
            write(path, LOG_H, rows)
            rollup(quiet=True)
            print(f"removed {key} ({r['kcal']} kcal) | " + day_line(date))
            return
    print("not found")


def upsert_act(date, vals):
    rows = {r["date"]: r for r in read(ACT)}
    row = rows.get(date, {"date": date})
    for k, v in vals.items():
        if v not in (None, ""):
            row[k] = v
    if not row.get("total") and row.get("active"):
        bmr = profile().get("bmr")
        if bmr:
            row["total"] = g(num(row["active"], 0) + bmr)
    rows[date] = row
    write(ACT, ACT_H, [rows[d] for d in sorted(rows)])
    return row


def cmd_act(args):
    date = parse_date("today")
    if args and "=" not in args[0] and is_date(args[0]):
        date, args = parse_date(args[0]), args[1:]
    vals = {}
    for a in args:
        if "=" not in a:
            sys.exit(f"expected key=value, got '{a}'")
        k, v = a.split("=", 1)
        k = ACT_ALIASES.get(k.lower(), k.lower())
        if k not in ACT_H[1:]:
            sys.exit(f"unknown field {k}; use {', '.join(ACT_H[1:])}")
        vals[k] = v if k == "workout" else g(num(v))
    row = upsert_act(date, vals)
    rollup(quiet=True)
    print("act " + " ".join(f"{k}={row[k]}" for k in ACT_H[1:] if row.get(k)) + " | " + day_line(date))


def cmd_zepp(args):
    if not args:
        sys.exit("usage: zepp PATH (folder or csv from Zepp export)")
    path = args[0]
    files = [path] if os.path.isfile(path) else glob.glob(os.path.join(path, "**", "*.csv"), recursive=True)
    merged = defaultdict(dict)
    for fp in files:
        rows = read(fp)
        if not rows or "date" not in rows[0]:
            continue
        cols = set(rows[0])
        name = os.path.basename(fp).upper()
        for r in rows:
            try:
                date = parse_date(r["date"][:10])
            except ValueError:
                continue
            m = merged[date]
            if "steps" in cols and "calories" in cols and "MINUTE" not in name:
                if num(r["steps"], 0) > 0:
                    m["steps"] = g(num(r["steps"]))
                if num(r["calories"], 0) > 0:
                    m["active"] = g(num(r["calories"]))
            elif "deepSleepTime" in cols:
                mins = sum(num(r.get(k), 0) for k in ("deepSleepTime", "shallowSleepTime", "REMTime"))
                if mins > 0:
                    m["sleep_h"] = g(mins / 60)
            elif "weight" in cols and num(r.get("weight")):
                m["weight"] = g(num(r["weight"]))
    n = 0
    for date in sorted(merged):
        if merged[date]:
            upsert_act(date, merged[date])
            n += 1
    rollup(quiet=True)
    print(f"zepp: {n} days imported from {len(files)} files")


def cmd_day(args):
    date = parse_date(args[0] if args else "today")
    rows = [r for r in read(log_path(date)) if r["date"] == date]
    for m in "BLDS":
        items = [r for r in rows if r["meal"] == m]
        if items:
            kc = sum(num(r["kcal"], 0) for r in items)
            print(f"{m} {g(kc)}: " + ", ".join(f"{r['food']}x{r['qty']}" for r in items))
    print(day_line(date))


def pct(a, b):
    return f"{round(100 * a / b)}%" if b else "-"


def cmd_stats(args):
    n = int(args[0]) if args else 7
    pr = profile()
    end = dt.date.today()
    start = end - dt.timedelta(days=n - 1)
    rng = [(start + dt.timedelta(days=i)).isoformat() for i in range(n)]
    daily = {r["date"]: r for r in read(DAILY)}
    fdays = [daily[d] for d in rng if d in daily and num(daily[d].get("in"))]
    odays = [daily[d] for d in rng if d in daily and num(daily[d].get("out"))]
    ndays = [daily[d] for d in rng if d in daily and daily[d].get("net") not in (None, "")]
    avg = lambda rows, k: sum(num(r[k], 0) for r in rows) / len(rows) if rows else None

    print(f"PERIOD {rng[0]}..{rng[-1]} ({n}d) food-logged {len(fdays)} burn-logged {len(odays)}")
    if not fdays and not odays:
        print("no food/burn data in period")
        gym_stats(rng)
        return
    ai, ao, an = avg(fdays, "in"), avg(odays, "out"), avg(ndays, "net")
    print(f"AVG in {g(ai)} out {g(ao)} net {g(an)} | target in {g(pr.get('kcal_target'))} "
          f"net {g(pr.get('goal_net_kcal'))}")

    # previous period comparison
    prev = [(start - dt.timedelta(days=i)).isoformat() for i in range(1, n + 1)]
    pin = [daily[d] for d in prev if d in daily and num(daily[d].get("in"))]
    pnet = [daily[d] for d in prev if d in daily and daily[d].get("net") not in (None, "")]
    if pin:
        print(f"PREV {n}d avg in {g(avg(pin, 'in'))} net {g(avg(pnet, 'net'))}")

    if fdays:
        p, c, f = avg(fdays, "p"), avg(fdays, "c"), avg(fdays, "f")
        tot = p * 4 + c * 4 + f * 9
        print(f"MACRO avg P {g(p)}g({pct(p * 4, tot)}) C {g(c)}g({pct(c * 4, tot)}) "
              f"F {g(f)}g({pct(f * 9, tot)}) | P target {g(pr.get('protein_g'))}g")
        if pr.get("protein_g"):
            hit = sum(1 for r in fdays if num(r["p"], 0) >= pr["protein_g"])
            print(f"PROTEIN target hit {hit}/{len(fdays)} days")
        if pr.get("kcal_target"):
            over = [r["date"][5:] for r in fdays if num(r["in"], 0) > pr["kcal_target"] * 1.1]
            print(f"OVER target+10%: {len(over)} days {' '.join(over)}".rstrip())
        wk = [r for r in fdays if dt.date.fromisoformat(r["date"]).weekday() < 5]
        we = [r for r in fdays if dt.date.fromisoformat(r["date"]).weekday() >= 5]
        print(f"WEEKDAY/WEEKEND avg in {g(avg(wk, 'in'))} / {g(avg(we, 'in'))}")

    if ndays:
        best = min(ndays, key=lambda r: num(r["net"]))
        worst = max(ndays, key=lambda r: num(r["net"]))
        total_net = sum(num(r["net"], 0) for r in ndays)
        print(f"NET best {best['date'][5:]} {best['net']} worst {worst['date'][5:]} {worst['net']} "
              f"| sum {g(total_net)} = ~{g(total_net / 7700)} kg fat")

    # meal split + top foods from raw log
    logs = [r for r in all_logs() if rng[0] <= r["date"] <= rng[-1]]
    if logs:
        meal = Counter()
        food = Counter()
        foodp = Counter()
        for r in logs:
            meal[r["meal"]] += num(r["kcal"], 0)
            food[r["food"]] += num(r["kcal"], 0)
            foodp[r["food"]] += num(r["p"], 0)
        tot = sum(meal.values())
        print("MEALS " + " ".join(f"{m} {pct(meal[m], tot)}" for m in "BLDS"))
        print("TOP kcal " + ", ".join(f"{k} {g(v)}" for k, v in food.most_common(6)))
        print("TOP protein " + ", ".join(f"{k} {g(v)}g" for k, v in foodp.most_common(4)))

    act = [r for r in read(ACT) if rng[0] <= r["date"] <= rng[-1]]
    st = [num(r["steps"]) for r in act if num(r.get("steps"))]
    sl = [num(r["sleep_h"]) for r in act if num(r.get("sleep_h"))]
    wo = [r["date"][5:] + ":" + r["workout"] for r in act if r.get("workout")]
    if st or sl:
        print(f"STEPS avg {g(sum(st) / len(st)) if st else '-'} | SLEEP avg "
              f"{g(sum(sl) / len(sl)) if sl else '-'}h")
    if wo:
        print("WORKOUTS " + "; ".join(wo))
    ws = [(r["date"], num(r["weight"])) for r in read(ACT) if num(r.get("weight")) and r["date"] <= rng[-1]]
    inr = [w for w in ws if w[0] >= rng[0]]
    if inr:
        print(f"WEIGHT {g(inr[0][1])} -> {g(inr[-1][1])} ({g(inr[-1][1] - inr[0][1])}) "
              f"goal {g(pr.get('goal_weight'))}")
    miss_f = [d[5:] for d in rng if d not in {r['date'] for r in fdays}]
    miss_o = [d[5:] for d in rng if d not in {r['date'] for r in odays}]
    if miss_f or miss_o:
        print(f"MISSING food: {' '.join(miss_f) or '-'} | burn: {' '.join(miss_o) or '-'}")
    gym_stats(rng)
    if ai is not None and ai < 1200:
        print("FLAG avg intake < 1200 kcal")


# ---------- gym ----------
SPEC = re.compile(
    r"^(?P<key>.+?)\s+(?:"
    r"(?P<sets>\d+)\s*[x*]\s*(?P<reps>\d+)(?:\s*@\s*(?P<w>[\d.]+)\s*(?P<u>kg|lbs?)?)?"
    r"|(?P<min>[\d.]+)\s*(?:m|min|mins)"
    r")$", re.I)


def cmd_ex(args):
    if len(args) < 2 or args[1].lower() not in GROUPS:
        sys.exit(f"usage: ex KEY GROUP [w|bw|c]  GROUP = {'|'.join(GROUPS)}")
    key = norm_key(args[0])
    row = {"key": key, "group": args[1].lower(), "type": args[2] if len(args) > 2 else "w"}
    rows = [r for r in read(EXFILE) if r["key"] != key] + [row]
    rows.sort(key=lambda r: (r["group"], r["key"]))
    write(EXFILE, EX_H, rows)
    print(f"exercise {key} -> {row['group']} ({row['type']})")


def best_kg(rows):
    best = {}
    for r in rows:
        kg = num(r["kg"], 0)
        if kg > best.get(r["exercise"], 0):
            best[r["exercise"]] = kg
    return best


def cmd_gym(args):
    date = parse_date("today")
    if args and is_date(args[0]):
        date, args = parse_date(args[0]), args[1:]
    parts = [p.strip() for p in " ".join(args).replace(";", ",").split(",") if p.strip()]
    if not parts:
        sys.exit('usage: gym [DATE] "bench_press 4x8@60, pullup 3x10, treadmill 20m"')
    matches, bad = [], []
    for p in parts:
        m = SPEC.match(p)
        (matches if m else bad).append(m or p)
    if bad:
        print("CANNOT PARSE: " + " | ".join(bad))
        print("format: KEY SETSxREPS[@KG|@LBS] or KEY MINUTESm  (nothing was logged)")
        sys.exit(1)
    exm = {r["key"]: r for r in read(EXFILE)}
    unknown = sorted({norm_key(m["key"]) for m in matches} - set(exm))
    if unknown:
        print("UNKNOWN: " + ", ".join(unknown))
        print(f"add each: fit.py ex KEY {'|'.join(GROUPS)} [w|bw|c]  (nothing was logged)")
        sys.exit(1)
    prev = best_kg(all_gym())
    rows = []
    for m in matches:
        k = norm_key(m["key"])
        row = {"date": date, "exercise": k, "group": exm[k]["group"], "sets": "", "reps": "",
               "kg": "", "min": "", "vol": "0"}
        if m["min"]:
            row["min"] = g(num(m["min"]))
        else:
            sets, reps, kg = int(m["sets"]), int(m["reps"]), num(m["w"], 0)
            if (m["u"] or "").lower().startswith("lb"):
                kg *= 0.45359237
            row.update(sets=str(sets), reps=str(reps), kg=g(kg) if kg else "", vol=g(sets * reps * kg))
        rows.append(row)
    append(gym_path(date), GYM_H, rows)
    rollup(quiet=True)
    day = [r for r in read(gym_path(date)) if r["date"] == date]
    sets = sum(num(r["sets"], 0) for r in day)
    vol = sum(num(r["vol"], 0) for r in day)
    mins = sum(num(r["min"], 0) for r in day)
    groups = sorted({r["group"] for r in day})
    prs = [f"{r['exercise']} {r['kg']}kg" for r in rows
           if num(r["kg"], 0) > prev.get(r["exercise"], 0) and r["exercise"] in prev]
    s = f"gym {date}: {g(sets)} sets, vol {g(vol)} kg"
    if mins:
        s += f", cardio {g(mins)} min"
    s += " | " + ", ".join(groups)
    if prs:
        s += " | PR " + ", ".join(prs)
    print(s)


def cmd_gymday(args):
    date = parse_date(args[0] if args else "today")
    day = [r for r in read(gym_path(date)) if r["date"] == date]
    if not day:
        print(f"{date}: no workout")
        return
    for r in day:
        print(f"{r['exercise']} {r['min'] + 'm' if r['min'] else r['sets'] + 'x' + r['reps']}"
              + (f"@{r['kg']}" if r["kg"] else ""))


def cmd_gdel(args):
    if len(args) < 2:
        sys.exit("usage: gdel DATE KEY  (removes the last entry of KEY on DATE)")
    date, key = parse_date(args[0]), norm_key(args[1])
    path = gym_path(date)
    rows = read(path)
    for i in range(len(rows) - 1, -1, -1):
        if rows[i]["date"] == date and rows[i]["exercise"] == key:
            del rows[i]
            write(path, GYM_H, rows)
            rollup(quiet=True)
            print(f"removed {key} on {date}")
            return
    print("not found")


def cmd_prs(_):
    best = {}
    for r in all_gym():
        kg, reps = num(r["kg"], 0), num(r["reps"], 0)
        if not kg:
            continue
        e1rm = kg * (1 + reps / 30)
        b = best.get(r["exercise"])
        if not b or e1rm > b[1]:
            best[r["exercise"]] = (kg, e1rm, reps, r["date"])
    if not best:
        print("no weighted lifts yet")
    for k, (kg, e1rm, reps, d) in sorted(best.items(), key=lambda x: -x[1][1])[:15]:
        print(f"{k}: {g(kg)}kg x{g(reps)} (e1RM {g(e1rm)}) {d}")


def gym_stats(rng):
    rows = [r for r in all_gym() if rng[0] <= r["date"] <= rng[-1]]
    n = len(rng)
    start = dt.date.fromisoformat(rng[0])
    prev_rng = ((start - dt.timedelta(days=n)).isoformat(), (start - dt.timedelta(days=1)).isoformat())
    prev = [r for r in all_gym() if prev_rng[0] <= r["date"] <= prev_rng[1]]
    if not rows and not prev:
        print("GYM no workouts logged")
        return
    vol = sum(num(r["vol"], 0) for r in rows)
    pvol = sum(num(r["vol"], 0) for r in prev)
    mins = sum(num(r["min"], 0) for r in rows)
    sessions = len({r["date"] for r in rows})
    print(f"GYM sessions {sessions}/{n}d (prev {len({r['date'] for r in prev})}) | sets "
          f"{g(sum(num(r['sets'], 0) for r in rows))} | vol {g(vol)} kg (prev {g(pvol)}) | cardio {g(mins)} min")
    gs = Counter()
    for r in rows:
        gs[r["group"]] += num(r["sets"], 0) or (1 if r["min"] else 0)
    missed = [x for x in GROUPS[:6] if not gs[x]]
    print("GYM sets/group " + ", ".join(f"{k} {g(v)}" for k, v in gs.most_common())
          + (f" | not trained: {' '.join(missed)}" if missed else ""))
    before = best_kg([r for r in all_gym() if r["date"] < rng[0]])
    prs = {}
    for r in rows:
        kg = num(r["kg"], 0)
        if kg > before.get(r["exercise"], 0) and r["exercise"] in before and kg > prs.get(r["exercise"], 0):
            prs[r["exercise"]] = kg
    if prs:
        print("GYM PRs " + ", ".join(f"{k} {g(v)}kg" for k, v in prs.items()))


def cmd_help(_):
    print(__doc__)
    print("commands: find food add del act zepp day stats rollup | gym ex gymday gdel prs  (see CLAUDE.md)")


CMDS = {"find": cmd_find, "food": cmd_food, "add": cmd_add, "del": cmd_del, "act": cmd_act,
        "zepp": cmd_zepp, "day": cmd_day, "stats": cmd_stats,
        "gym": cmd_gym, "ex": cmd_ex, "gymday": cmd_gymday, "gdel": cmd_gdel, "prs": cmd_prs,
        "rollup": lambda a: rollup(), "help": cmd_help}

if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2 or sys.argv[1] not in CMDS:
        cmd_help(None)
        sys.exit(1)
    CMDS[sys.argv[1]](sys.argv[2:])
