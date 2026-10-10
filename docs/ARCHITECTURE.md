# How NOVIQO works

**Request path.** The browser captures speech (Web Speech API behind a `SpeechProvider` interface) and sends the text to `POST /api/chat`. The backend loads the last 20 messages of that conversation and the user's settings and memories, then runs the **agent loop**. The reply is saved and returned; the browser speaks it (`TTSProvider`).

| Component | Where | What it does |
|---|---|---|
| LLM providers | `backend/app/ai/llm.py` | `LLMProvider` abstraction (Anthropic, OpenAI) with native tool calling; chosen by env vars; errors mapped to safe messages |
| Agent | `backend/app/agents/agent.py` | Offers the tools to the model, runs the ones it picks (12 s timeout, up to 6 rounds), feeds results back. Tells the model the user's current time. Counts tool calls in metrics |
| Tools | `backend/app/tools/builtin.py` | Registered with `@tool(...)`: calculator, time/date, units, timer, notes, weather, web search, reminders, email-to-self, calendar, open link, remember |
| Permissions | `tools/base.py`, `core/security.py` | A tool with a `confirm` hook never runs straight from the model. The user gets a summary and Confirm/Cancel; approval is a server-signed, 5-minute, single-use token bound to that user |
| Memory | `api/chat.py`, `api/data.py` | Short-term: recent messages from the database. Long-term: facts saved only when the user asks, listable and deletable, switchable off, sent to the model as data |
| Auth & isolation | `core/auth.py`, `api/auth.py` | argon2 passwords, httpOnly session cookie, rate limits; every query is filtered by the logged-in user |
| Reminders & email | `services/` | Reminders are delivered in the open app (polling) or emailed if overdue; email goes through SMTP and `email_me` only ever targets the user's own address |
| Calendar | `services/gcal.py`, `api/calendar.py` | Google OAuth with encrypted refresh tokens; list events (title/time/place only), add events (confirmed, no invitations) |
| Observability | `core/observability.py` | JSON logs, request ids, Prometheus metrics, security headers, optional Sentry |
| Frontend | `frontend/src` | React + Tailwind: the Orb (5 states), chat, history drawer, settings, auth screens, confirmation cards |
| Edge | `frontend/Caddyfile` | HTTPS, security headers, serves the app, proxies `/api` |

**Safety principles.** Secrets stay on the server. Tools that touch the outside world ask first. Text from outside sources (web pages, calendar invites) is treated as data, not instructions. Logs avoid user content. Production mode refuses unsafe configuration.
