# ContractIQ

ContractIQ is a local-first API testing and reliability platform. It includes the Stage 1 foundation, Stage 2 OpenAPI import/version management, Stage 3 contract-driven test generation and opt-in API execution, Stage 4 deterministic breaking-change detection, and Stage 5 scheduled API monitoring with persisted measurements, alerts, and anomaly detection.

## Implemented Features

- FastAPI project, health, and versioned status endpoints.
- Interactive API documentation at `/docs`.
- Configurable backend CORS and application metadata.
- Responsive React dashboard with Overview, Projects, API Explorer, Test Runs, Contract Changes, Monitoring, Performance, Errors, AI Insights, Live Monitoring, Alerts, and Settings navigation.
- The dashboard calls the backend `/health` endpoint and presents loading, connected, disconnected, and retry states.
- Searchable command palette (`Ctrl+K` / `Cmd+K`), project selector, notifications menu, profile menu, and mobile navigation drawer.
- API health metrics, trend chart, recent executions, and change panels show explicit empty states until real product data exists.
- Safe OpenAPI 3.0/3.1 JSON/YAML import, project/specification persistence, endpoint exploration, versions, and structural comparison.
- OpenAPI-derived API test generation, HTTPX execution against explicitly allowlisted hosts, response validation, persisted test results, and report history.
- Deterministic OpenAPI compatibility comparisons, severity and compatibility classification, indicative scoring, persisted comparison history, filtering, and JSON report export.
- Scheduled read-only API probes with host allowlisting, DNS-pinned connections, bounded timeouts/responses, per-environment metrics, and persistent checks.
- Project-scoped REST/WebSocket monitoring access, database-backed scheduler leases, persistent deduplicated alerts, and process-local live alert delivery.
- Isolation Forest anomaly detection trained only on collected measurements, with a rule-based warm-up fallback and scores explicitly identified as non-probabilities.
- Pytest coverage for health, imports, generation, schema validation, HTTPX mock execution, and run history.

## Technology

- **Python 3.11 or 3.12 / FastAPI:** typed HTTP API with generated OpenAPI docs and an ASGI server.
- **Pytest / HTTPX:** tests API responses and executes bounded API test cases; backend HTTPX tests use mock transports.
- **JavaScript / React:** reusable, interactive dashboard interface.
- **Vite:** local development server and production bundler for the frontend.
- **Tailwind CSS:** utility foundation and design tokens, with page-specific visual styling in `src/App.css`.
- **shadcn-style UI primitives:** local accessible button variants built with class-variance-authority and Tailwind class merging.
- **Recharts:** responsive chart primitives for later telemetry screens.
- **Fetch API:** native browser HTTP client; no additional HTTP library is required.
- **Lucide React:** open-source interface icons.

## Project Structure

```text
ContractIQ/
├── backend/
│   ├── app/
│   │   ├── database/            # SQLAlchemy entities, engine, and sessions
│   │   ├── routes/              # Health, projects, import, testing, compatibility, monitoring APIs
│   │   ├── schemas/             # Request and response models
│   │   ├── services/            # Parsing, validation, execution, monitoring, metrics, and anomaly detection
│   │   ├── utils/               # Upload validation
│   │   ├── config.py            # Environment-driven settings
│   │   └── main.py              # FastAPI app, CORS, and router registration
│   ├── alembic/                 # Versioned database migrations
│   ├── tests/                   # API, parser, validation, and mocked execution tests
│   ├── .env.example             # Credential-free environment template
│   └── requirements.txt         # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── components/          # Navigation, backend status, and shared UI primitives
│   │   │   └── ui/button.jsx    # Reusable shadcn-style button variants
│   │   ├── pages/               # Overview, import/explorer, testing, compatibility, and monitoring screens
│   │   ├── services/api.js      # Shared backend API client
│   │   ├── App.jsx              # App shell and page navigation
│   │   ├── App.css              # Responsive dashboard styling
│   │   └── main.jsx             # React browser entry point
│   ├── .env                     # Local Vite API URL (ignored by Git)
│   ├── .env.example             # Example Vite API URL
│   ├── index.html               # Vite HTML entry point
│   ├── package.json             # Scripts and JavaScript dependencies
│   ├── tailwind.config.js        # Tailwind content paths and theme tokens
│   ├── postcss.config.js         # Tailwind and Autoprefixer integration
│   └── vite.config.js           # Vite React plugin configuration
├── docs/
│   ├── architecture.md
│   ├── openapi-import-engine.md
│   ├── automated-testing-engine.md
│   ├── breaking-change-detection.md
│   ├── deployment-options.md
│   ├── project-access-and-authentication.md
│   ├── project-showcase.md
│   ├── real-time-monitoring.md
│   └── development_log.md
├── .gitignore                   # Excludes generated and local-only files
├── CHANGELOG.md
└── README.md
```

## Requirements

