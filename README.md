# Job Radar MVP

This is a local-first MVP for a Japan-focused job radar based on the user's resume/profile.

## What It Does

- Prioritizes Salesforce, CRM, PM/PL, presales, implementation consultant, and customer success roles.
- Excludes engineer/developer/admin-first job titles by default, including Japanese title variants such as `エンジニア`, `開発リーダー`, `アドミン`, `管理者`, and `社内SE`.
- Uses LinkedIn as the first discovery source.
- Tracks a curated official Careers watchlist for 50 target companies.
- Shows a `공고` button only when a verified official job URL is available; otherwise the primary action opens LinkedIn.
- Presents recommendation, stretch, and backup buckets in a static dashboard.

## Scoring

The score is a 100-point fit model:

- Skills: 30
- Role direction: 25
- Experience fit: 20
- Salary fit: 10
- Location/language fit: 10
- Source quality: 5

Classification:

- Recommended: 66+ total, enough role and experience fit, Salesforce/CRM/Slack/etc. in the title, and a target-role title such as consultant, PM/PL, presales, customer success, implementation, or DX. Short title acronyms such as PM/PL are matched conservatively so they do not trigger on unrelated words like `Deployment`.
- Stretch: 55+ total or senior/high-requirement roles.
- Backup: lower relevance or unclear fit.

## Update Model

True real-time updates are not necessary for job postings and are more likely to trigger rate limits. The intended model is:

- LinkedIn discovery: every 3-6 hours.
- Official Careers watchlist: every 6-12 hours.
- Immediate notification only when a new high-fit posting appears or a recommended posting disappears.

The generic official-page scanner is conservative and disabled by default because many official Careers sites mix job pages with product, event, and help content. Promote official postings into the main feed after adding a company-specific ATS adapter or validating the page pattern.

## Files

- `index.html`: dashboard
- `app.js`: filtering and rendering
- `data/profile.js`: candidate profile and matching keywords
- `data/target_companies.js`: official Careers watchlist
- `data/jobs.js`: latest collected/seeded postings
- `scripts/collect_jobs.py`: collector for LinkedIn plus conservative official-page scanning

## Run

Open `index.html` in a browser. It uses JavaScript data files instead of JSON fetches, so it works directly from the filesystem.

## Deploy

See `DEPLOY.md`. The recommended path is GitHub Pages with the included GitHub Actions workflow, which refreshes LinkedIn data every 3 hours.

Refresh LinkedIn data, including salary extraction from the top detail pages:

```powershell
python .\scripts\collect_jobs.py --replace --linkedin-queries 5 --linkedin-detail-limit 24 --no-official
```

Try official scanning for the first few target companies:

```powershell
python .\scripts\collect_jobs.py --official-companies 3 --no-linkedin
```
