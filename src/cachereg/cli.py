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


def _day(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


@app.command()
def fetch(
    sources: list[str] = typer.Argument(None, help="Source ids; omit for all enabled sources."),
    full: bool = typer.Option(False, help="Re-fetch full history instead of the trailing window."),
) -> None:
    """Download raw data from sources into data/raw (immutable, one folder per fetch)."""
    known = load_sources()
    ids = sources or [s.id for s in known.values() if s.enabled]
    unknown = [s for s in ids if s not in known]
    if unknown:
        raise typer.BadParameter(f"unknown source(s) {', '.join(unknown)}; known: {', '.join(known)}")
    failed = False
    for sid in ids:
        try:
            raw = known[sid].module("fetch").fetch(full=full)
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
def build(
    as_of: str = typer.Option(None, help="YYYY-MM-DD; default today (UTC)."),
    sources: str = typer.Option(None, help="Comma-separated source ids; default: every source with data."),
) -> None:
    """Rebuild staged tables and marts from raw data (only marts whose inputs are available)."""
    from cachereg.build import build as run_build

    report = run_build(_day(as_of) or datetime.now(UTC).date(), sources.split(",") if sources else None)
    for table, n in report.staged.items():
        typer.echo(f"  staged  {table:<40} {n:>9,} rows")
    for sid, n in report.rejected.items():
        if n:
            typer.echo(f"  WARN    {sid}: {n} raw rows rejected during staging", err=True)
    for sid, v in report.vintages.items():
        flag = "  (vintage after as-of!)" if v.get("vintage_after_as_of") else ""
        typer.echo(f"  vintage {sid:<24} {v['fetch_date']}{flag}")
    typer.echo(
        f"  marts   built: {', '.join(report.marts_built) or '-'}; skipped: {', '.join(report.marts_skipped) or '-'}"
    )


@app.command()
def render(
    folder: str = typer.Argument(..., help="A receipt (receipts/<topic>) or exploration (explore/<dated>)."),
    as_of: str = typer.Option(None, help="YYYY-MM-DD. Receipts: default the pinned date; a new date is saved."),
    targets: str = typer.Option(None, help="Explorations only: comma-separated target names."),
    force: bool = typer.Option(False, help="Receipts: re-render even if data and code are unchanged."),
) -> None:
    """Render every visual. Receipts write to their committed output/; explorations to outputs/."""
    from pathlib import Path

    from cachereg.render import render as run_render

    r = run_render(Path(folder), _day(as_of), targets=targets.split(",") if targets else None, force=force)
    typer.echo(f"  {r.title}")
    if r.skipped:
        typer.echo("  up to date (data and code unchanged) — use --force to re-render")
    for name in r.outputs:
        typer.echo(f"  ok        {name}")
    for name, why in r.withheld.items():
        typer.echo(f"  withheld  {name}: {why}")
    typer.echo(f"  -> {repo_relative(r.out_dir)}")


@app.command()
def reproduce(
    receipt: str = typer.Argument(..., help="receipts/<topic>"),
    latest: bool = typer.Option(False, help="Reproduce the method on today's data instead of the pinned date."),
    no_fetch: bool = typer.Option(False, help="Use raw data already downloaded."),
) -> None:
    """Rebuild one receipt on its own (only its sources and marts) and compare with the committed run."""
    from pathlib import Path

    from cachereg.reproduce import reproduce as run_reproduce

    r = run_reproduce(Path(receipt), latest=latest, no_fetch=no_fetch)
    typer.echo(f"  {r.status} (as of {r.as_of})")
    for reason in r.reasons:
        typer.echo(f"  - {reason}")
    if r.out_dir:
        typer.echo(f"  rendered to {r.out_dir}")
    raise typer.Exit(code={"identical": 0, "rendered-latest": 0, "differs": 1}.get(r.status, 2))


@app.command()
def entities(action: str = typer.Argument("check", help="check | suggest")) -> None:
    """Report or suggest canonical model/vendor mappings."""
    _not_yet("Phase 3")


@app.command()
def site(out: str = typer.Option("_site", help="Output folder (gitignored).")) -> None:
    """Build the short-link site published to GitHub Pages (cacheregister.dev/<link>)."""
    from pathlib import Path

    from cachereg.site import build_site, short_url

    for link in build_site(Path(out)):  # receipts only
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
