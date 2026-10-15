# Production plan: 200 casinos, updated daily

(Draft — rewrite in your own words before submitting; the PDF asks for your own words.)

**Where it runs.** One small VPS (Hetzner CX32-class, ~€7/month, Ubuntu, Docker). 200 pages a day is a few minutes of work, so a single box beats Kubernetes or serverless: fewer moving parts, fixed price, and I can SSH in and debug it. The website stays static (the generated JSON/HTML), served by Caddy on the same box or Cloudflare Pages (free).

**Database.** PostgreSQL in Docker on the same VPS, with tables for `casinos`, `sources` (URL, robots/terms check date), `fetches` (hash, status) and `offers` (the three fields, status, model, timestamp). Storing history lets me see when an offer changed and skip pages whose content hash is unchanged, which also saves LLM cost. Backups: nightly `pg_dump` pushed to object storage (Backblaze B2 or Hetzner Storage Box), 14 days retained, plus VPS snapshots. I would test a restore once a month, because an untested backup is not a backup.

**Domain, DNS, HTTPS.** Domain from Cloudflare Registrar (~$10/year), DNS at Cloudflare. Caddy obtains and renews Let's Encrypt certificates automatically, HTTP redirects to HTTPS.

**Scheduling and failure detection.** A systemd timer (cron works too) runs the scraper daily at 04:00 and keeps last good data if a run fails. On success it pings Healthchecks.io; if no ping arrives, I get an email/Slack alert, which also catches the case where the server is down. The run also logs per-casino status and alerts if more than ~10% of casinos come back `failed`/`not_found`, or if wagering values change wildly versus yesterday.

**Rough monthly cost.** VPS ~€7, backup storage ~€1–2, domain ~$1, monitoring $0 (free tier), LLM ~$3 (200 casinos × 30 days, small model, ~1.5k tokens in / 300 out each). **Total ≈ $12–15/month.** Only permitted sources, honouring robots.txt and per-domain rate limits.
