# Stage 5: Real-Time API Monitoring

Stage 5 monitors documented public API operations with scheduled, read-only HTTP probes. It stores check outcomes, latency, anomaly summaries, and persistent alerts, and exposes project-scoped dashboards and live alert events.

## Enablement and access control

Apply the Stage 5 migration from `backend`:

```powershell
python -m alembic upgrade head
```

Set these backend environment variables and restart the API:

```text
CONTRACTIQ_MONITORING_AUTH_TOKEN=<random token with at least 32 characters>
CONTRACTIQ_MONITORING_ALLOWED_PROJECT_IDS=<project UUIDs separated by commas>
CONTRACTIQ_MONITORING_SCHEDULER_ENABLED=true
```

Generate a token with Python:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

An empty project allowlist denies all project access. Setting the list to `*` explicitly allows the token to access every project. The frontend asks for the token on the monitoring pages and keeps it in browser `sessionStorage` for the current browser session. REST requests use a bearer header; browser WebSockets use the `contractiq.monitoring.v1` and `bearer.<token>` subprotocols, never a URL query parameter. Do not place the token in source control or a `VITE_*` setting.

This repository has no user identity provider or login/session service. The monitoring token is therefore shared workspace access, not per-user authentication. Project authorization is an environment-configured allowlist, not a user-to-project permission database. For multi-user production deployments, replace this mechanism with an identity provider or an authenticated backend-for-frontend that issues short-lived user sessions; do not ship a shared token in a public static frontend.

## Target safety and scheduled checks

Monitoring reuses `CONTRACTIQ_TEST_ALLOWED_TARGET_HOSTS`, `CONTRACTIQ_TEST_ALLOWED_TARGET_PORTS`, and `CONTRACTIQ_TEST_ALLOW_PRIVATE_TARGETS` from the existing outbound-target guard. Hosts and ports must match the exact allowlist; every scheduled run re-resolves the target, rejects prohibited addresses, and pins the validated DNS addresses for the HTTP connection. Redirects and environment proxy settings are disabled.

Only public `GET`, `HEAD`, and `OPTIONS` operations can be scheduled. Write methods, OpenAPI operations with authentication requirements, specifications with global security, required header/cookie credentials, and sensitive required query/path parameters are rejected. Required non-sensitive parameters need safe examples or defaults. Request bodies, headers, cookies, response bodies, and response headers are not persisted. Response bodies are read only up to `CONTRACTIQ_MONITORING_MAX_RESPONSE_BYTES` (256 KiB by default) for documented response validation, then discarded. A response exceeding the cap is recorded as a bounded error.

The API limits configurations to 20 endpoints, intervals from 30 through 3600 seconds, and timeouts no greater than 30 seconds. The scheduler claims due configurations using database lease fields and runs synchronous HTTP work in a thread, preventing duplicate claims across workers. Pausing prevents future cycles; a currently running request is allowed to finish. Deleting a configuration with an active lease is rejected.

## Metrics and API behavior

Each saved monitoring check is one synthetic probe. The metrics APIs aggregate the checks into success/failure counts, status and error-category distributions, average latency, and p50/p90/p95/p99 latency. Windows are `5m`, `15m`, `1h`, `24h`, or `7d`; `environment_name` can scope metrics and check/error lists. Metrics computation samples at most 20,000 recent check rows and returns `sample_truncated` when more rows exist, so consumers can distinguish sampled percentiles from an exhaustive calculation.

Representative REST routes:

```text
POST  /api/v1/projects/{project_id}/monitoring/configurations
GET   /api/v1/projects/{project_id}/monitoring/configurations
PATCH /api/v1/projects/{project_id}/monitoring/configurations/{configuration_id}
POST  /api/v1/projects/{project_id}/monitoring/configurations/{configuration_id}/start
POST  /api/v1/projects/{project_id}/monitoring/configurations/{configuration_id}/pause
GET   /api/v1/projects/{project_id}/monitoring/overview?window=1h&environment_name=staging
GET   /api/v1/projects/{project_id}/monitoring/metrics?window=24h
GET   /api/v1/projects/{project_id}/monitoring/checks?page=1&page_size=50
GET   /api/v1/projects/{project_id}/monitoring/errors
GET   /api/v1/projects/{project_id}/monitoring/anomalies
GET   /api/v1/projects/{project_id}/monitoring/anomalies/model
POST  /api/v1/projects/{project_id}/monitoring/anomalies/train
GET   /api/v1/projects/{project_id}/monitoring/alerts
PATCH /api/v1/projects/{project_id}/monitoring/alerts/{alert_id}
WS    /ws/v1/projects/{project_id}/monitoring/live
```

Alert lifecycle actions are `read`, `acknowledge`, and `resolve`. Repeated active alerts for the same configuration, endpoint, and type are deduplicated during the 15-minute cooldown. Failed checks and detected anomalies create persistent alerts. No response payload or credential is included in an alert.

## Anomaly detection

The Isolation Forest is trained on persisted check measurements, not labels or response content. Features describe latency and its recent baseline, recent failure/timeout ratios, probe counts, and latency variability. The default minimum is 100 observations; `CONTRACTIQ_ANOMALY_MIN_TRAINING_SAMPLES` can raise it but cannot be set below 20. The model retrains after at least 50 new observations by default or when explicitly requested with the train endpoint; `CONTRACTIQ_ANOMALY_RETRAIN_NEW_SAMPLES` controls the automatic threshold.

Until enough data exists, the service uses deterministic rules for high latency, elevated failure rates, and unusual **monitoring probe volume**. Probe-volume anomalies are not claims about API consumer traffic. Isolation Forest scores are raw isolation scores, not calibrated probabilities. The database stores model version and training metadata; model objects are kept in process memory and rebuilt from persisted measurements after restart rather than loading serialized pickle files.

## WebSocket delivery and limits

The live endpoint is project-scoped and authenticated. It emits persisted alert-created events and periodic application heartbeats. The connection manager is process-local: database leases prevent duplicate scheduled checks across workers, but WebSocket events are not broadcast between workers. Use one backend worker when relying on the live page. A shared event broker is not implemented.

Synthetic probes measure the configured monitor's own request/response behavior. They cannot observe actual traffic volume, user-level request counts, or service-side resource saturation without telemetry instrumentation inside the target API or a metrics integration. Authentication headers and secrets are intentionally unsupported for scheduled targets in this Stage 5 implementation.

## Dashboard and verification

The dashboard pages are Monitoring (configuration and overview), Performance, Errors, AI Insights, Live Monitoring, and Alerts. A target must be allowlisted before a configuration can be saved. If the access token is missing, unconfigured, or lacks project authorization, the monitoring API returns an explicit 401, 403, or 503 error.

Focused backend coverage is in `backend/tests/test_monitoring_routes.py` and `backend/tests/test_monitoring_services.py`. HTTP execution tests use `httpx.MockTransport`; they do not call a live target. The frontend is validated with `npm run build`.
