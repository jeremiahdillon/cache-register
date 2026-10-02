"""Secrets and settings.

Secrets are read from, in order of precedence:

1. the process environment;
2. the file named by ``CACHEREG_SECRETS_FILE`` (kept outside the repo);
3. a gitignored ``.env`` at the repo root (convenient for replicators).

``CACHEREG_SECRETS_FILE`` itself may be set in the environment or in the repo ``.env``, so a
one-line ``.env`` can point at an existing secrets file without editing shell profiles.

Values are never logged, printed or written to manifests. Use :func:`redact` on any text
that might contain one (error messages, URLs) before it leaves the process.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SECRETS_FILE_ENV = "CACHEREG_SECRETS_FILE"


@dataclass(frozen=True)
class SecretSpec:
    name: str
    purpose: str
    required_for: str


SECRETS: dict[str, SecretSpec] = {
    s.name: s
    for s in [
        SecretSpec("OPENROUTER_API_KEY", "OpenRouter datasets API (any key)", "openrouter"),
        SecretSpec("ARTIFICIAL_ANALYSIS_API_KEY", "Artificial Analysis data API", "artificial_analysis"),
        SecretSpec("RAMP_DATA_API_KEY", "Ramp Data (AI Index, Ramp Rate); via the Ramp Data Partner Program", "ramp"),
        SecretSpec("SEC_EDGAR_USER_AGENT", "SEC EDGAR requires 'Name contact@example.com'", "edgar"),
        SecretSpec("HF_TOKEN", "Hugging Face (optional; raises rate limits)", "huggingface"),
    ]
}

_LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$")


class MissingSecretError(RuntimeError):
    pass


def parse_env_file(path: Path) -> dict[str, str]:
    """Parse ``KEY=value`` / ``export KEY=value`` lines; quotes are stripped, comments ignored."""
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        m = _LINE.match(raw)
        if not m:
            continue
        key, value = m.groups()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        values[key] = value
    return values


def _file_sources(env: dict[str, str]) -> list[Path]:
    repo_env = REPO_ROOT / ".env"
    pointer = env.get(SECRETS_FILE_ENV)
    if not pointer and repo_env.is_file():
        pointer = parse_env_file(repo_env).get(SECRETS_FILE_ENV)
    paths = [Path(os.path.expandvars(pointer)).expanduser()] if pointer else []
    paths.append(repo_env)
    return paths


def get_secret(name: str, env: dict[str, str] | None = None) -> str:
    """Return a secret's value, or raise :class:`MissingSecretError` naming how to set it."""
    env = dict(os.environ) if env is None else env
    if env.get(name):
        return env[name]
    for path in _file_sources(env):
        if path.is_file():
            value = parse_env_file(path).get(name)
            if value:
                return value
    spec = SECRETS.get(name)
    hint = f" ({spec.purpose})" if spec else ""
    raise MissingSecretError(
        f"{name} is not set{hint}. Set it in the environment, in the file named by "
        f"{SECRETS_FILE_ENV}, or in a repo-local .env (see .env.example)."
    )


def secret_status(env: dict[str, str] | None = None) -> dict[str, bool]:
    """Which known secrets are configured — booleans only, never values."""
    status = {}
    for name in SECRETS:
        try:
            get_secret(name, env)
            status[name] = True
        except MissingSecretError:
            status[name] = False
    return status


def redact(text: str, env: dict[str, str] | None = None) -> str:
    """Replace any configured secret value appearing in ``text`` with ``[REDACTED:NAME]``."""
    for name in SECRETS:
        try:
            value = get_secret(name, env)
        except MissingSecretError:
            continue
        if len(value) >= 6:
            text = text.replace(value, f"[REDACTED:{name}]")
    return text
