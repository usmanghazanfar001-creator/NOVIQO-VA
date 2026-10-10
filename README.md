# NOVIQO — Stage 1 (MVP)
Speak → Speech-to-Text → LLM → Text-to-Speech, with a text fallback.

## Run locally

**Windows (easiest):** install Python from python.org (tick "Add python.exe to PATH") and Node.js LTS, extract this folder to a short local path such as `C:\noviqo`, double-click `setup.bat`, put your API key in `backend\.env`, then double-click `start.bat`. Open http://localhost:5173 in Chrome or Edge.

**Windows (by hand):** type the lines exactly, with nothing after them. Command Prompt does not support `#` comments.

First time only, in the project folder:
```
py -3 -m venv .venv
.venv\Scripts\activate
pip install -r backend\requirements.txt
copy .env.example backend\.env
```
Then delete the `DATABASE_URL=` line in `backend\.env` (a local SQLite file is used) and add your API key. Window 1:
```
cd /d "C:\noviqo"
.venv\Scripts\activate
cd backend
uvicorn app.main:app --reload
```
Window 2:
```
cd /d "C:\noviqo\frontend"
npm install
npm run dev
```

**macOS / Linux:**
```
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example backend/.env
cd backend && uvicorn app.main:app --reload
```
and in a second terminal: `cd frontend && npm install && npm run dev`. PostgreSQL is optional locally (`docker compose up -d db`, then keep `DATABASE_URL` in `.env`).

Voice input uses the browser Speech API (Chrome/Edge/Safari). Tests: `pytest tests` from the project root (set `PYTHONPATH=.`).

## How it works
- `frontend/src/services/speech.ts` — `SpeechProvider` / `TTSProvider` interfaces; browser implementations. Add cloud providers by implementing the same interface.
- `backend/app/ai/llm.py` — `LLMProvider` abstraction (Anthropic, OpenAI). Chosen via `LLM_PROVIDER` / `LLM_MODEL`. Keys stay server-side; errors are mapped to safe messages.
- `backend/app/main.py` — `/api/chat` with validation, CORS, rate limiting (30/min/IP). The client sends the last 20 messages, which is the short-term memory.
- `Orb.tsx` + `index.css` — the orb and its five states.

## Next stages
2 tools (calculator, time, weather, search, notes, timer) → 3 memory/history → 4 agent routing (tool-calling loop in `app/agents/`) → 5 auth + PostgreSQL → 6 automation → 7 production.

## Stage 2 — Tools
`backend/app/agents/agent.py` runs a tool-calling loop (max 4 rounds): the model decides whether a tool is needed, `execute()` runs it with a 12 s timeout, results go back to the model. Tools live in `backend/app/tools/builtin.py` and register with `@tool(...)`; add one by writing a function.
Tools: calculate (safe AST, linear equations), get_datetime, days_until, convert_units, set_timer, create/list/delete_note, get_weather (Open-Meteo, no key), search_web (needs `TAVILY_API_KEY`).
Timers run in the browser: the server returns an `action`, the UI counts down and speaks when done.
Limits until Stage 5: notes are in server memory (lost on restart, shared by all users); timers vanish on page reload.

## Stage 3 — History & memory
- **Short-term context:** the last 20 messages of the active conversation go to the model, so pronouns resolve.
- **History:** the History drawer lists conversations (title, date, voice/text), with new, search (titles and message text), rename and delete. Stored in browser `localStorage` until Stage 5 moves it to PostgreSQL.
- **Long-term memory:** only when you say e.g. "remember that I prefer metric units" does the model call `remember`; the fact appears in the Memory tab, where you can delete one, delete all, or switch the feature off (which also withholds the tool). Saved facts are sent with each request and put in the system prompt as data, never instructions (max 20 facts, 200 chars each).

## Stage 4 — Agent & permissions
- **Intent detection / routing:** the model picks tools from their descriptions; no separate classifier. Chains (search → note) run in the same loop (max 6 rounds).
- **Permission-based tools:** `@tool(..., confirm=fn)` marks a tool as needing approval. The agent never runs it directly: it returns a signed, 5-minute, single-use token (`core/security.py`) plus a plain-language summary. The UI shows Confirm / Cancel; Confirm calls `POST /api/confirm`, which verifies the token and only then runs the tool. The client cannot alter or forge a call. `confirm` may raise `ValueError` to reject bad input before asking (e.g. `javascript:` URLs).
- **Gated today:** `open_url` (new, opens a site in a new tab) and `delete_note`. Future computer tools (open apps, files, browser control) should use the same hook.
- Set `SECRET_KEY` in production; without it a random key is generated per process, so tokens die on restart and don't work across workers.

