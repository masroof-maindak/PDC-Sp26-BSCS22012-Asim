lint:
	uv run ruff check

fmt:
	uv run ruff check --select I --fix
	uv run ruff format

