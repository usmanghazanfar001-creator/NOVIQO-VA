# Deploying NOVIQO

One server (a small VPS is enough), Docker with the Compose plugin (images use Python 3.14 and Node 22), and a domain name pointing at it.

## 1. Configure
```bash
cp .env.example .env
```
Edit `.env` (this single file is used by Compose **and** the backend):
- `DOMAIN` – your domain (DNS A/AAAA record must already point at the server; ports 80 and 443 open)
- `POSTGRES_PASSWORD` – a long random password
- `SECRET_KEY` – `python3 -c "import secrets; print(secrets.token_hex(32))"`. **Keep it stable**: changing it logs everyone out and disconnects Google Calendar.
- `LLM_PROVIDER`, `LLM_MODEL`, and the matching API key
- Optional: `TAVILY_API_KEY` (web search), `SMTP_*` (email, reminder emails, password reset), `GOOGLE_*` (calendar; set `GOOGLE_REDIRECT_URI=https://YOUR_DOMAIN/api/calendar/callback`), `SENTRY_DSN`, `METRICS_TOKEN`

## 2. Start
```bash
docker compose up -d --build
docker compose ps            # db, backend, web should be healthy/running
curl -s https://YOUR_DOMAIN/api/ready      # {"ok":true}
```
Caddy obtains the HTTPS certificate on first request. In production mode the backend **refuses to start** if `SECRET_KEY` is weak, `COOKIE_SECURE` isn't true, the database isn't PostgreSQL, or the DB password is the default; `docker compose logs backend` tells you which.
Tables are created on first start. API docs (`/docs`) are disabled in production.

## 3. Operate
| Task | Command |
|---|---|
| Logs (JSON, one line per request) | `docker compose logs -f backend` |
| Update | `git pull && docker compose up -d --build` |
| Back up | `docker compose exec -T db pg_dump -U noviqo noviqo \| gzip > backup-$(date +%F).sql.gz` |
| Restore | `gunzip -c backup.sql.gz \| docker compose exec -T db psql -U noviqo noviqo` |
| Stop | `docker compose down` (data survives; add `-v` to **delete** it) |

Schedule the backup with cron and copy it off the server. Test a restore at least once.

## 4. Monitoring
- **Liveness / readiness:** `/api/health`, `/api/ready` (readiness checks the database). The backend container has a Docker healthcheck.
- **Metrics:** set `METRICS_TOKEN`, then scrape `http://backend:8000/metrics` from inside the Compose network with `Authorization: Bearer <token>` (Caddy does not expose `/metrics` publicly). Series: `http_requests_total`, `http_request_seconds`, `tool_calls_total{tool,outcome}`. Useful alerts: 5xx rate, p95 latency, `/api/ready` failing, `tool_calls_total{outcome="error"}` spikes.
- **Errors:** set `SENTRY_DSN`; cookies, headers, bodies and query strings are removed before sending.
- **Logs** hold method, route template, status and timing, never query strings, message text or tokens. Request ids appear in the `X-Request-ID` response header and in every log line, so a user's error report can be traced.

## 5. Scaling and known limits
- The backend runs **one worker** deliberately. The reminder emailer would send duplicates with several, and rate-limit counters are per process. To scale out, move rate limiting to Redis (slowapi supports it) and run the reminder mailer as its own single process.
- Sessions are stateless JWTs: logout clears the cookie but cannot revoke a copied one (7-day lifetime).
- There is no migration tool yet. `create_all` only creates missing tables. Add Alembic before changing the schema in production.
- `FORWARDED_ALLOW_IPS=*` is safe only while the backend is not published; do not add a `ports:` entry to it.

## 6. Security checklist
- [ ] `.env` is not committed and has mode 600
- [ ] Firewall allows only 22, 80, 443 (the database listens on 127.0.0.1 only)
- [ ] Strong `POSTGRES_PASSWORD` and `SECRET_KEY`
- [ ] Backups run and a restore has been tested
- [ ] OS and Docker images updated regularly (`docker compose pull && docker compose up -d --build`)
