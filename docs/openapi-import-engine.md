# OpenAPI Import Engine

## Architecture

The Stage 2 backend separates HTTP routes, Pydantic schemas, SQLAlchemy entities, file validation, parsing, and version comparison. Imports are in-memory operations: uploaded bytes are parsed, never executed, and never written to an upload directory.

## Upload flow

1. FastAPI receives a multipart file and validates its `.json`, `.yaml`, or `.yml` extension.
2. The file is limited to `CONTRACTIQ_MAX_UPLOAD_SIZE` (5 MB by default).
3. JSON is decoded with `json.loads`; YAML uses a safe loader that preserves date scalars as strings.
4. The parser verifies the OpenAPI version, `info.title`, and `paths` object, then validates the document against the OpenAPI 3.0/3.1 schema.
5. A SHA-256 content hash detects duplicate imports.
6. SQLAlchemy stores one immutable specification version and extracted endpoint rows in one transaction.

## Database relationships

`projects` owns many `api_specifications`; `api_specifications` owns many `api_endpoints`. Foreign keys cascade deletes. Unique constraints prevent duplicate project versions and duplicate specification/path/method endpoint rows.

For PostgreSQL, set `CONTRACTIQ_DATABASE_URL=postgresql+psycopg://host:5432/database` and provide any required credentials through the local environment or secret manager; do not commit them. Apply migrations with `alembic upgrade head`. The default local SQLite URL permits isolated development.

## References and parsing

Only local `#/...` references are resolved. External references are rejected before schema validation, avoiding outbound reference fetches. Recursive schema references are retained at the recursion boundary; unresolved references and direct reference cycles are rejected. Resolved schemas remain attached to endpoint JSON, with the original `$ref` retained where applicable.

## Versioning and comparison

Every successful import receives the next project version number and is never overwritten. The comparison endpoint reports endpoint additions/removals and parameter, request body, response, and response-code changes. It is structural and should not be described as complete compatibility analysis.
