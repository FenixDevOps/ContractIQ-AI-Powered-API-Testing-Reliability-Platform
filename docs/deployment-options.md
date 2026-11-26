# Hosting Options for a ContractIQ Demo

Checked 2026-11-26 against the official provider pages linked below. Prices and free-tier terms change; confirm them in the provider calculator and account before provisioning. This is a feasibility comparison, not a deployment or cost guarantee.

ContractIQ needs a persistent PostgreSQL database, an always-on single backend process for complete live WebSocket delivery, HTTPS, outbound email for verification/invitations/recovery, and enough memory for the monitoring and anomaly-detection workload.

| Provider | Current low-cost/free facts | Fit and caveats |
|---|---|---|
| Render | Free web services sleep after 15 minutes without inbound traffic; their filesystem is ephemeral. Free Postgres is limited to 1 GB and expires after 30 days. Render documents that free web services cannot send outbound SMTP on ports 25, 465, or 587. Paid service compute starts at $7/month and Postgres at $6/month on the pricing page, before any applicable usage or storage charges. | Free is suitable only for disposable previews, not this persistent auth-enabled app. Paid services have managed TLS and documented WebSocket support, but the current SMTP integration is incompatible with Render's outbound SMTP restriction; use an HTTPS email provider integration or choose another host. |
| Railway | Free includes $1/month of usage, up to 0.5 GB RAM per service, one replica, and 0.5 GB of volume storage; free services sleep after 5–10 minutes without outbound traffic. Hobby costs $5/month and includes $5/month of usage; Hobby services are always-on, with usage beyond the included amount billed separately. | A possible low-cost public demo on Hobby, but estimate actual usage for backend, frontend, and PostgreSQL. Scheduled probes may generate outbound traffic that prevents useful idle behavior on Free. The pricing pages reviewed do not establish SMTP egress behavior; verify delivery and WebSocket routing before selecting it. |
| Azure App Service | The F1 free plan lists 60 CPU minutes/day and 1 GB storage, has no SLA, and is explicitly not supported for production workloads. A PostgreSQL service is separate; total pricing depends on region and configuration. | Useful for learning the Azure platform, but not a dependable free home for the continuous scheduler and persistent database. Use the Azure pricing calculator for a paid estimate. |

## Recommendation

There is no verified zero-cost production option for this stack. For local evaluation, use the repository's Docker Compose setup on a machine where Docker is available. For a public demo, Railway Hobby is a candidate if actual usage stays within budget and SMTP/WebSocket behavior is confirmed; otherwise, use a small always-on VM or a paid managed container/database plan. Render's free tier is not suitable for persistent data or required SMTP delivery as currently implemented.

Do not treat this research as a provider selection or proof of deployment. Docker was unavailable during this implementation, so the Compose stack and live TLS, PostgreSQL, WebSocket, and email behavior still need validation in the chosen hosting environment.

## Official sources

- [Render pricing](https://render.com/pricing)
- [Render free services and limitations](https://render.com/docs/free)
- [Railway pricing](https://railway.com/pricing)
- [Railway pricing plans documentation](https://docs.railway.com/reference/pricing/plans)
- [Azure App Service on Linux pricing](https://azure.microsoft.com/en-us/pricing/details/app-service/linux/)
