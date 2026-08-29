# Commercial readiness gate

This document is the release gate for the VoiceOS commercial product. A green
local test suite is necessary, but it is not sufficient to call a production
release ready.

## Verified in the repository

- Multi-tenant API, RBAC, agent versions, draft/publish/rollback and tenant
  isolation are implemented.
- WebRTC, phone, WhatsApp, billing, public API, exports, LGPD workflows,
  analytics, widget and configurable deterministic/hybrid flows are implemented
  with local automated coverage.
- Python regression suite: `173 passed` (latest local run, including worker
  production-configuration checks).
- Local backend coverage: `80%` with the repository's `--cov-fail-under=80` gate.
- `ruff check .`: passed after commit `789aa95`.
- Docker health was previously verified at `http://localhost:8005/health` with
  database, Redis, S3 and LiveKit components healthy.
- The repository is clean and `master` is synchronized with `origin/master` at the
  latest pushed commit.

- The API and `agent-worker` both fail fast on placeholder production settings;
  development/test environments retain their documented local defaults.

### Latest local smoke (2026-08-28)

- Credential Manager lookup: LiveKit URL/key/secret, OpenAI, Anthropic,
  ElevenLabs, Google, Cartesia, Cerebras and OpenRouter available (values not
  printed).
- OpenAI `GET /v1/models`: HTTP 200.
- ElevenLabs `GET /v1/voices`: HTTP 200.
- LiveKit worker registered as `voiceos-agent` in the Brazil region.
- API `/health`: database, Redis, S3 and LiveKit token checks all `true`.

## Release blockers requiring external evidence

The current reconciliation audit is recorded in
`reports/commercial-gate-audit-2026-08-29.json`. Some older phase/handoff
reports contain historical artifact checks and may say `complete=true`; they
do not replace the five production gates below and are not, by themselves,
evidence that the commercial release is ready.

The product must not be labelled production-ready until each item below has a
dated report attached under `reports/`:

1. **Real voice staging**: 50 LiveKit calls using the configured STT, LLM and
   TTS providers; voice-to-voice p50/p95, barge-in success, recording/Egress and
   effective provider cost meet the limits in `docs/14-fases.md`.
2. **PSTN**: real inbound/outbound Twilio + LiveKit SIP call, DTMF, transfer,
   voicemail and a 50-room load run.
3. **Billing**: Stripe test lifecycle from trial through upgrade, usage,
   overage, failed payment, suspension and reactivation.
4. **Operations**: AWS staging deployment, migrations, backups/restore,
   Grafana/Sentry alerts and incident drill.
5. **Distribution**: external widget host-site test, origin rejection,
   custom-domain TLS and Lighthouse impact measurement.

## Required secrets and accounts

The checks above require credentials for LiveKit, Twilio, Stripe, AWS/S3,
Grafana/Sentry and the selected voice providers. Secrets must be supplied via
the deployment secret store or Windows Credential Manager; never commit them or
place them in reports.

## Final release decision

Until all five external gates have reports and the acceptance workflow is green,
the correct status is **MVP/homologation ready, production release pending**.
This distinction is intentional: passing local tests proves implementation
quality, not provider, network, billing or operational behavior in production.
