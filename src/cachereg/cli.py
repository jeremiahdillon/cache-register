"""`cachereg` command line.

Phase 0 ships the command surface and `status`; the other commands land in the phases
named in their help text (see docs/PLAN.md §10).
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import typer

from cachereg.core.paths import repo_relative
from cachereg.core.registry import load_sources
from cachereg.core.settings import SECRETS, MissingSecretError, secret_status

app = typer.Typer(no_args_is_help=True, add_completion=False, help="Cache Register — receipts for the AI economy.")


def _not_yet(phase: str) -> None:
    typer.echo(f"Not implemented yet (planned for {phase}; see docs/PLAN.md §10).", err=True)
    raise typer.Exit(code=2)


@app.command()
def fetch(
    source: str = typer.Argument(None, help="Source id; omit for all enabled sources."),
    full: bool = typer.Option(False, help="Re-fetch full history instead of the trailing window."),
) -> None:
    """Download raw data from sources into data/raw (immutable, one folder per fetch)."""
    sources = load_sources()
    ids = [source] if source else [s.id for s in sources.values() if s.enabled]
    failed = False
    for sid in ids:
        if sid not in sources:
            raise typer.BadParameter(f"unknown source {sid!r}; known: {', '.join(sources)}")
        try:
            raw = sources[sid].module("fetch").fetch(full=full)
            out = raw.write()
            typer.echo(f"  ok    {sid:<22} {len(raw.files)} file(s) -> {repo_relative(out)}")
        except MissingSecretError as e:
            failed = True
            typer.echo(f"  skip  {sid:<22} {e}", err=True)
        except Exception as e:  # noqa: BLE001 (report per source, keep going)
            failed = True
            typer.echo(f"  FAIL  {sid:<22} {type(e).__name__}: {e}", err=True)
    if failed:
        raise typer.Exit(code=1)


@app.command()
def build(as_of: str = typer.Option(None, help="YYYY-MM-DD; default today (UTC).")) -> None:
    """Rebuild staged tables and marts from raw data."""
    from cachereg.build import build as run_build

    day = date.fromisoformat(as_of) if as_of else datetime.now(UTC).date()
    report = run_build(day)
    for table, n in report.staged.items():
        typer.echo(f"  staged {table:<40} {n:>9,} rows")
    for sid, n in report.rejected.items():
        if n:
            typer.echo(f"  WARN   {sid}: {n} raw rows rejected during staging", err=True)
    for sid, v in report.vintages.items():
        flag = "  (vintage after as-of!)" if v.get("vintage_after_as_of") else ""
        typer.echo(f"  vintage {sid:<24} {v}{flag}")


@app.command()
def render(
    analysis: str = typer.Argument(..., help="Path to an analysis folder."),
    targets: str = typer.Option(None, help="Comma-separated target names; default: all in story.yaml."),
    as_of: str = typer.Option(None, help="YYYY-MM-DD; default today (UTC)."),
) -> None:
    """Render an analysis to its targets (HTML, PNG, video, …) under outputs/."""
    from pathlib import Path

    from cachereg.render import render as run_render

    day = date.fromisoformat(as_of) if as_of else datetime.now(UTC).date()
    result = run_render(Path(analysis), day, targets.split(",") if targets else None)
    typer.echo(f"  {result['title']}")
    for name, file in result["outputs"].items():
        typer.echo(f"  ok    {name:<16} {file:<22} {result['timings'][name]:>6}s")
    typer.echo(f"  -> {repo_relative(result['out_dir'])}")


@app.command()
def publish(analysis: str, check: bool = typer.Option(False, help="Only run the licensing check.")) -> None:
    """Copy rendered outputs and their manifest into the analysis's published/ folder."""
    _not_yet("Phase 4")


@app.command()
def entities(action: str = typer.Argument("check", help="check | suggest")) -> None:
    """Report or suggest canonical model/vendor mappings."""
    _not_yet("Phase 3")


@app.command()
def site(out: str = typer.Option("_site", help="Output folder (gitignored).")) -> None:
    """Build the short-link site published to GitHub Pages (cacheregister.dev/<link>)."""
    from pathlib import Path

    from cachereg.site import build_site, short_url

    for link in build_site(Path(out)):
        typer.echo(f"  {short_url(link.slug):<45} -> {link.analysis}")


@app.command()
def status() -> None:
    """Show which credentials are configured (never their values)."""
    configured = secret_status()
    for name, ok in configured.items():
        mark = "set    " if ok else "missing"
        typer.echo(f"  {mark}  {name:<30} {SECRETS[name].purpose}")


if __name__ == "__main__":
    app()
