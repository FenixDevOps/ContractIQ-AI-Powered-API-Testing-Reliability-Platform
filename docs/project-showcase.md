# ContractIQ Project Showcase

## Short description

ContractIQ is a full-stack API testing and reliability workspace. It imports versioned OpenAPI specifications, generates and runs allowlisted contract tests, detects breaking specification changes, and monitors approved read-only endpoints. Project roles, email-verified accounts, and secure session flows provide access control for team workspaces.

## Resume bullets

- Built a full-stack API quality platform with a React/Vite dashboard and FastAPI backend, including OpenAPI import, endpoint exploration, contract test generation, and persisted test history.
- Implemented deterministic OpenAPI compatibility analysis and saved reports to identify request/response contract changes between specification versions.
- Developed bounded, read-only API monitoring with DNS-pinned outbound requests, persistent latency and error measurements, alerting, and Isolation Forest anomaly detection with an explicit warm-up fallback.
- Added project-scoped roles and team workflows, plus Argon2id passwords, rotating refresh sessions, CSRF protection, rate-limited recovery, and single-use email-verification tokens.
- Packaged the application with Docker Compose, PostgreSQL, and an Nginx HTTPS reverse proxy; added migrations, operational setup guidance, and automated backend/frontend tests.

## Recruiter pitch

I built ContractIQ to bring API contract quality and runtime reliability into one workflow. The platform connects OpenAPI specifications to generated tests, deterministic compatibility reports, and scheduled read-only monitoring. I focused on safe execution boundaries, project-level authorization, measurable persisted results, and practical deployment documentation rather than presenting unverified benchmarks as outcomes.

## Technical discussion points

- **API safety:** Tests and monitors require explicit host/port allowlists, validate and pin DNS results, disable redirects, and apply request/response bounds.
- **Compatibility:** Specification changes are compared deterministically, persisted, and exposed through project-scoped APIs and reports.
- **Monitoring:** Database-backed leases coordinate scheduled probes; anomaly scores are not represented as probabilities, and rule-based checks cover the model warm-up period.
- **Authentication:** Access tokens remain in memory, refresh tokens rotate in HttpOnly cookies, CSRF is checked for cookie-authenticated operations, and verification/recovery tokens are stored as hashes.
- **Honest limitations:** WebSocket fan-out is process-local, deployment has not been validated against a live provider, and there are no production traffic or anomaly-accuracy benchmarks.

## Project status

The application has automated backend and frontend checks and versioned database migrations. Docker and a live hosting provider were unavailable during this implementation, so the container configuration has not been built or deployed in a real environment. Treat this as a verified codebase and deployment starting point, not evidence of production operation or measured customer impact.
