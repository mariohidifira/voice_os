# Phase 4 Report

Status date: 2026-08-25

## Implemented in this round

- `POST /v1/integrations/whatsapp` to connect a WhatsApp Cloud API number to an agent
- `GET /v1/integrations` now returns sanitized Google and WhatsApp integration records
- `GET /webhooks/whatsapp` for Meta verification challenge
- `POST /webhooks/whatsapp` for signed inbound webhook ingestion
- `POST /internal/whatsapp/tick` to claim queued inbound messages, generate a deterministic reply, persist turns, and publish live events
- `POST /v1/calls/{call_id}/whatsapp-handoff` to let an operator send text into an active WhatsApp conversation
- `POST /v1/simulations`, `GET /v1/simulations/{id}`, and `GET /v1/simulations/{id}/yaml`
- repository + memory/postgres contracts already added in the WIP are now exercised by the API layer
- provider-backed WhatsApp runtime in `apps/api/voiceos_api/whatsapp_runtime.py`
  - Deepgram-first audio transcription with OpenAI fallback
  - Anthropic reply generation with optional tool use
  - ElevenLabs OGG audio synthesis with preview fallback
  - shared runtime tool execution path reused by `POST /internal/whatsapp/tick`
- dashboard surfaces in `apps/web/app/app/[tenantSlug]/dashboard.tsx` for:
  - WhatsApp integration settings
  - operator text handoff inside the live view for WhatsApp calls
  - a dedicated simulator section with report and YAML output
- frontend helper coverage in `apps/web/lib/dashboard-phase4.ts` and `apps/web/lib/dashboard-phase4.test.ts`
  - WhatsApp integration payload building
  - operator handoff request building
  - simulator payload/YAML path building
  - deterministic simulation metric formatting
- Playwright spec for Phase 4 interaction coverage in `apps/web/e2e/phase4-whatsapp-simulator.spec.ts`
  - WhatsApp connection through dashboard settings
  - simulator execution through dashboard UI
  - live WhatsApp handoff through the `/live` surface
- Playwright config stabilization in `apps/web/playwright.config.ts`
  - local base URL aligned to `localhost`
  - `webServer` readiness target and auth URLs aligned to the same host
- Next.js dev-origin stabilization in `apps/web/next.config.ts`
  - `allowedDevOrigins` now includes both `http://localhost:3100` and `http://127.0.0.1:3100`
- backend regression fix in `apps/api/voiceos_api/routes.py`
  - WhatsApp handoff now accepts `refresh_token_secret_id` whether it arrives as native `UUID` or serialized string
- OpenAPI artifact regenerated in `packages/shared-ts/openapi.json`
- deterministic Phase 4 coverage expanded with API/runtime tests for:
  - WhatsApp connect + listing
  - webhook verification + signed inbound ingest
  - async tick processing with tool execution
  - audio transcription/reply + text+audio send path
  - operator handoff route
  - simulation report + YAML export

## Validation completed on 2026-08-25

- `ruff check --no-cache apps/api/voiceos_api/routes.py apps/api/voiceos_api/whatsapp.py apps/api/voiceos_api/simulator.py`
- `mypy G:\DEV\VOICE_OS\apps\api\voiceos_api`
- `pytest -q G:\DEV\VOICE_OS\tests\test_api.py`
- `pytest -q G:\DEV\VOICE_OS\tests\test_whatsapp_runtime.py G:\DEV\VOICE_OS\tests\test_api.py`
- `npm run typecheck` in `apps/web`
- `npm run lint` in `apps/web`
- `npm run build` in `apps/web`
- `npm test --workspace=@voiceos/dashboard`
- `npm run typecheck --workspace=@voiceos/dashboard`
- `pytest -q tests/test_api.py -k "whatsapp_handoff_route_sends_operator_message or whatsapp_handoff_route_accepts_string_secret_id or simulation_endpoints_return_report_and_yaml"`

Result:

- lint passed
- typecheck passed
- `23` API tests passed
- `33` runtime + API tests passed after the provider-backed WhatsApp worker changes
- web app typecheck passed
- web app lint passed
- dashboard Vitest suite passed with `13` tests on Tuesday, August 25, 2026
- dashboard typecheck passed on Tuesday, August 25, 2026
- targeted backend Phase 4 regression/API checks passed with `3` tests on Tuesday, August 25, 2026
- Next.js production build reached successful compile and static page generation on Tuesday, August 25, 2026

Additional evidence gathered on Tuesday, August 25, 2026:

