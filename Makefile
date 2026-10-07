# Thin wrappers. Installs go through Socket Firewall (sfw) when it is available.
SFW := $(shell command -v sfw >/dev/null 2>&1 && echo sfw)

.PHONY: setup hooks test lint format guard check status install-schedule

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

# Daily `cachereg fetch --due` via launchd (PLAN §4.5). Renders the template into your LaunchAgents
# folder and prints the commands to load or unload it; it never loads the agent itself.
SCHEDULE_LABEL := dev.cacheregister.fetch
SCHEDULE_HOUR ?= 5
SCHEDULE_MINUTE ?= 47
SCHEDULE_PLIST := $(HOME)/Library/LaunchAgents/$(SCHEDULE_LABEL).plist
SCHEDULE_LOGS := $(HOME)/Library/Logs/cachereg

install-schedule:
	@test -x .venv/bin/cachereg || { echo "run 'make setup' first"; exit 1; }
	@mkdir -p "$(dir $(SCHEDULE_PLIST))" "$(SCHEDULE_LOGS)"
	@sed -e 's|@CACHEREG@|$(CURDIR)/.venv/bin/cachereg|' -e 's|@REPO@|$(CURDIR)|' \
		-e 's|@LOG_DIR@|$(SCHEDULE_LOGS)|' -e 's|@HOUR@|$(SCHEDULE_HOUR)|' -e 's|@MINUTE@|$(SCHEDULE_MINUTE)|' \
		ops/launchd/cachereg.fetch.plist.template > "$(SCHEDULE_PLIST)"
	@plutil -lint "$(SCHEDULE_PLIST)"
	@echo "Secrets the agent will see (it starts without your shell environment):"
	@env -i HOME="$(HOME)" PATH=/usr/bin:/bin .venv/bin/cachereg status
	@echo
	@echo "Load:    launchctl bootstrap gui/$$(id -u) \"$(SCHEDULE_PLIST)\""
	@echo "Run now: launchctl kickstart gui/$$(id -u)/$(SCHEDULE_LABEL)"
	@echo "Unload:  launchctl bootout gui/$$(id -u)/$(SCHEDULE_LABEL)"
	@echo "Logs:    $(SCHEDULE_LOGS)/fetch.log"
