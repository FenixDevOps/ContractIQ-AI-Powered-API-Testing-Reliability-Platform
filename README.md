# ContractIQ

ContractIQ is a local-first foundation for an API testing and reliability platform. This repository contains **Stage 1 only**: a small FastAPI service, a React dashboard, and a real frontend-to-backend health check. It deliberately does not import OpenAPI documents, run API tests, store project data, or display made-up monitoring results.

## Stage 1 Features

- FastAPI project, health, and versioned status endpoints.
- Interactive API documentation at `/docs`.
- Configurable backend CORS and application metadata.
- Responsive React dashboard with Overview, API Projects, API Testing, Breaking Changes, Performance Monitoring, and Settings navigation.
- The dashboard calls the backend `/health` endpoint and presents loading, connected, disconnected, and retry states.
- API import and later-stage views are clearly identified as not yet implemented.
- Pytest coverage for the endpoints and local frontend CORS policy.

## Technology

- **Python 3.11 or 3.12 / FastAPI:** typed HTTP API with generated OpenAPI docs and an ASGI server.
- **Pytest / HTTPX:** tests API responses and browser-style HTTP requests without needing to start a server.
- **JavaScript / React:** reusable, interactive dashboard interface.
- **Vite:** local development server and production bundler for the frontend.
- **Fetch API:** native browser HTTP client; no additional HTTP library is required.
- **Lucide React:** open-source interface icons.

## Project Structure

```text
ContractIQ/
├── backend/
│   ├── app/
│   │   ├── __init__.py          # Backend package marker
│   │   ├── config.py            # Environment-driven settings
│   │   ├── main.py              # FastAPI app, CORS, root route, router registration
│   │   └── routes/
│   │       ├── __init__.py      # Routes package marker
│   │       └── health.py        # Health and versioned status routes
│   ├── tests/
│   │   └── test_health.py       # Endpoint and CORS tests
│   ├── .env.example             # Example backend environment settings
│   └── requirements.txt         # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── components/          # Navigation and backend status components
│   │   ├── pages/               # Overview and future-stage placeholder views
│   │   ├── services/api.js      # Shared backend health request
│   │   ├── App.jsx              # App shell, navigation state, and import notice
│   │   ├── App.css              # Responsive dashboard styling
│   │   └── main.jsx             # React browser entry point
│   ├── .env                     # Local Vite API URL (ignored by Git)
│   ├── .env.example             # Example Vite API URL
│   ├── index.html               # Vite HTML entry point
│   ├── package.json             # Scripts and JavaScript dependencies
│   └── vite.config.js           # Vite React plugin configuration
├── docs/
│   └── architecture.md          # Frontend/backend request and configuration flow
├── .gitignore                   # Excludes generated and local-only files
└── README.md
```

## Requirements

- Windows 11 with Python 3.11 or 3.12 and Node.js 18 or later.
- PowerShell and a terminal in VS Code.
- No paid services, API keys, or external database are needed.

## Setup

Run these commands from the repository root in PowerShell. A virtual environment keeps Python dependencies isolated from other projects.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt
if (-not (Test-Path backend\.env)) { Copy-Item backend\.env.example backend\.env }
```

If PowerShell blocks activation, allow it for the current terminal session with `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, then activate the environment again.

## Start the Backend

In a PowerShell terminal from the repository root:

```powershell
Set-Location backend
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --env-file .env
```

The server reads `CONTRACTIQ_APP_NAME`, `CONTRACTIQ_APP_VERSION`, and `CONTRACTIQ_ALLOWED_ORIGINS` from the backend environment file. If you do not use the example file, the same values can be set as PowerShell environment variables before starting Uvicorn.

## Start the Frontend

Open a second PowerShell terminal from the repository root:

```powershell
Set-Location frontend
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
npm install
npm run dev
```

Vite reads `VITE_API_BASE_URL` when it starts. Restart Vite after changing the value in `frontend/.env`. The supplied value points to `http://127.0.0.1:8000`.

## Local URLs

- Dashboard: <http://127.0.0.1:5173>
- Backend root: <http://127.0.0.1:8000/>
- Backend health: <http://127.0.0.1:8000/health>
- Versioned status: <http://127.0.0.1:8000/api/v1/status>
- Swagger UI: <http://127.0.0.1:8000/docs>
- ReDoc: <http://127.0.0.1:8000/redoc>

Vite may select the next available port if 5173 is occupied. In that case, add the chosen frontend origin to `CONTRACTIQ_ALLOWED_ORIGINS` in `backend/.env` and restart the backend.

## Test the Backend

From the repository root, with the virtual environment active:

```powershell
Set-Location backend
python -m pytest -p no:cacheprovider
```

The cache option avoids permission issues some Windows OneDrive folders can cause for pytest's optional cache. You can also inspect each response directly:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/api/v1/status
```

Build-check the frontend in a terminal from the repository root:

```powershell
Set-Location frontend
npm run build
```

## How the Pieces Fit

When the dashboard loads, `App.jsx` calls the reusable `fetchHealth` function in `src/services/api.js`. That function uses `VITE_API_BASE_URL` to request `/health`, checks the HTTP response and returned status, and resolves or throws an error. The app maps that result to a visible connection state. FastAPI's CORS middleware allows the local Vite origin to make the cross-origin request. See [docs/architecture.md](docs/architecture.md) for the request flow and boundaries.

The backend separates app setup, configuration, and routes so later API features can be added in dedicated modules. The frontend separates its shell, reusable controls, pages, and API client so upcoming import work can be added without mixing network logic into presentation components.