"""`cachereg` command line.

Phase 0 ships the command surface and `status`; the other commands land in the phases
named in their help text (see docs/PLAN.md §10).
"""

from __future__ import annotations

import typer

from cachereg.core.settings import SECRETS, secret_status

app = typer.Typer(no_args_is_help=True, add_completion=False, help="Cache Register — receipts for the AI economy.")


def _not_yet(phase: str) -> None:
    typer.echo(f"Not implemented yet (planned for {phase}; see docs/PLAN.md §10).", err=True)
    raise typer.Exit(code=2)


@app.command()
def fetch(
    source: str = typer.Argument(None, help="Source id; omit for all."),
    due: bool = typer.Option(False, help="Only sources whose cadence says they are stale."),
) -> None:
    """Download raw data from sources into data/raw."""
    _not_yet("Phase 0.5")


@app.command()
def build() -> None:
    """Rebuild staged tables and marts from raw data."""
    _not_yet("Phase 0.5")


@app.command()
def render(analysis: str, targets: str = typer.Option(None), as_of: str = typer.Option(None)) -> None:
    """Render an analysis to its targets (HTML, PNG, video, …)."""
    _not_yet("Phase 0.5")


@app.command()
def publish(analysis: str, check: bool = typer.Option(False, help="Only run the licensing check.")) -> None:
    """Copy rendered outputs and their manifest into the analysis's published/ folder."""
    _not_yet("Phase 4")


@app.command()
def entities(action: str = typer.Argument("check", help="check | suggest")) -> None:
    """Report or suggest canonical model/vendor mappings."""
    _not_yet("Phase 3")


@app.command()
def status() -> None:
    """Show which credentials are configured (never their values)."""
    configured = secret_status()
    for name, ok in configured.items():
        mark = "set    " if ok else "missing"
        typer.echo(f"  {mark}  {name:<30} {SECRETS[name].purpose}")


if __name__ == "__main__":
    app()
