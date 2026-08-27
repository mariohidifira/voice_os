# External Execution Checklist - 2026-08-25

This checklist captures the exact remaining work that must happen outside the current managed executor.

## Delivery artifacts to identify before external execution

- Phase 4 evidence bundle:
  - `reports/phase4-evidence-bundle.zip`
  - SHA-256: `cfc8756d09b2ca22ebd7b7d59894c53b79ddfde891f0c4ec18c2a35b555fedee`
  - bytes: `11300`
- Phase 5 evidence bundle:
  - `reports/phase5-evidence-bundle.zip`
  - SHA-256: `1fdfd5a76d2f7e38570076cdb9252cb354c7b88f1e2289f93c7ac0d149eef8e0`
  - bytes: `29899`
- Final handoff bundle manifest:
  - `reports/final-handoff-bundle.manifest.json`
  - bundle path: `reports/final-handoff-bundle.zip`

## Phase 4

Current gap: `remote_repo_access`

Environment blocker:

- type: `node_g_drive_eperm`
- detail: Node/Playwright cannot resolve G:\ in this executor
- current gap mapping: `phase4_playwright_executor_blocked`

1. Restore GitHub and repository credentials for `mariohidifira/voice_os`
2. Run the Phase 4 nightly workflow in GitHub Actions
3. Retain the uploaded artifacts from the first successful nightly run
4. After provider credentials are available, run the real WhatsApp audio latency measurement and compare it against the `<= 8 s p50` target

Commands:

- `npm --prefix G:\DEV\VOICE_OS run phase4:remote:ready`
- `gh workflow run phase4-nightly-whatsapp.yml --repo mariohidifira/voice_os`
- `gh run list --repo mariohidifira/voice_os --workflow phase4-nightly-whatsapp.yml --limit 5`
- `python scripts/verify_phase4_remote_artifact.py <artifact_dir>`

## Phase 5

Current gap: `external_deploy_and_host_validation`

1. Deploy the hosted asset and verify `/voiceos.js` is externally reachable
2. Validate custom-domain TLS in staging
3. Collect host-site Lighthouse impact evidence

Commands:

- `npm --prefix G:\DEV\VOICE_OS run phase5:widget:fallback`
- `npm --prefix G:\DEV\VOICE_OS run phase5:asset:ready`
- `npm --prefix G:\DEV\VOICE_OS run phase5:acceptance`
- `python scripts/check_phase5_external_delivery.py --base-url https://<host>`
- `npm --prefix G:\DEV\VOICE_OS run phase5:evidence:package`
- `npm --prefix G:\DEV\VOICE_OS run phase5:evidence:verify`

## External capabilities required

- GitHub/repository access
- Provider credentials and live accounts
- Reachable staging/production deployment surface

## Machine-readable companion

- `reports/external-execution-checklist.json`

## Verifiers to run during closeout

- Phase 4 remote artifact:
  - `python scripts/verify_phase4_remote_artifact.py <artifact_dir>`
  - output: `reports/phase4-remote-artifact-verification.json`
- Phase 5 external delivery:
  - `python scripts/check_phase5_external_delivery.py --base-url https://<host> --expected-host <domain>`
  - output: `reports/phase5-external-delivery.json`
