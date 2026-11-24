.PHONY: install verify eval up down specs

install:
	cd services/ai && uv sync
	cd services/gateway && npm ci

verify:
	./scripts/verify.sh

eval:
	./scripts/eval.sh

up:
	docker compose -f deploy/compose.yaml up -d --build

down:
	docker compose -f deploy/compose.yaml down

specs:
	openspec validate --all
