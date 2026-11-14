# Fitness Agent — Calorie Tracker

I log food + Zepp (Amazfit) burn data through chat. You store it as CSV in this
GitHub repo, analyse it, and give suggestions. The website (`index.html`) renders
charts directly from the CSVs — you never produce charts or HTML for daily use.

## Token rules (most important)
1. **Never read raw data files** (`data/log/*.csv`, `data/foods.csv`, `data/daily.csv`).
   Use `python scripts/fit.py ...` — it prints compact output. Read files only to debug.
2. **Don't do arithmetic yourself.** The script calculates kcal, macros, totals, averages.
3. **Replies after logging: max 2 lines** (the script's summary line + optional 1 tip).
   No tables, no restating what I ate, no motivational filler.
4. Batch: one `add` call per meal, one `act` call per day, one commit per session.
5. Don't touch `index.html` or `scripts/` unless I ask.

## Files
| Path | What | Who writes |
|---|---|---|
| `profile.json` | targets (kcal, protein, BMR, goal, diet) | me / you on request |
| `data/foods.csv` | food dictionary: `key,serving,kcal,p,c,f,src` per 1 serving | `fit.py food` |
| `data/log/YYYY-MM.csv` | every item eaten: `date,meal,food,qty,kcal,p,c,f` | `fit.py add` |
| `data/activity.csv` | one row/day: `date,total,active,steps,sleep_h,rhr,weight,workout` | `fit.py act` / `zepp` |
| `data/exercises.csv` | exercise dictionary: `key,group,type` (type w/bw/c) | `fit.py ex` |
| `data/gym/YYYY-MM.csv` | every exercise done: `date,exercise,group,sets,reps,kg,min,vol` | `fit.py gym` |
| `data/daily.csv` | generated rollup: `date,in,out,net,p,c,f,steps,weight,gym_sets,gym_vol,gym_min` | `fit.py rollup` (auto) |
| `insights/latest.md` | latest review + suggestions, shown on website | you (`review`) |

Git history is the archive. Never delete rows; correct with `del` then `add`.

## fit.py commands
```
fit.py find TERM                          # search food dictionary
fit.py food KEY "SERVING" KCAL P C F [src]  # add/update food (src: est|label|user)
fit.py add [DATE] MEAL "key:qty, key:qty"   # MEAL = B L D S ; qty = servings (default 1)
fit.py del DATE MEAL KEY                    # remove one logged item
fit.py act [DATE] total= active= steps= sleep= rhr= weight= workout="..."
fit.py zepp PATH                            # import Zepp export folder/CSV
fit.py day [DATE]                           # one day: items + totals vs target
fit.py stats [DAYS]                         # analytics summary (default 7)
fit.py rollup                               # rebuild daily.csv (add/act/zepp/gym do it automatically)
fit.py gym [DATE] "bench_press 4x8@60, pullup 3x10, squat 5x5@135lbs, treadmill 20m"
fit.py ex KEY GROUP [w|bw|c]                # add exercise; GROUP = chest back legs shoulders arms core cardio full
fit.py gymday [DATE]                        # one day's workout
fit.py gdel DATE KEY                        # remove last entry of KEY on DATE
fit.py prs                                  # best lift + estimated 1RM per exercise
```
Gym format: `KEY SETSxREPS@WEIGHT` (weight in kg; `lbs`/`lb` suffix is converted), bodyweight
moves omit `@`, cardio is `KEY MINUTESm`. Different weights per set → separate entries
(`bench_press 1x8@60, bench_press 2x6@70`). `stats` includes GYM lines automatically.
DATE = `YYYY-MM-DD`, `today`, `y` (yesterday) or `-N` (N days ago). Default today.

## Chat shorthand I'll use
| I type | You do |
|---|---|
| `b: 3 idli, sambar, coffee` (`b/l/d/s`) | log meal → `add` |
| `y b: ...` / `11-12 l: ...` | same, for yesterday / that date |
| `burn 2450` or `burn a520 s9800 sl7.2` | `act total=2450` / `active=520 steps=9800 sleep=7.2` |
| screenshot of Zepp | read numbers → `act` |
| `w 72.4` | `act weight=72.4` |
| `g: bench 4x8@60, pullups 3x10, treadmill 20m` | map names to keys → `gym` (unknown → `ex` first) |
| `y g: ...` | gym for yesterday |
| `prs` | `prs` → list as-is |
| `today` | `day` + `gymday` → 2-line verdict |
| `week` / `month` | `stats 7` / `stats 30` → analysis (≤8 bullets) |
| `review` | `stats 7` + `stats 28` → rewrite `insights/latest.md` → commit |
| `suggest` | next-meal suggestion that fits the remaining budget from `day` |
| `fix: ...` | `del` + `add` |

## Logging workflow
1. Map each item to a food key: lowercase, `_` for spaces (`chicken_biryani`).
   Prefer existing keys — `find` first if unsure.
2. Run `add`. If it prints `UNKNOWN`, add each with `food` (estimate typical
   home portion, `src=est`; use label values if I give them, `src=label`), then re-run `add`.
3. Quantities: `qty` is a multiple of the serving in foods.csv (e.g. serving "1 pc",
   3 idli → `idli:3`; serving "1 cup", half cup → `:0.5`). Ask only if the portion is truly unclear
   and >300 kcal is at stake; otherwise estimate and say "(est)".
4. Reply with the script's summary line. Commit at the end of the session.

## Burn data (Zepp)
- Zepp "Calories" on the home screen = **active** kcal. Total burn = BMR + active;
  if only active is given, `act` fills `total` from `profile.json` bmr.
- Bulk import: Zepp app → Profile → Settings → Account/Privacy → Export data →
  unzip into `imports/zepp/` → `fit.py zepp imports/zepp`. `imports/` is git-ignored.

## Analysis & suggestions
- Base everything on `stats` output. Compare to `profile.json` targets.
- Focus on: avg net vs goal deficit, protein adequacy, worst meal/time pattern,
  weekday vs weekend, top kcal foods (easiest swaps), consistency (missing days).
- Suggestions must be concrete and food-specific from foods I actually eat
  ("swap 2nd chapati for 100 g curd: -70 kcal, +4 g protein"), max 3.
- Gym: sessions/week, muscle groups not trained, volume trend vs previous period, PRs.
  Tie to nutrition: protein on training days, deficit too deep if volume/PRs drop.
- 7700 kcal ≈ 1 kg fat — the script already prints the estimate.
- Not medical advice; flag if avg intake < 1200 kcal or rapid weight loss > 1 kg/week.

## insights/latest.md format (website renders it; keep ≤ 20 lines)
```
# Week of YYYY-MM-DD
**Verdict:** one sentence.
## Numbers
- Avg in / out / net: ...
- Protein: ...
- Weight: ...
- Gym: sessions, volume, PRs
## What worked
- ...
## Fix next week (max 3)
- ...
```

## Git
- Session end: `git add -A && git commit -m "log YYYY-MM-DD" && git push`
  (PowerShell: use `;` instead of `&&`). Short messages: `log`, `food: +key`, `review W46`.
- Website: GitHub Pages from `main` branch, root folder. Local preview:
  `python -m http.server 8000` then open http://localhost:8000.