- Windows 11 with Python 3.11 or 3.12 and Node.js 18 or later.
- PowerShell and a terminal in VS Code.
- No paid services are required. SQLite is the local default; PostgreSQL is supported for persistent deployment.

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
python -m alembic upgrade head
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --env-file .env
```

The server reads `CONTRACTIQ_*` settings from the backend environment file. Apply Alembic migrations before starting the application. Testing and monitoring requests are disabled until exact target hosts/ports are allowlisted; DNS results are pinned for each run to prevent rebinding between validation and connection. Stage 5 additionally requires a backend monitoring token and an explicit project allowlist; see [docs/real-time-monitoring.md](docs/real-time-monitoring.md) before enabling it.

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
python -m pytest -v
```
You can also inspect each response directly:

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

The backend separates app setup, configuration, routes, persistence, schemas, and service logic. The frontend separates navigation, reusable controls, data-backed pages, and API client functions. Stage-specific implementation notes are in the linked architecture documents.

## Stage 2: OpenAPI Import Engine

Stage 2 adds JSON/YAML OpenAPI 3.0.x and 3.1.x imports, PostgreSQL/SQLite persistence, immutable specification versions, endpoint extraction, project and endpoint APIs, basic version comparison, and React project/import/explorer screens.

### PostgreSQL configuration

Set `CONTRACTIQ_DATABASE_URL` in `backend/.env` using your local PostgreSQL configuration. Do not commit credentials:

```text
CONTRACTIQ_DATABASE_URL=postgresql+psycopg://localhost:5432/contractiq
CONTRACTIQ_MAX_UPLOAD_SIZE=5242880
```

The default local fallback is SQLite at `backend/contractiq.db`. Alembic migrations are available in `backend/alembic`; initialize or upgrade a PostgreSQL database with:

```powershell
Set-Location backend
python -m alembic upgrade head
```

### Stage 2 API routes

- `POST /api/v1/projects`
- `GET /api/v1/projects`
- `POST /api/v1/projects/{project_id}/specifications/import`
- `GET /api/v1/projects/{project_id}/specifications`
- `GET /api/v1/specifications/{specification_id}`
- `GET /api/v1/specifications/{specification_id}/endpoints`
- `GET /api/v1/specifications/{specification_id}/versions`
- `GET /api/v1/specifications/{specification_id}/raw`
- `GET /api/v1/specifications/{specification_id}/compare/{other_specification_id}`

Upload `.json`, `.yaml`, or `.yml` files. JSON and YAML are validated against the OpenAPI 3.0/3.1 schema. External `$ref` URLs are rejected; local `#/components/...` references are resolved safely, including recursive schemas. Unresolved references and direct reference cycles produce validation errors. Duplicate content hashes return HTTP 409.

### Stage 2 testing

```powershell
Set-Location backend
python -m pytest -p no:cacheprovider
```

```powershell
Set-Location frontend
npm run build
```

See [docs/openapi-import-engine.md](docs/openapi-import-engine.md) for parser, database, upload, reference, and versioning details.

## Stage 3: Automated API Testing Engine

Generate test cases from a selected imported specification, enable/disable cases, configure an environment and target base URL, execute HTTPX tests, validate status/content type/JSON schema, and inspect persisted results and run history. Write methods require explicit enablement and confirmation; production environment runs are read-only.

### Execution target security

Test execution requires explicit exact-host and port allowlists. DNS is resolved once during validation, and the HTTPX transport connects only to those validated addresses while retaining the configured hostname for HTTP and TLS. For a local development API, configure `backend/.env` (development only):

```text
CONTRACTIQ_TEST_ALLOWED_TARGET_HOSTS=localhost,127.0.0.1
CONTRACTIQ_TEST_ALLOWED_TARGET_PORTS=8000
CONTRACTIQ_TEST_ALLOW_PRIVATE_TARGETS=true
```

For a staging API, allow only its exact hostname and required port, keeping private target access disabled unless the deployment specifically requires it. Redirects are not followed; request timeouts, a 1 MB response limit, and a 100-case run limit are applied by default.

### Stage 3 API routes

- `POST /api/v1/specifications/{specification_id}/test-cases/generate`
- `GET /api/v1/specifications/{specification_id}/test-cases`
- `GET`, `PATCH`, and `DELETE /api/v1/test-cases/{test_case_id}`
- `POST /api/v1/specifications/{specification_id}/test-runs`
- `POST /api/v1/test-runs/execute-selected`
- `GET /api/v1/specifications/{specification_id}/test-runs`
- `GET /api/v1/test-runs/{test_run_id}` and `/results`
- `GET /api/v1/test-results/{result_id}`
- `GET /api/v1/specifications/{specification_id}/testing-summary`
- `DELETE /api/v1/test-runs/{test_run_id}`

### Manual demonstration

1. Import an OpenAPI JSON/YAML file and select the project/specification in **Test Runs**.
2. Click **Generate test cases**; review categories and enable only cases appropriate for your test API.
3. Configure an exact backend allowlisted target, for example the local development settings above, plus any authorized default headers.
4. Run read-only cases first. To execute POST/PUT/PATCH/DELETE outside production, select both write-operation and destructive-confirmation checkboxes.
5. Inspect result details and saved execution history. Network tests in the test suite use mocks and never call production APIs.