- the local Playwright Phase 4 flow reached the handoff UI, exposed a real backend `HTTP 500`, and that handoff defect was then fixed and locked by regression coverage
- `apps/web/e2e/phase4-whatsapp-simulator.spec.ts` later passed locally against the live localhost stack after the host/dev-origin alignment
- direct local diagnosis confirmed:
  - `next dev --port 3100` starts successfully
  - `GET /login` returns `200`
  - the prior local E2E blocker was the auth/dev-origin path between `127.0.0.1` and `localhost`
  - Next.js emitted a cross-origin dev warning for requests from `127.0.0.1` to `/_next/*`
  - the dashboard config was updated to prefer `localhost` for the web flow and to explicitly allow both local dev origins
- `python scripts/repro_phase4_handoff.py` returned `200` with a stub `provider_message_id`, confirming the handoff route on the Postgres-backed local stack after the latest fixes
- `reports/phase4-local-acceptance.json` now captures a consolidated local acceptance run where the webhook stub test, targeted handoff API regressions, direct handoff reproducer, and Playwright dashboard flow all passed
- the consolidated local acceptance runner is now green end to end when executed outside the managed sandbox restrictions on `G:\`
- `PHASE-4-REMOTE-RUNBOOK.md` and `scripts/check_phase4_remote_ready.ps1` now document and diagnose the first remote GitHub Actions execution path for the Phase 4 nightly workflow
- the remote diagnosis on Tuesday, August 25, 2026 confirmed the remaining gap is repository/auth access in this executor, not a missing local workflow implementation:
  - `gh api user` returned `401`
  - `gh api repos/mariohidifira/voice_os` returned `404`
  - `git ls-remote origin` failed with `SEC_E_NO_CREDENTIALS`

## Provider and environment status

- external provider acquisition is still pending and remains non-blocking for local development
- WhatsApp Cloud API, Anthropic, Deepgram, and ElevenLabs should stay marked as pending until credentials and provider-side setup are delivered
- local implementation therefore keeps deterministic fallbacks for continuity and testability

## Acceptance status against `docs/voiceos-spec-v1.0/voice-agent-spec/14-fases.md`

- `tools funcionam pelo WhatsApp`: covered locally by deterministic tests
- `handoff humano funciona`: covered locally by deterministic tests
- `simulador roda 20 conversas e gera relatório`: covered locally by deterministic tests
- `mensagem de áudio no WhatsApp respondida com texto+áudio`: covered locally for behavior, but not yet benchmarked at real provider p50 `<= 8 s`
- `suíte nightly inclui casos WhatsApp`: implemented at CI level with a dedicated nightly workflow for deterministic WhatsApp/simulator coverage; still pending first successful run in GitHub Actions

## Current Phase 4 completion estimate

- local implementation and validation: ~94%
- overall project roadmap completion: ~88%

## Current limitations

- WhatsApp processing now has a real STT/LLM/TTS path, but still falls back deterministically when provider state is unavailable or errors
- audio reply upload now prefers an OGG path for WhatsApp when ElevenLabs is available, with MP3 fallback only when needed
- the panel UI now has helper-level automated frontend coverage plus a dedicated Playwright spec for the WhatsApp/simulator/handoff flow
- the new nightly workflow still needs its first successful remote execution as acceptance evidence
- real provider latency measurement for WhatsApp audio p50 is still pending
- end-to-end staging verification remains blocked by pending provider setup
- this specific managed executor still requires an out-of-sandbox launch for the Node/Playwright portion because sandboxed access to `G:\` remains restricted

Structured local environment blocker now persisted in `reports/phase4-local-acceptance.json`,
`reports/phase4-evidence-summary.json`, `reports/phase4-evidence-bundle.manifest.json`,
`reports/final-local-audit.json`, `reports/final-refresh-status.json`, and
`reports/final-handoff-bundle.manifest.json`:

- `type: node_g_drive_eperm`
- `detail: Node/Playwright cannot resolve G:\ in this executor`
- `current_gap: phase4_playwright_executor_blocked`

## Remaining work to fully close Phase 4

- confirm remote GitHub Actions execution of the Phase 4 nightly workflow and retain artifacts
- measure real provider-backed WhatsApp audio reply p50 against the `<= 8 s` target
- produce final acceptance evidence against the Phase 4 goals in `docs/voiceos-spec-v1.0/voice-agent-spec/14-fases.md`

## Update on 2026-08-25 after the latest reruns

- `apps/web/e2e/phase4-whatsapp-simulator.spec.ts` passed locally with Playwright against the live localhost stack
- `tests/test_whatsapp_gateway.py` passed and now covers the dev/test WhatsApp stub path for fake local tokens
- `python scripts/repro_phase4_handoff.py` returned `200` with a stub `provider_message_id`, confirming the handoff route works on the Postgres-backed local stack after the latest fixes
- `scripts/run_phase4_local_acceptance.py`, `scripts/run_phase4_local_acceptance.ps1`, and `make phase4-acceptance-local` were added to consolidate local acceptance evidence into `reports/phase4-local-acceptance.json`
- `scripts/run_phase4_playwright.ps1` and `scripts/run_phase4_local_acceptance.py` were hardened so the local acceptance flow can reuse a stable Playwright launch path
- the consolidated runner passed end to end on Tuesday, August 25, 2026 when executed outside the managed sandbox, including the dashboard E2E step
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_phase4_local_acceptance.ps1` also passed on Tuesday, August 25, 2026 as the native Windows entry point for the same acceptance flow
- `npm run phase4:acceptance:local` also passed on Tuesday, August 25, 2026 as a root-level shortcut for the same consolidated acceptance flow
- `.github/workflows/phase4-nightly-whatsapp.yml` now runs the expanded deterministic WhatsApp suite, then the consolidated acceptance runner, and uploads both the JUnit XML and `reports/phase4-local-acceptance.json` as artifacts
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check_phase4_remote_ready.ps1` ran on Tuesday, August 25, 2026 and reproduced the current GitHub access blockers with explicit diagnostics
- `reports/phase4-remote-readiness.json` now persists the same remote-readiness diagnosis in machine-readable form with `passed: false` and step-by-step evidence
- `npm run phase4:remote:ready` also passed as the root-level shortcut for the same remote-readiness diagnostic flow on Tuesday, August 25, 2026
- `make phase4-remote-ready` is now available as the GNU Make entry point for the same diagnostic flow, and `PHASE-4-REMOTE-RUNBOOK.md` was aligned to document the PowerShell, npm, and Make entry points together
- `npm run generate-types` passed on Tuesday, August 25, 2026 and `.github/workflows/phase4-nightly-whatsapp.yml` now uses that same validated root command instead of a Makefile-only path
- `reports/phase4-evidence-summary.json` now consolidates the local acceptance and remote-readiness evidence into a single machine-readable status artifact; the current `next_gap` is `remote_repo_access`
- `python scripts/build_phase4_evidence_summary.py` and `npm run phase4:evidence:summary` both passed on Tuesday, August 25, 2026 and now provide a single root entry point for the Phase 4 evidence summary
- `scripts/run_phase4_evidence_bundle.ps1` and `npm run phase4:evidence:bundle` both passed on Tuesday, August 25, 2026 and now refresh the remote-readiness report plus the consolidated Phase 4 evidence summary in one step
- `scripts/build_phase4_evidence_summary.py` was also validated on Tuesday, August 25, 2026 in the no-remote-report scenario that matches the GitHub Actions nightly path; in that case it emits `next_gap: "remote_readiness_report_missing"` instead of failing
- `scripts/build_phase4_evidence_package.py` and `npm run phase4:evidence:package` both passed on Tuesday, August 25, 2026 and now produce a material handoff artifact at `reports/phase4-evidence-bundle.zip` with a matching manifest in `reports/phase4-evidence-bundle.manifest.json`
- `.github/workflows/phase4-nightly-whatsapp.yml` now also builds and uploads the Phase 4 evidence package (`reports/phase4-evidence-bundle.zip` + manifest) alongside the XML and JSON artifacts
- `reports/phase4-evidence-bundle.manifest.json` now also carries SHA-256 hashes for every included evidence file, the SHA-256 of the ZIP itself, and the propagated `next_gap` (`remote_repo_access`) from the consolidated evidence summary
- the same manifest now also carries the propagated `environment_blocker` from local Phase 4 acceptance, so the packaged evidence identifies the executor-level `G:\` / Node Playwright failure directly
- `scripts/verify_phase4_evidence_package.py` and `npm run phase4:evidence:verify` both passed on Tuesday, August 25, 2026 and confirmed that the ZIP, the manifest, and every included file hash/size are internally consistent (`passed: true`)
- local Phase 4 completion estimate is now ~94%
- overall project roadmap completion estimate is now ~88%
- the highest-value remaining proof is the first successful GitHub Actions artifact for the Phase 4 nightly workflow plus real provider-backed latency evidence