## Stage 5 (part 1) — Database, auth, per-user data (backend)
**The Stage 4 frontend does not work against this backend yet** (login is required and `/api/chat` now takes one `message` plus an optional `conversation_id`). Part 2 adds the login screens and moves history/memory off local storage.

- **Schema:** `docs/schema.sql` (generated: `python -m app.database.schema`). Tables: users, conversations, messages, notes, memories, user_settings, password_resets. Tables are created on startup; add Alembic once the schema changes.
- **Auth:** argon2 password hashes; 7-day JWT in an httpOnly, SameSite=Lax cookie (set `COOKIE_SECURE=true` behind HTTPS). Sessions are stateless, so logout clears the cookie but doesn't revoke an already-copied one. Login/signup/reset are rate limited. Password reset stores only a hash of a 1-hour, single-use token; until Stage 6 (email) the link is **logged by the server**, never returned in a response.
- **Isolation:** every query filters by the authenticated user; other users' ids return 404. Notes and memories (including the `create_note`, `delete_note`, `remember` tools) are per user. Confirmation tokens are bound to the user they were issued to.
- **Chat:** the server loads the last 20 messages of the conversation, applies the user's memory setting, runs the agent, and saves both messages only if it succeeds.

| Endpoint | Purpose |
|---|---|
| `POST /api/auth/signup \| login \| logout \| forgot \| reset` | account lifecycle |
| `GET/PATCH /api/auth/me` | profile |
| `POST /api/chat`, `POST /api/confirm` | agent chat; approve a gated action |
| `GET/POST /api/conversations`, `GET/PATCH/DELETE /api/conversations/{id}` | history (`?q=` searches titles and messages) |
| `GET/POST /api/notes`, `DELETE /api/notes/{id}` | notes |
| `GET/POST/DELETE /api/memories`, `DELETE /api/memories/{id}` | long-term memory |
| `GET/PUT /api/settings` | memory, auto-speak, speed, voice, theme |
| `DELETE /api/me/data`, `POST /api/me/delete` | delete all data; delete account (needs password) |

Interactive docs: `http://localhost:8000/docs`.

