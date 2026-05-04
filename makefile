run:
	uv run uvicorn src.main:app --reload

test:
	uv run src/test_circuit_breaker.py

lint:
	uv run ruff check

fmt:
	uv run ruff check --select I --fix
	uv run ruff format

