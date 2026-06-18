# Deploy Job Radar

Recommended setup: GitHub Pages with GitHub Actions.

This gives you:

- A public URL you can open without Codex.
- A scheduled refresh every 3 hours.
- Manual refresh from the GitHub Actions tab.

## GitHub Pages

1. Create a new GitHub repository, for example `job-radar`.
2. Upload the contents of this `job-radar` folder as the repository root.
3. In GitHub, open `Settings -> Pages`.
4. Set `Build and deployment` to `GitHub Actions`.
5. Open `Actions -> Deploy Job Radar -> Run workflow`.
6. After the workflow finishes, open the Pages URL shown in the deployment summary.

The workflow refreshes LinkedIn job data with:

```bash
python scripts/collect_jobs.py --replace --linkedin-queries 5 --linkedin-detail-limit 24 --no-official
```

Official Careers are kept as a watchlist until company-specific ATS adapters are added. This avoids mixing product/event/help pages into the actual job feed.

## Vercel or Netlify

You can also deploy this folder as a static site. Vercel and Netlify will serve the dashboard, but scheduled job refresh needs an additional cron/serverless setup. Without that, the dashboard will show the last bundled `data/jobs.js`.

## Privacy

The dashboard contains resume-derived profile signals and target job preferences. Use a private repository if you do not want the source files public. GitHub Pages for private repositories depends on your GitHub plan and repository settings.
