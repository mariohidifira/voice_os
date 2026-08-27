.PHONY: dev test lint typecheck build migrate seed smoke generate-types stripe-sync phase4-acceptance-local phase4-remote-ready phase4-remote-artifact phase4-evidence-summary phase4-evidence-bundle phase4-evidence-package phase4-evidence-verify phase5-widget-fallback phase5-asset-ready phase5-external-delivery phase5-acceptance phase5-evidence-package phase5-evidence-verify final-handoff final-package final-verify final-audit final-external-checklist final-external-closeout final-refresh
dev:
	docker compose up --build
test:
	pytest --cov=voiceos_api --cov=voiceos_shared --cov-report=term-missing --cov-fail-under=80
	npm test --workspaces --if-present
lint:
	ruff check .
	npm run lint --workspaces --if-present
typecheck:
	mypy
	npm run typecheck --workspaces --if-present
build:
	npm run build --workspaces --if-present
migrate:
	alembic -c apps/api/alembic.ini upgrade head
seed:
	python apps/api/scripts/seed.py
smoke:
	python scripts/smoke.py
generate-types:
	python scripts/generate_openapi.py
	npm run generate --workspace=@voiceos/shared
stripe-sync:
	python scripts/stripe_sync.py
phase4-acceptance-local:
	python scripts/run_phase4_local_acceptance.py
phase4-remote-ready:
	powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check_phase4_remote_ready.ps1
phase4-remote-artifact:
	python scripts/verify_phase4_remote_artifact.py
phase4-evidence-summary:
	python scripts/build_phase4_evidence_summary.py
phase4-evidence-bundle:
	powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_phase4_evidence_bundle.ps1
phase4-evidence-package:
	python scripts/build_phase4_evidence_package.py
phase4-evidence-verify:
	python scripts/verify_phase4_evidence_package.py
phase5-widget-fallback:
	python scripts/build_widget_bundle_fallback.py
phase5-asset-ready:
	python scripts/check_phase5_hosted_asset_ready.py
phase5-external-delivery:
	python scripts/check_phase5_external_delivery.py
phase5-acceptance:
	python scripts/check_phase5_acceptance.py
phase5-evidence-package:
	python scripts/build_phase5_evidence_package.py
phase5-evidence-verify:
	python scripts/verify_phase5_evidence_package.py
final-handoff:
	python scripts/build_final_handoff_summary.py
final-package:
	python scripts/build_final_handoff_package.py
final-verify:
	python scripts/verify_final_handoff_package.py
final-audit:
	python scripts/run_final_local_audit.py
final-external-checklist:
	python scripts/build_external_execution_checklist.py
final-external-closeout:
	python scripts/check_external_closeout_complete.py
final-refresh:
	python scripts/refresh_final_handoff.py
