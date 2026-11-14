# Fitness Agent

Personal calorie tracker run through Claude chat. Data lives as CSV in this repo;
`index.html` is the dashboard. Rules for Claude are in `CLAUDE.md`.

## Setup
1. Edit `profile.json` with your own targets (kcal, protein, BMR, goal weight, diet).
2. Install Git for Windows, then:
   ```
   git init -b main
   git add -A
   git commit -m "init"
   git remote add origin https://github.com/<you>/fitness-agent.git
   git push -u origin main
   ```
3. Dashboard: GitHub repo → Settings → Pages → Deploy from branch `main`, folder `/ (root)`.
   Free GitHub Pages needs a **public** repo, which makes your food log public.
   To keep it private, keep the repo private and run it locally:
   `python -m http.server 8000` → http://localhost:8000

## Daily use (in Claude Code, opened in this folder)
`b: 3 idli, sambar, coffee` · `l: ...` · `d: ...` · `s: ...` · `burn a520 s9800` · `w 72.4`
· `today` · `week` · `suggest` · `review`
