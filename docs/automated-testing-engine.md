# Automated API Testing Engine

Stage 3 extends the Stage 2 OpenAPI importer with deterministic test generation, opt-in HTTPX execution, response validation, persisted run history, and a React reporting page.

## Architecture

- `routes/testing.py` validates input, scopes operations to specification/test IDs, and provides generation, case configuration, run, history, and result APIs.
- `services/test_generator.py` builds stable, duplicate-free cases from persisted endpoint operations. It uses documented examples/defaults/enums where possible and marks unavailable inputs instead of inventing target-specific values.
- `services/test_executor.py` runs cases sequentially with HTTPX, bounded timeouts and response size, no redirects, sanitized result details, and per-case failure isolation.
- `services/response_validator.py` checks documented status codes, response media types, and response JSON Schemas (including local refs, nested schemas, formats, and OpenAPI 3.0 `nullable`).
- `database/models.py` stores cases, runs, and individual results. Result snapshots preserve historical test names/configuration even if a test case is deleted.
- `frontend/src/pages/TestingPage.jsx` provides generation, case enablement/filtering, execution configuration, latest results, run history, and detail inspection.

## Test generation

Generate and list cases:

```http
POST /api/v1/specifications/{specification_id}/test-cases/generate
GET  /api/v1/specifications/{specification_id}/test-cases?include_disabled=true
```

Generation is idempotent for a specification: stable generation keys prevent repeats from creating duplicates. A new specification version has its own cases. Cases with unavailable path/query/header/body inputs are retained with a reason and are reported as skipped until configured.

Update a case with `PATCH /api/v1/test-cases/{test_case_id}` (for example `{"is_enabled": false}`), or delete it with `DELETE /api/v1/test-cases/{test_case_id}`. Existing run results are retained as snapshots.

## Target allowlist and security

The execution endpoint is intentionally disabled for hosts that are not explicitly allowlisted. Set exact hostnames and ports in backend environment configuration, for example:

```text
CONTRACTIQ_TEST_ALLOWED_TARGET_HOSTS=api.staging.example
CONTRACTIQ_TEST_ALLOWED_TARGET_PORTS=443
CONTRACTIQ_TEST_ALLOW_PRIVATE_TARGETS=false
CONTRACTIQ_TEST_MAX_RESPONSE_BYTES=1048576
CONTRACTIQ_TEST_MAX_CASES_PER_RUN=100
```

For local development only, explicitly allow a local host, port, and private address access:

```text
CONTRACTIQ_TEST_ALLOWED_TARGET_HOSTS=localhost,127.0.0.1
CONTRACTIQ_TEST_ALLOWED_TARGET_PORTS=8000
CONTRACTIQ_TEST_ALLOW_PRIVATE_TARGETS=true
```

The configured exact host allowlist is required in either case. URL validation rejects non-HTTP(S) schemes, embedded credentials, query strings, fragments, unapproved ports, unapproved hosts, and prohibited network ranges. DNS is resolved once, the validated addresses are pinned in the HTTPX connection backend, and the original hostname remains in the request URL for HTTP host routing and TLS verification. This prevents a second DNS lookup from redirecting the connection after validation. A base URL may include a non-traversing path prefix such as `/v1`. Private/loopback targets are denied by default. HTTPX does not use environment proxies and does not follow redirects. Redirect responses are reported, not followed. Each request is subject to the configured response-byte cap.

Only generated negative tests for GET/HEAD/OPTIONS can run. POST/PUT/PATCH/DELETE are skipped by default and require both `allow_write_operations` and `confirm_destructive`. `production` environment runs allow only GET/HEAD/OPTIONS regardless of flags. Configure targets only when you are authorized to test them. Use a staging/mock API before production.

Default/auth headers are passed only for that execution, are never included in the run API response, and are redacted from persisted request details. Secret-like fields, sensitive path/query parameters, and bearer values in captured JSON/text are redacted in test-case and result snapshots. Response bodies are size limited but may still contain sensitive business data; use test data and restrict database access.

## HTTPX execution

Run all enabled cases:

```http
POST /api/v1/specifications/{specification_id}/test-runs
Content-Type: application/json

{
  "base_url": "https://api.staging.example",
  "environment_name": "staging",
  "timeout_seconds": 10,
  "include_negative_tests": false,
  "allow_write_operations": false,
  "confirm_destructive": false,
  "default_headers": {}
}
```

Run selected cases through `POST /api/v1/test-runs/execute-selected` with `test_case_ids` plus the same execution configuration. The synchronous executor runs up to the configured case limit serially. A completed run can include PASSED, FAILED, SKIPPED, and ERROR results; a single HTTP/network failure does not stop other cases.

## Validation and reports

Status validation checks the documented successful status codes. Schema validation supports JSON Schema object/array constraints, required properties, primitive types, enums, formats, composition keywords, local component references, and OpenAPI 3.0 nullable values. Content type validation compares normalized media types. Failures contain machine-readable codes and paths.

Useful read APIs:

- `GET /api/v1/specifications/{specification_id}/testing-summary`
- `GET /api/v1/specifications/{specification_id}/test-runs`
- `GET /api/v1/test-runs/{test_run_id}`
- `GET /api/v1/test-runs/{test_run_id}/results`
- `GET /api/v1/test-results/{result_id}`

`DELETE /api/v1/test-runs/{test_run_id}` explicitly removes a run and its results. Normal test generation never removes history.

## Database and migrations

The `test_cases` and `test_runs` tables belong to a specification. `test_results` belong to a run and reference a test case with `ON DELETE SET NULL`; a JSON snapshot preserves the test identity when a case is removed. Apply the Alembic migrations with `python -m alembic upgrade head` before starting the backend. The migration adds Stage 3 tables without changing Stage 2 specification data.

## Limitations

- Generation is intentionally conservative and does not infer business-specific identifiers, authentication, or arbitrary request values.
- The engine validates response bodies against documented JSON schemas; it does not generate exhaustive property-based tests.
- Comparison of media types is strict after removing parameters.
- Runs are synchronous and serial; background workers, cancellation, and live progress are not included.
- OAuth flows and API-key discovery are not automated. Supply authorized headers for a run.
- A host allowlist is a deployment guard, not a substitute for confirming authorization and using isolated test data.

## Tests

From `backend`, run `python -m pytest -p no:cacheprovider`. Network tests use HTTPX mock transports and do not call production services. Validate migration SQL with `python -m alembic upgrade head --sql`.
