# LinkedIn Auto Apply

A Python API and React dashboard for managing LinkedIn job applications. The project includes user authentication, CV processing with Ollama, application runs and logs, Playwright browser automation, and a Windows helper for connecting a local LinkedIn session.

## Desktop app required to connect LinkedIn

**The current LinkedIn connection flow requires the Auto Apply desktop helper on the user's computer. The web dashboard alone cannot connect or reconnect a LinkedIn account.** Windows installer/build scripts are provided; packaged macOS and Linux helpers are not included.

1. Install a helper built and configured for the same backend as the dashboard. This repository includes its source and packaging scripts, but does not include a downloadable installer. See [helper_app/README.md](helper_app/README.md).
2. Sign in to the dashboard on the Windows computer and select **Connect LinkedIn**. Allow the browser to open the installed helper through `linkedinautoapply://`.
3. Sign in to LinkedIn in the helper's local Chromium window and complete any verification. The helper uploads the captured browser session (`storage_state`) to the backend using a short-lived, one-time connection token. Your LinkedIn password is entered in LinkedIn's page, not in the dashboard.
4. Keep the dashboard open until it confirms the connection. The helper can then be closed: application runs execute in the backend Celery worker using the saved session. Use the helper again when a reconnect is needed.

The connection step cannot be completed from a phone. Once connected, the web dashboard can be used to manage settings and view runs without keeping the helper open. The backend, worker, database, and Redis must still be running. For a hosted deployment, configure the dashboard and helper to use the deployed backend; both currently default to `http://127.0.0.1:8000`.

## Project structure

- `app/` — FastAPI routes, SQLAlchemy models, application services, and Celery tasks.
- `alembic/` — Database migrations.
- `frontend/` — React, TypeScript, and Vite dashboard.
- `helper_app/` — Local session capture helper and Windows packaging scripts.
- `tests/` — Backend tests.
- `docker-compose.yml` — PostgreSQL, Redis, API, and worker services.

## Run locally

Prerequisites: Python 3.11, PostgreSQL, Redis, Node.js with npm, and an Ollama server for AI features.

From the project root, create and activate a Python environment. These commands use PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m playwright install chromium
Copy-Item .env.production.example .env
```

Edit `.env` before starting the backend:

- Replace `APP_SECRET_KEY` and all credential placeholders.
- Set `DATABASE_URL` to your local PostgreSQL database. The template's `db` hostname is for Docker.
- Set `REDIS_URL`, `CELERY_BROKER_URL`, and `CELERY_RESULT_BACKEND` to your local Redis server. Use the correct password, if configured; the template's `redis` hostname is for Docker.
- Set `OLLAMA_BASE_URL=http://localhost:11434` and install the model selected by `OLLAMA_MODEL` (default: `gemma3:4b`).
- Set `CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173` for the Vite dashboard. Adjust this if Vite uses another port.
- Set `BROWSER_HEADLESS=false` if you need a visible browser during local development.

Create the configured database, then run migrations and start the API:

```powershell
python -m alembic upgrade head
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

API documentation: <http://127.0.0.1:8000/docs>. Health endpoint: <http://127.0.0.1:8000/health>.

For background application runs, activate the same Python environment in another terminal and start a worker with Redis running:

```powershell
python -m celery -A app.workers.celery_app worker --loglevel=info --pool=solo
```

Start the frontend in another terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open the address printed by Vite (normally <http://localhost:5173>). The frontend currently calls `http://127.0.0.1:8000`, configured in `frontend/src/shared/api/client.ts`.

## Windows helper

`helper_app/` contains the required connection helper, a development protocol registration file, a PyInstaller specification, and a Windows Inno Setup installer script. See [helper setup and packaging instructions](helper_app/README.md). The registration file contains machine-specific paths and must be adjusted before use. The helper's backend address is configured in `helper_app/main.py`.

## Tests and frontend checks

With the backend environment configured:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest tests
```

The tests use a local SQLite file, `test_temp.db`. Frontend checks run from `frontend/`:

```powershell
npm run lint
npm run build
```

## Docker

See [DEPLOYMENT.md](DEPLOYMENT.md) for Docker configuration, environment files, and startup commands. The Compose stack exposes the API on port `8001`; adjust the frontend and helper API addresses when connecting to it.

Environment files containing credentials, browser sessions, local databases, logs, and generated dependencies should stay outside version control. `.env.production.example` provides a configuration template without real credentials.
