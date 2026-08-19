# Phase 0 Report

Status: **local acceptance complete; real AWS staging deployment pending credentials**.

## Implemented

- Monorepo with `api`, `web`, `agent-worker`, `worker`, shared Python/TypeScript packages and provider mock.
- Docker Compose for PostgreSQL 16 + pgvector, Redis 7 and all application services.
- Alembic schema for product tables plus Auth.js tables; tenant-scoped tables use forced RLS with `app.tenant_id`, including tenant-row isolation and a non-bypass application role.
- PostgreSQL repository opens a transaction and applies `SET LOCAL app.tenant_id` before tenant queries.
- Idempotent PostgreSQL seed creates plans, demo tenant/owner, agent/version, KB with three documents, two tools and 20 calls.
- FastAPI JWT/tenant/internal authentication, standard errors, OpenAPI 3.1, request IDs, `/health` and `/ready`.
- Next.js 15 dashboard and Auth.js with Resend magic link, optional Google login, PostgreSQL adapter, cryptographically validated middleware and a five-minute API JWT exchange backed by real memberships.
- CI gates for migrations, Ruff, strict mypy, pytest coverage, ESLint, TypeScript and production builds.
- Terraform for VPC, public/private subnets, NAT, KMS, RDS, ElastiCache, S3, ECR, ECS/Fargate, ALB, logs and secrets.
- Two-stage deployment workflow using GitHub OIDC: base infrastructure, runtime secrets, ECR images, ECS services, migrations and ALB smoke checks.

## How to test

1. Start Docker Desktop.
2. Run `make dev`; wait for service health (target: under three minutes).
3. Run `make migrate && make seed`.
4. Run `make lint typecheck test build`.
5. Run `python scripts/test_auth_flow.py` to verify magic link, dashboard session, API JWT, `GET /v1/me` and forged-cookie rejection.
6. Run `python scripts/test_rls.py` twice to verify idempotent tenant isolation against PostgreSQL.
7. Configure staging secrets and run `deploy-staging`, then `make smoke`.

## Verified locally

- All seven Compose services start from cached images in 3.78 seconds; API is exposed on `localhost:8005` and the smoke test passes.
- Alembic revisions through `0003` execute against PostgreSQL 16; the idempotent seed produces one demo tenant, one agent, three documents, two tools and 20 calls.
- Forced RLS integration passes for `tenants`, `agents` and `calls` with two tenants and a `NOBYPASSRLS` role, twice consecutively.
- Auth.js magic-link login passes through the local provider mock; a real membership JWT reaches `/v1/me`, while a forged session cookie is redirected to login.
- Terraform `fmt` and `validate` pass with AWS provider 5.100.0.
- Ruff and strict mypy pass.
- Backend suite has 12 passing tests and 82.53% coverage.
- ESLint, TypeScript and Next.js production build pass.
- GitHub repository `mariohidifira/voice_os` is connected; CI run `32203264679` passed every gate, including real PostgreSQL migrations/seed/RLS and all Docker image builds.
- GitHub environment `staging` exists and is ready for environment-scoped secrets.

## Outside / external acceptance remaining

- A real staging deployment and remote smoke test cannot be executed yet: the GitHub `staging` environment has no AWS/provider secrets, including `AWS_STAGING_ROLE_ARN`. Terraform and workflow syntax validate locally, but this is not evidence of a deployed environment.
- Production Resend delivery and Google OAuth require their staging credentials. The complete magic-link protocol is verified locally through the HTTP email mock.