See [docs/automated-testing-engine.md](docs/automated-testing-engine.md) for generation behavior, validation, security constraints, environment settings, request examples, and limitations.

## Stage 4: Breaking Change Detection

Compare two imported OpenAPI versions in **Contract Changes**. The engine analyzes normalized endpoint paths, parameters, request and response schemas, local component references, response codes, content types, enums, constraints, security, and nullability. Findings are persisted with their severity, compatibility status, explanation, and recommended action. The dashboard provides comparison history, filters, side-by-side old/new values, a printable report, and downloadable JSON.

### Stage 4 API routes

- `POST /api/v1/compatibility/compare`
- `GET /api/v1/projects/{project_id}/compatibility?page=1&page_size=20`
- `GET /api/v1/compatibility/{comparison_id}`
- `GET /api/v1/compatibility/{comparison_id}/changes` (severity, compatibility, category, method, and path filters; paginated)
- `GET /api/v1/compatibility/{comparison_id}/summary`
- `GET /api/v1/compatibility/{comparison_id}/report/json`
- `DELETE /api/v1/compatibility/{comparison_id}`

Apply database changes with `python -m alembic upgrade head` from `backend`. PDF export is not included; use the report's print action to print or save a browser-generated PDF.

See [docs/breaking-change-detection.md](docs/breaking-change-detection.md) for comparison rules, score weights, persistence, API examples, reference handling, test coverage, and limitations.

## Stage 5: Real-Time API Monitoring

Stage 5 adds scheduled, read-only probes for public `GET`, `HEAD`, and `OPTIONS` endpoints, using the existing exact host/port allowlist and DNS-pinned transport. It persists response status, latency, safe error categories, anomalies, and alerts without storing response bodies or headers. The dashboard now includes monitoring setup, availability/latency trends, errors, anomaly explanations, a project alert stream, and alert lifecycle actions.

### Enable Stage 5

1. Apply `python -m alembic upgrade head` from `backend`.
2. Add each approved target's exact hostname and port to `CONTRACTIQ_TEST_ALLOWED_TARGET_HOSTS` and `CONTRACTIQ_TEST_ALLOWED_TARGET_PORTS`. Private targets remain disabled unless explicitly enabled for development.
3. Sign in with an account that belongs to the project. Monitoring REST and WebSocket requests use the account session and enforce project membership.
4. Create a configuration and start it. The scheduler supports intervals from 30 to 3600 seconds, up to 20 endpoints per configuration, and timeouts up to 30 seconds.

### Stage 5 API routes

- `POST /api/v1/projects/{project_id}/monitoring/configurations`
- `GET /api/v1/projects/{project_id}/monitoring/configurations`
- `PATCH /api/v1/projects/{project_id}/monitoring/configurations/{configuration_id}`
- `POST /api/v1/projects/{project_id}/monitoring/configurations/{configuration_id}/start`
- `POST /api/v1/projects/{project_id}/monitoring/configurations/{configuration_id}/pause`
- `GET /api/v1/projects/{project_id}/monitoring/overview`
- `GET /api/v1/projects/{project_id}/monitoring/metrics`
- `GET /api/v1/projects/{project_id}/monitoring/checks` and `/errors`
- `GET /api/v1/projects/{project_id}/monitoring/anomalies` and `/anomalies/model`
- `POST /api/v1/projects/{project_id}/monitoring/anomalies/train`
- `GET /api/v1/projects/{project_id}/monitoring/alerts`; `PATCH .../alerts/{alert_id}`
- `WS /ws/v1/projects/{project_id}/monitoring/live`

Live WebSocket events are delivered only within the current backend process; run a single worker when using the live page. Synthetic probe counts are not actual client-traffic measurements. See [docs/real-time-monitoring.md](docs/real-time-monitoring.md) for security boundaries, model warm-up, data limits, environment filters, and these limitations.

## Stage 6: Accounts, Project Access, and Production Readiness

Stage 6 adds account registration and sign-in, email verification, rotating refresh sessions, password reset and change flows, project membership roles, project lifecycle actions, invitation management, and project activity/dashboard data. Existing testing, compatibility, and monitoring APIs are now scoped to project membership. Legacy projects remain unclaimed until an operator explicitly assigns ownership. Dockerfiles and a PostgreSQL Compose deployment are included; no live deployment is claimed. See [docs/project-access-and-authentication.md](docs/project-access-and-authentication.md) for role boundaries and deployment guidance, [docs/deployment-options.md](docs/deployment-options.md) for a sourced hosting/free-tier comparison, and [docs/project-showcase.md](docs/project-showcase.md) for a portfolio summary with verified scope and limitations.

Apply all schema changes with `python -m alembic upgrade head` from `backend`. Production deployments must configure `CONTRACTIQ_SECRET_KEY`, secure cookies, exact allowed origins, and SMTP credentials before enabling account workflows. Registration defaults to disabled and email verification defaults to required in production. Multi-worker WebSocket broadcasting is not implemented. Do not claim a live deployment without validating it in the target environment.