# Thin wrappers. Installs go through Socket Firewall (sfw) when it is available.
SFW := $(shell command -v sfw >/dev/null 2>&1 && echo sfw)

.PHONY: setup hooks test lint format guard check status

setup: hooks
	$(SFW) uv sync --frozen

hooks:
	git config core.hooksPath .githooks

test:
	uv run --frozen pytest -q

lint:
	uv run --frozen ruff check
	uv run --frozen ruff format --check

format:
	uv run --frozen ruff format
	uv run --frozen ruff check --fix

guard:
	python3 scripts/guard.py --tracked

check: guard lint test

status:
	uv run --frozen cachereg status
