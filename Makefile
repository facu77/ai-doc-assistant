.PHONY: install verify eval up down specs test-integration

install:
	cd services/ai && uv sync
	cd services/gateway && npm ci

verify:
	./scripts/verify.sh

eval:
	./scripts/eval.sh

# Tests marcados `integration` (modelo e5 real; proveedores pagos solo si hay clave en el entorno).
test-integration:
	cd services/ai && uv run pytest -m integration
	# pytest sale con 5 si no hay tests marcados: en ingest eso no es un fallo.
	if [ -f pipelines/ingest/pyproject.toml ]; then \
		cd pipelines/ingest && { uv run pytest -m integration; rc=$$?; [ $$rc -eq 0 ] || [ $$rc -eq 5 ]; }; \
	fi

up:
	docker compose -f deploy/compose.yaml up -d --build

down:
	docker compose -f deploy/compose.yaml down

specs:
	openspec validate --all
