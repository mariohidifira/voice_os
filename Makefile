.PHONY: dev test lint typecheck build migrate seed smoke generate-types
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
