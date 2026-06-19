# Job Radar MVP

This is a local-first MVP for a Japan-focused job radar based on the user's resume/profile.

## What It Does

- Prioritizes Salesforce, CRM, PM/PL, presales, implementation consultant, and customer success roles.
- Excludes engineer/developer/admin-first job titles by default, including Japanese title variants such as `エンジニア`, `開発リーダー`, `アドミン`, `管理者`, and `社内SE`.
- Uses paginated LinkedIn public search as the first discovery source.
- Also runs conservative official Careers scanning for the 150-company watchlist.
- Tracks a curated official Careers watchlist for 150 target companies.
- Filters for companies with an expected employee scale of 1,000+, with a 500+ exception for AI/mega-venture targets.
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

Company Scale:

- Jobs from target companies are allowed when the target company is marked `minEmployees: 1000`, or `minEmployees: 500` for AI/mega-venture targets.
- Non-target jobs are allowed only when the job text contains a strong large-company signal such as Fortune/Global 500 or an explicit 1,000+ employee phrase.
- Smaller or unverified company-scale jobs are filtered out before scoring.

## Update Model

True real-time updates are not necessary for job postings and are more likely to trigger rate limits. The intended model is:

- LinkedIn discovery: every 3 hours, with Salesforce/CRM plus AI query sets across multiple pages.
- Official Careers watchlist: every 3 hours for the highest-priority companies, using conservative keyword link scanning.
- Immediate notification only when a new high-fit posting appears or a recommended posting disappears.

The generic official-page scanner is conservative because many official Careers sites mix job pages with product, event, and help content. Promote official postings into the main feed only when the link text and target-company keywords look like a job page.

## OpenWork

The UI includes Google search links for `company + OpenWork 評判` and a display slot for company ratings. Ratings are not scraped automatically because OpenWork can require CAPTCHA/login and restricts mechanical access and reuse of rating data; add manual or licensed rating data to `openWorkRating` when available.

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
python .\scripts\collect_jobs.py --replace --linkedin-queries 26 --linkedin-pages 3 --linkedin-megaventure-companies 30 --linkedin-detail-limit 64 --official-companies 30
```

Try official scanning for the first few target companies:

```powershell
python .\scripts\collect_jobs.py --official-companies 3 --no-linkedin
```
