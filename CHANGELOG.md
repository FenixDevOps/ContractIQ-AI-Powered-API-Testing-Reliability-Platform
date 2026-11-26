# Changelog

## Unreleased

### Stage 4 — Breaking Change Detection

- Added deterministic OpenAPI endpoint, parameter, request, response, content-type, enum, constraint, security, and local-reference comparison with compatibility classifications and indicative severity-weighted scores.
- Added persisted comparison/change history, filtered and paginated APIs, JSON report export, and a React dashboard with version selection, side-by-side finding values, history, and browser printing.
- Added an Alembic migration and focused engine/API tests without changing Stage 1–3 test-run data.

### Stage 2 — OpenAPI Import Engine

- Added project and specification APIs with JSON/YAML uploads, OpenAPI 3.0/3.1 schema validation, endpoint extraction, local references, immutable versions, duplicate detection, and structural comparison.
- Added SQLAlchemy persistence, Alembic migrations, and React project, import, explorer, and comparison screens.

### Stage 3 — Automated API Testing Engine

- Added deterministic test generation, configurable HTTPX execution, status/content-type/schema validation, and persistent run/result history.
- Added target allowlists, DNS address pinning, private-address restrictions, redirect/proxy protections, request timeouts and size limits, secret redaction, and write-operation safeguards.
- Added the React testing workflow, result filtering/details, run history, and summary metrics.
