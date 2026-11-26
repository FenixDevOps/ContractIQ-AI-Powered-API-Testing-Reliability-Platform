# Stage 4: Breaking Change Detection

ContractIQ compares two stored OpenAPI 3.0/3.1 documents and saves a deterministic report. It does not execute API calls or fetch remote references. The existing Stage 2 endpoint comparison remains available; Stage 4 adds classified findings, history, filters, scores, and JSON exports.

## Architecture and workflow

1. Import two valid specifications into the same project.
2. `POST /api/v1/compatibility/compare` validates that the IDs exist, belong to the same project, and are different.
3. `CompatibilityEngine` compares the stored raw OpenAPI documents. It normalizes path templates (`/users/{id}` and `/users/{user_id}` match), then inspects operations, parameters, media types, request bodies, responses, security requirements, and JSON Schema constraints.
4. The comparison summary and all findings are written in one database transaction.
5. The dashboard reads saved history, summary and filtered/paginated changes. JSON export serializes the saved report. The browser print action can create a PDF without a server-side PDF dependency.

The backend implementation is in `backend/app/services/compatibility_engine.py`; persistence is in `backend/app/database/models.py`, with migration `backend/alembic/versions/20261126_003_compatibility.py`.

## Change record

Each finding has a UUID, category, change type, severity, compatibility classification, endpoint path and method when applicable, schema property, old/new values, explanation, and recommendation. Values are limited to the changed contract detail rather than request/response examples.

Categories include `ENDPOINT`, `PARAMETER`, `REQUEST_BODY`, `RESPONSE`, `RESPONSE_SCHEMA`, `SECURITY`, and `CONTENT_TYPE`.

## Compatibility rules

Rules account for request-versus-response direction. The table summarizes common cases; exact finding types are included in the persisted change records.

| Change | Request contract | Response contract |
|---|---|---|
| Endpoint removed | Breaking / critical | Breaking / critical |
| Endpoint added | Non-breaking / low | Non-breaking / low |
| Parameter newly required | Breaking / high | N/A |
| Optional request field added | Non-breaking / low | N/A |
| Required request field added | Breaking / high | N/A |
| Response field removed | N/A | Breaking / high |
| Optional response field added | N/A | Non-breaking / low, unless the old schema closed the object |
| Incompatible type or format change | Breaking or potentially breaking | Breaking or potentially breaking |
| Request enum values removed | Breaking / high | N/A |
| Response enum values added | N/A | Potentially breaking / medium |
| Response status removed | N/A | Breaking / high |
| Request content type removed | Breaking / high | N/A |
| Response content type removed | N/A | Potentially breaking / medium |

Other compared details include path/query/header/cookie parameters, operation identifiers, path parameter renames, request body presence/required status, array items, nested object properties, `required`, `nullable` and OpenAPI 3.1 null unions, numeric/string/array/object constraints, `allOf`/`oneOf`/`anyOf`, `additionalProperties`, response headers, and security requirements.

Optional parameter or property additions are generally treated as non-breaking. Restricting request enums or tightening request constraints is breaking; expanding response enums can be risky for clients that reject unknown values. Adding fields to a response schema that was closed (`additionalProperties: false`) is potentially breaking. Metadata-only operation ID changes are low severity; path-parameter renames on an otherwise matching route are informational.

These are deterministic heuristics, not proof of runtime compatibility. A change can affect consumers in ways not represented by the contract.

## Severity and score

The engine assigns per-change penalties:

| Severity | Penalty |
|---|---:|
| CRITICAL | 30 |
| HIGH | 15 |
| MEDIUM | 7 |
| LOW | 2 |
| INFO | 0 |

`compatibility_score = max(0, 100 - sum(change penalties))`. Every detected finding contributes; the score is clamped at zero. It is an indicative heuristic, not a mathematically proven compatibility guarantee. Overall status is `BREAKING` if any breaking finding exists, otherwise `POTENTIALLY_BREAKING` if any potentially breaking finding exists, otherwise `COMPATIBLE`.

## References and limits

- Local JSON Pointer references are resolved in-memory, including nested components and escaped pointer segments. Reference data remains unchanged in the stored source specification.
- External references are not fetched. Unresolved, unsupported, circular, or too-deep references are bounded and reported as informational limitations rather than followed over the network.
- Schema traversal has a depth limit of 40 to bound recursive documents.
- Composed schema (`allOf`, `oneOf`, `anyOf`) changes are detected and classified as potentially breaking; individual branches are not fully normalized into an equivalence proof.
- Endpoint identity uses HTTP method plus path with parameter names normalized by position. A method change is represented as an endpoint removal and addition.
- A score does not account for server behavior, actual client usage, or deployment sequence.
- PDF creation is client-side via the browser print dialog; there is no server PDF endpoint.

## Persistence

`compatibility_comparisons` stores project/specification references, score/status, change counts, comparison metadata, and timestamp. `compatibility_changes` stores the individual findings with JSON old/new values. Database foreign keys cascade when a project/specification/comparison is removed. Stage 1–3 tables and test-run history are not modified.

Run the new Alembic migration from `backend`:

```powershell
python -m alembic upgrade head
```

The models use portable SQLAlchemy JSON with JSONB on PostgreSQL, so local SQLite tests exercise the same API behavior.

## API

Create and persist a comparison:

```http
POST /api/v1/compatibility/compare
Content-Type: application/json

{
  "old_specification_id": "UUID",
  "new_specification_id": "UUID"
}
```

Other endpoints:

- `GET /api/v1/projects/{project_id}/compatibility?page=1&page_size=20` — paginated history and aggregate dashboard metrics.
- `GET /api/v1/compatibility/{comparison_id}` — comparison and all findings.
- `GET /api/v1/compatibility/{comparison_id}/changes?severity=HIGH&compatibility=BREAKING&category=RESPONSE_SCHEMA&method=GET&path=/users&page=1&page_size=50` — filtered, paginated findings.
- `GET /api/v1/compatibility/{comparison_id}/summary` — score, endpoint summary, and limitations.
- `GET /api/v1/compatibility/{comparison_id}/report/json` — downloadable JSON report.
- `DELETE /api/v1/compatibility/{comparison_id}` — delete a report and its findings.

History page size is limited to 100 and findings page size to 200. Invalid UUIDs are rejected by FastAPI; missing records return 404, cross-project comparisons return 400, and comparing a specification with itself returns 422.

## Frontend and reports

The **Breaking Changes** page loads projects, specifications, history, and findings from the backend. It prevents self-comparisons, shows progress/error/empty states, supports severity/category/path filtering, presents old and new values side-by-side, and offers JSON download and browser printing. No demo comparison data is hardcoded.

## Testing

From `backend`:

```powershell
python -m pytest -v
```

Tests cover normalized parameterized paths, required request fields, type and enum changes, nested/circular local references, response property/status changes, endpoint additions, persisted comparisons, filtering, summary, JSON export, deletion, and invalid project/specification combinations.
