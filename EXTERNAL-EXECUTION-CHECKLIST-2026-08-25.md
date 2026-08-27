# External Execution Checklist - 2026-08-25

This checklist captures the exact remaining work that must happen outside the current managed executor.

## Delivery artifacts to identify before external execution

- Phase 4 evidence bundle:
  - `reports/phase4-evidence-bundle.zip`
  - SHA-256: `ad83d022e97c63169fa552b68496c4bc0659ff22017581a24af9dff6bca104df`
  - bytes: `11269`
- Phase 5 evidence bundle:
  - `reports/phase5-evidence-bundle.zip`
  - SHA-256: `18f599557dd66993d48e6cff78c83f915998bc12535d012eeb24140afb0d49a0`
  - bytes: `29783`
- Final handoff bundle manifest:
  - `reports/final-handoff-bundle.manifest.json`
  - bundle path: `reports/final-handoff-bundle.zip`

## Phase 4

Current gap: `None`

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

Current gap: `None`


Commands:

- `npm --prefix G:\DEV\VOICE_OS run phase5:widget:fallback`
- `npm --prefix G:\DEV\VOICE_OS run phase5:asset:ready`
- `npm --prefix G:\DEV\VOICE_OS run phase5:acceptance`
- `python scripts/check_phase5_external_delivery.py --base-url https://<host>`
- `npm --prefix G:\DEV\VOICE_OS run phase5:evidence:package`
- `npm --prefix G:\DEV\VOICE_OS run phase5:evidence:verify`

## External capabilities required


## Machine-readable companion

- `reports/external-execution-checklist.json`

## Verifiers to run during closeout

- Phase 4 remote artifact:
  - `python scripts/verify_phase4_remote_artifact.py <artifact_dir>`
  - output: `reports/phase4-remote-artifact-verification.json`
- Phase 5 external delivery:
  - `python scripts/check_phase5_external_delivery.py --base-url https://<host> --expected-host <domain>`
  - output: `reports/phase5-external-delivery.json`
