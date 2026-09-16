.PHONY: up down test api-test web-test lint local-ai
up:
	docker compose up -d --build

down:
	docker compose down

local-ai:
	docker compose --profile local-ai up -d --build

api-test:
	cd services/api && pytest

web-test:
	cd apps/web && npm test

test: api-test web-test

lint:
	cd services/api && ruff check app tests && mypy app
	cd apps/web && npm run lint && npm run typecheck
