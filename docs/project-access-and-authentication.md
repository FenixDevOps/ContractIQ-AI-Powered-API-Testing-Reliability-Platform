# Stage 6: Authentication and Project Access

## Account and session behavior

Accounts use Argon2id password hashes. Access tokens are short-lived JWTs held only in frontend memory. Refresh tokens are opaque, rotated on refresh, stored as hashes in the database, and delivered in an HttpOnly cookie. The browser sends a separate CSRF cookie value in a header for refresh and logout. Sessions can be revoked on logout, password change, or password reset. Authentication endpoints apply persistent rate limits keyed by hashed account identity and client address.

Configure these backend variables before production use:

```text
CONTRACTIQ_ENVIRONMENT=production
CONTRACTIQ_SECRET_KEY=<random secret from a secret manager>
CONTRACTIQ_AUTH_COOKIE_SECURE=true
CONTRACTIQ_AUTH_COOKIE_SAMESITE=lax
CONTRACTIQ_AUTH_ALLOW_REGISTRATION=false
CONTRACTIQ_AUTH_REQUIRE_EMAIL_VERIFICATION=true
CONTRACTIQ_EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS=24
CONTRACTIQ_FRONTEND_BASE_URL=https://<frontend-domain>
CONTRACTIQ_ALLOWED_ORIGINS=https://<frontend-domain>
CONTRACTIQ_SMTP_HOST=<smtp-host>
CONTRACTIQ_SMTP_PORT=587
CONTRACTIQ_SMTP_USERNAME=<smtp-user>
CONTRACTIQ_SMTP_PASSWORD=<smtp-password>
CONTRACTIQ_SMTP_FROM_EMAIL=<verified-sender>
CONTRACTIQ_SMTP_USE_TLS=true
```

Generate and store `CONTRACTIQ_SECRET_KEY` outside source control; production requires at least 32 characters. Production startup also rejects insecure cookies and non-HTTPS frontend/CORS origins. The development fallback is generated per process and is not suitable for a multi-instance deployment. `SameSite=None` requires secure cookies. Configure SMTP before enabling registrations, invitations, email verification, or password recovery.

When email verification is required, registration sends a one-time URL-fragment link, and unverified users cannot sign in. Links are stored as hashes, expire after the configured interval, and can be requested again through the generic-response endpoint. The development default does not require verification; production defaults to requiring it. Existing accounts without a verified address must complete verification before signing in. Password reset uses single-use links with URL-fragment tokens, generic response wording, hashed token storage, and a configurable expiration.

## Project roles

| Role | Read project data | Edit project resources | Manage team/archive | Delete project |
|---|---:|---:|---:|---:|
| Owner | Yes | Yes | Yes | Yes |
| Admin | Yes | Yes | Yes | No |
| Member | Yes | Yes | No | No |
| Viewer | Yes | No | No | No |

Only owners can grant or manage the Admin role and transfer ownership. All project-scoped specifications, endpoints, test runs/results, compatibility comparisons, monitoring records, alerts, and WebSocket connections require project membership. The backend is the authorization boundary; hiding a frontend control does not grant or deny access.

Legacy projects remain unclaimed after applying the Stage 6 migration. This avoids granting an unauthenticated first registrant access to pre-existing data. To assign a project, first create and verify the intended operator account out of band, then run this command from `backend` for each unclaimed project:

```powershell
python -m app.scripts.claim_legacy_projects --owner-email owner@example.com --project-id <project-uuid>
```

The command refuses inactive/missing users, unknown projects, and projects that already have memberships. Production registration defaults to disabled; explicitly set `CONTRACTIQ_AUTH_ALLOW_REGISTRATION=true` only when open registration is intended. Use an operator-controlled provisioning process when registration is disabled.

Invitations are email-bound and expire after seven days. The recipient must sign in or register with the invited address, complete email verification when required, and then accept. Invitation tokens are single-use and stored as hashes. An owner may transfer project ownership to another existing member; the former owner becomes an Admin.

## API routes

- `POST /api/v1/auth/register`, `/login`, `/refresh`, and `/logout`
- `GET /api/v1/auth/me` and `PATCH /api/v1/auth/me`
- `POST /api/v1/auth/change-password`
- `POST /api/v1/auth/email-verification/request` and `/confirm`
- `POST /api/v1/auth/password-reset/request` and `/confirm`
- `GET /api/v1/projects?include_archived=true`
- `POST /api/v1/projects`; `GET`, `PATCH`, `DELETE /api/v1/projects/{project_id}`
- `POST /api/v1/projects/{project_id}/archive` and `/restore`
- `GET /api/v1/projects/{project_id}/members`
- `POST /api/v1/projects/{project_id}/invites`, `GET` and `DELETE` invitations
- `POST /api/v1/projects/invites/accept`
- `PATCH` and `DELETE /api/v1/projects/{project_id}/members/{user_id}`
- `POST /api/v1/projects/{project_id}/transfer-ownership?new_owner_id={user_id}`
- `GET /api/v1/projects/{project_id}/activity` and `/dashboard`

## Container deployment

The repository includes Dockerfiles, an Nginx SPA/API/WebSocket proxy, and a PostgreSQL-backed Compose definition. Docker is not required for local development. To prepare a deployment from the repository root:

```powershell
Copy-Item deploy.compose.env.example .env
```

Set `POSTGRES_PASSWORD` to a strong URL-safe value, set `CONTRACTIQ_SECRET_KEY` to a generated secret of at least 32 characters, and replace the example HTTPS hostnames and `CONTRACTIQ_PUBLIC_HOST` with the deployed frontend domain. Set `CONTRACTIQ_TLS_CERT_PATH` and `CONTRACTIQ_TLS_KEY_PATH` to absolute paths for the TLS certificate chain and private key on the Docker host. Configure SMTP before enabling registration, invitations, email verification, or password recovery. Then run the migration once and start the services:

```powershell
docker compose run --rm backend python -m alembic upgrade head
docker compose up --build -d
```

The frontend proxy redirects HTTP to HTTPS and publishes ports 80/443 by default. The database uses a named persistent volume and the backend is not published directly. If TLS is terminated by an upstream load balancer instead, keep its connection to this stack encrypted and do not expose the HTTP listener to untrusted networks. Validate proxy WebSocket upgrades, cookie behavior, SMTP delivery, backups, and migrations in the actual hosting environment before production use. Compose uses a single backend instance; live WebSocket fan-out remains process-local.

## Known limitations

The repository does not include a verified hosted production deployment or an identity-provider integration. Use health/readiness probes in the chosen hosting environment and test the actual proxy behavior before deployment.

There is no organization-wide account administration UI, invite resend flow, or multi-worker WebSocket broker. The first-user legacy-project claim is a bootstrap mechanism and requires operator review for existing multi-tenant data.
