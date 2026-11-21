# Development Log

## 2026-11-21 — Stage 2 and Stage 3 audit

- Audited the Stage 2 import, parsing, persistence, versioning, comparison, and frontend paths.
- Audited the Stage 3 test generation, HTTPX execution, response validation, history, target restrictions, and frontend workflow.
- Fixed YAML date scalars to remain JSON-compatible, preserved recursive local schema references, enforced full OpenAPI 3.0/3.1 document validation without remote reference fetching, and redacted sensitive path-parameter values in stored request URLs.
- Pinned validated DNS addresses into the HTTPX transport to prevent DNS rebinding between target validation and connection.
- Replaced the sample PostgreSQL URL's username/password pair with a credential-free local URL template.
- Added focused coverage for YAML import, version comparison, recursive references, DNS pinning, response-size caps, and sensitive path redaction.
- Verified the browser import-to-explorer-to-test-generation workflow and ran read-only HTTPX cases against the local ContractIQ `/health` endpoint; POST cases remained skipped.
- Verified the backend test suite, frontend production build, SQLite migrations, and PostgreSQL migration SQL generation. A live PostgreSQL service was not available for integration testing.
