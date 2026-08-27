# Phase 5 Report

Status date: 2026-08-25

## Implemented on Tuesday, August 25, 2026

- `tenant.settings` now accepts structured Phase 5 branding/widget fields via API schema:
  - `branding.product_name`
  - `branding.logo_url`
  - `branding.favicon_url`
  - `branding.primary_color`
  - `branding.accent_color`
  - `branding.email_from_name`
  - `branding.custom_domain`
  - `widget.button_label`
  - `widget.theme`
  - `widget.position`
  - `widget.livekit_module_url`
- dashboard helper layer for Phase 5 in `apps/web/lib/dashboard-phase5.ts`
  - tenant settings payload builder
  - deterministic HTML widget snippet builder
  - deterministic React/Next snippet builder
  - snippets now point to the canonical public widget session endpoint:
    `/v1/public/tenants/{tenant_id}/widget/sessions`
  - snippets now optionally expose `livekitModuleUrl` for pinned/self-hosted browser bundles
- helper coverage in `apps/web/lib/dashboard-phase5.test.ts`
- dashboard Phase 5 surfacing in `apps/web/app/app/[tenantSlug]/dashboard.tsx`
  - settings form now sends branding/widget payloads
  - channels tab now exposes copyable widget embed snippets
  - latest public/widget API key is retained in-session so the user can copy a real snippet immediately after key creation
  - tenant settings now expose `livekit_module_url` so embeds can pin or self-host the LiveKit browser bundle
- public widget session backend in `apps/api/voiceos_api/routes.py`
  - validates `vos_pk_*` keys inside the requested tenant
  - enforces allowed origins for public/widget keys
  - provisions current-version web sessions without dashboard auth
  - supports public widget session delete/cancel for graceful client shutdown
- repository lookup support for hashed public API keys in `apps/api/voiceos_api/repository.py`
- shared contract alignment:
  - `packages/shared-ts/openapi.json` now includes the public widget session routes
  - `packages/shared-ts/src/openapi.ts` was synchronized to expose those routes in the typed client surface
  - `packages/shared-ts/dist/openapi.d.ts` was synchronized so the exported declaration surface matches the backend contract
- `packages/widget` upgraded from a placeholder button to a usable SDK:
  - configurable `theme`, `position`, `buttonLabel`, `zIndex`
  - `mount`, `unmount`, `open`, `close`, `update`
  - browser events `voiceos:start` and `voiceos:end`
  - auto-bootstrap from `<script type="module" ... data-*>`
  - global `window.VoiceOSWidget` exposure for host pages
  - public session provisioning via `vos_pk_*` + `X-API-Key`
  - real LiveKit room connection, microphone enablement, mute toggle, and public-session shutdown
  - dynamic browser-side LiveKit module loading with a configurable module URL
- SDK usage guide in `packages/widget/README.md`
- local host example in `packages/widget/examples/host-page.html`
- browser widget bundle pipeline now generates `packages/widget/dist/voiceos.js`, enforces the
  `<= 60 KB gz` budget, and synchronizes the hosted asset to `apps/web/public/voiceos.js` before
  dashboard builds
- hosted asset readiness verifier in `scripts/check_phase5_hosted_asset_ready.py`
  - writes `reports/phase5-hosted-asset-readiness.json`
  - checks snippet path, dashboard prebuild wiring, widget build/size scripts, host example, docs,
    public target directory, and whether the hosted asset artifacts are already present
- hosted asset runbook in `PHASE-5-HOSTED-ASSET-RUNBOOK.md`
- cross-phase local handoff in `FINAL-HANDOFF-2026-08-25.md`
- local acceptance verifier in `scripts/check_phase5_acceptance.py`
  - writes `reports/phase5-acceptance-summary.json`
  - covers the static host example, React/Next example, hosted snippet path, and the focused API
    proof for allowed-origin + public widget key enforcement
- evidence bundle scripts for the hosted asset rollout:
  - `scripts/build_phase5_evidence_package.py`
  - `scripts/verify_phase5_evidence_package.py`
  - outputs:
    - `reports/phase5-evidence-bundle.zip`
    - `reports/phase5-evidence-bundle.manifest.json`
- phase/spec docs updated to reflect the current widget contract:
  - `vos_pk_*` public key prefix
  - public endpoint `/v1/public/tenants/{tenant_id}/widget/sessions`
  - browser events `voiceos:start` / `voiceos:end`
  - optional `livekitModuleUrl`
- focused API proof now covers:
  - tenant branding/widget persistence
  - member/API-key tenant scoping
  - authenticated session lifecycle
  - public widget session creation with origin enforcement
  - public widget session delete/cancel

## Still pending

- production deployment proof that the hosted `voiceos.js` path is reachable externally
- staging proof for custom-domain TLS
- host-page Lighthouse impact measurement
- real end-to-end host-site acceptance outside the managed local executor

The canonical Node build still cannot resolve `G:\` in this executor. This no longer blocks
local Phase 5 acceptance because the repository-local native esbuild fallback consumes the
self-contained TypeScript entrypoint through stdin and applies the same browser target,
minification, legal-comment, and gzip-budget rules.

## Latest local evidence on Thursday, August 27, 2026

- `npm --prefix G:\DEV\VOICE_OS run phase5:widget:fallback` generated:
  - `packages/widget/dist/voiceos.js`
  - `apps/web/public/voiceos.js`
  - `packages/widget/dist/size.json`
- current bundle evidence:
  - bytes: `10,431`
  - gzip bytes: `3,686`
  - gzip budget: `61,440`
  - SHA-256: `cf0dd9118e4e74d9574e07bbba3d6b8d8b02a1aeb3aec9d2bf3111acf2a9039c`
- `reports/phase5-hosted-asset-readiness.json` reports:
  - `passed: true`
  - `next_gap: null`
  - `environment_blocker: null`
  - dist and hosted assets are byte-identical
  - bytes, SHA-256, deterministic gzip size, and size budget match `size.json`
- `reports/phase5-acceptance-summary.json` reports `passed: true` and `pending: []`
- the Phase 5 evidence bundle now includes both generated JavaScript files, `size.json`, and the
  native fallback script so the local proof is portable and independently hash-verifiable
