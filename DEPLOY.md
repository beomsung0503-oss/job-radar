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

The workflow refreshes LinkedIn plus conservative official Careers data with:

```bash
python scripts/collect_jobs.py --replace --linkedin-queries 16 --linkedin-pages 3 --linkedin-detail-limit 64 --official-companies 30
```

Official Careers scanning is intentionally conservative. It promotes links only when the link text and target-company keywords look like a job page, so it may miss JavaScript-only ATS pages.

## Vercel or Netlify

You can also deploy this folder as a static site. Vercel and Netlify will serve the dashboard, but scheduled job refresh needs an additional cron/serverless setup. Without that, the dashboard will show the last bundled `data/jobs.js`.

## Privacy

The dashboard contains resume-derived profile signals and target job preferences. Use a private repository if you do not want the source files public. GitHub Pages for private repositories depends on your GitHub plan and repository settings.