## Stage 5 (part 2) — Frontend: accounts, synced history, settings
The frontend now talks to the authenticated API; nothing is stored in the browser any more (the Stage 3 `localStorage` history was not migrated).
- `AuthPage` — log in, sign up, forgot password, and the reset screen (opened from the `?token=` link). A 401 anywhere returns you to log in.
- `Sidebar` — conversations from the API (server-side search of titles and message text, rename, delete, voice/text tag) and the Memory tab (list, delete, delete all, on/off).
- `SettingsPanel` — voice and speed, auto-speak, theme (dark / light / system), long-term memory, delete all data, name, log out, delete account (asks for your password). Settings are saved per user.
- Not exposed: AI provider/model/temperature (admin-set via `.env` by design) and microphone selection (browsers don't let speech recognition pick a device).
Run: backend `uvicorn app.main:app --reload` and frontend `npm run dev` (Vite proxies `/api`, so the session cookie is same-origin).

## Stage 6 (part 1) — Reminders & email
- **Reminders:** "Remind me to study at 8 PM" calls `set_reminder`. The model is told the user's current date/time and timezone on every request, so it can resolve "tomorrow at 10 AM". Past times and anything over a year ahead are rejected; 50 pending max. While the app is open it polls `GET /api/reminders/due` every 30 s: due reminders are shown, spoken, and (if allowed in Settings) sent as a desktop notification. Upcoming reminders can be viewed and cancelled in Settings; `cancel_reminder` by voice asks for confirmation.
- **Email (SMTP, STARTTLS on 587):** set `SMTP_*` in `.env`. Used for password-reset links, for the `email_me` tool, and to email reminders that came due while you weren't in the app (a background task checks every 30 s; it only starts when SMTP is configured). Without SMTP, emails are logged by the server and overdue reminders wait until you next open the app.
- **`email_me` only ever sends to your own account address**, ignores any other recipient the model supplies, and needs on-screen confirmation, which limits what a prompt injection (for example from a web page the agent read) can do.
- Run the reminder mailer in **one** worker only; with several, duplicates are possible.
- Still to do in Stage 6: calendar integration, browser tools, scheduled workflows.

## Stage 6 (part 2) — Google Calendar
- **Setup:** in Google Cloud Console enable the Calendar API, create an OAuth *Web application* client, add `GOOGLE_REDIRECT_URI` (default `http://localhost:5173/api/calendar/callback`) as an authorised redirect URI, and set `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`. Without them the calendar tools are hidden from the model and the Settings section doesn't appear. While the OAuth app is in "Testing" mode, add your Google account as a test user.
- **Connect:** Settings → Calendar → *Connect Google Calendar*. Scope is `calendar.events` only. The OAuth `state` is a signed, single-use token bound to the logged-in user. Refresh tokens are stored **encrypted** (key derived from `SECRET_KEY` — keep it stable, or users must reconnect). Disconnecting, "Delete all my data" and "Delete account" all revoke Google's grant.
- **Tools:** `calendar_list` (what's on this week?) returns only title, time and location, truncated, so invite descriptions can't carry instructions to the model; the system prompt also says tool results are data, never instructions. `calendar_add` needs on-screen confirmation and has no attendees field, so it can't send invitations to other people.
- Not verified against Google's live servers (tests replace the network layer).

## Stage 7 — Production
`docker compose up -d --build` runs PostgreSQL, the backend (non-root, healthchecked) and Caddy (automatic HTTPS, security headers, serves the app, proxies `/api`). Details, backups, monitoring and the security checklist: **`docs/DEPLOYMENT.md`**. How the pieces fit together: **`docs/ARCHITECTURE.md`**.
- Backend: JSON logs with request ids (no query strings or user content), `/api/health` + `/api/ready`, Prometheus `/metrics` (token-protected, internal only), optional Sentry with scrubbing, security headers, docs disabled in production, fail-fast on unsafe settings.
- CI (`.github/workflows/ci.yml`) runs the backend tests and the frontend build.
- Not verified here: the Docker images and Compose stack were not built or run (no Docker in the build environment).

## Python versions
Tested on **Python 3.12, 3.13 and 3.14** (3.14.4), with the newest releases of every dependency (FastAPI 0.142, Starlette 1.x, SQLAlchemy 2.1, Pydantic 2.13). `backend/requirements.txt` lists minimum versions only, so pip picks releases that have prebuilt wheels for your Python; `backend/requirements.lock` is the exact set tested on 3.14 and is what the Docker image installs. Binary wheels for all dependencies exist on Windows, Linux and macOS for 3.14, so no C compiler is needed.
Known warning: `slowapi` calls `asyncio.iscoroutinefunction`, which Python 3.16 removes; it is harmless today, but watch for a slowapi update before moving to 3.16.

**Windows:** install Python (python.org, tick "Add python.exe to PATH") and Node.js LTS, extract the zip to a short path such as `C:\noviqo` (not inside OneDrive), then double-click `setup.bat`, edit `backend\.env` (API key), and double-click `start.bat`. `test.bat` runs the tests.

## PC control by voice (local use only)
Say things like "open Notepad", "create a file called todo.txt with buy milk", "what files do I have?", "open YouTube".
- **Switches (in `backend\.env`):** `ENABLE_COMPUTER_TOOLS=true` allows opening apps from a fixed list and listing/reading/creating text files **inside one folder** (`WORKSPACE_DIR`, default `<your user folder>\NOVIQO`). `ENABLE_COMMANDS=true` additionally allows shell commands and is **off by default**. Both are refused in production because they act on the machine running the server.
- **Confirmation:** every action that changes something shows a card with the exact thing it will do. Low-risk ones (open an app, open a website) can be approved by saying "yes" or "no" (the app listens again after asking). Creating files and running commands need a mouse click, so background noise or a misheard word can't trigger them.
- **Limits you should know:** the file area is confined (no `..`, drive letters, symlink escapes, or script/executable extensions). The command filter blocks obviously destructive patterns but is a speed bump, not a sandbox: read each command before confirming, especially if the assistant has just read a web page or file. Opening apps works on Windows only. There is no "Hey NOVIQO" wake word; click the orb to start.

## Voice: streaming and natural speech
- **Streaming:** `POST /api/chat/stream` sends the reply as server-sent events (`delta`, `reset` when a tool round starts, then `done` or `error`). Both providers stream (Anthropic and OpenAI event parsers are unit-tested with recorded event sequences); a provider that can't stream falls back to one chunk. Messages are saved only when the reply completes, so a failed or abandoned reply leaves nothing half-saved. Confirmations, memory, tools and permissions behave exactly as before.
- **Speaks while it writes:** for voice questions the browser speaks each sentence as soon as it is complete (it keeps "3.14" and "Dr. Smith" together) instead of waiting for the whole reply. Clicking the orb while it talks stops both speech and any further speech from the same reply. Markdown symbols and links are not read aloud.
- **Natural voice:** with Settings → Voice on *Best available*, the browser's most natural voice for your language is chosen (Edge's "Natural"/"Online" neural voices are by far the best on Windows; Chrome's Google voices come second). You can still pick any voice by name.
- Not built: cloud text-to-speech (for example a paid neural-voice API) behind the `TTSProvider` interface, and an always-listening wake word.
"# NOVIQO-VA" 
