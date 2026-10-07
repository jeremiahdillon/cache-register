"""`cachereg` command line.

Phase 0 ships the command surface and `status`; the other commands land in the phases
named in their help text (see docs/PLAN.md §10).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import typer

from cachereg.core import fetch_state
from cachereg.core.paths import repo_relative
from cachereg.core.registry import load_sources
from cachereg.core.settings import SECRETS, MissingSecretError, secret_status

app = typer.Typer(no_args_is_help=True, add_completion=False, help="Cache Register — receipts for the AI economy.")


def _not_yet(phase: str) -> None:
    typer.echo(f"Not implemented yet (planned for {phase}; see docs/PLAN.md §10).", err=True)
    raise typer.Exit(code=2)


def _day(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def _today() -> date:
    """UTC date, as raw fetch folders are dated (a seam for tests)."""
    return datetime.now(UTC).date()


def _outcome(sid: str, error: str | None = None, kind: str = "FAIL") -> str:
    """Record a fetch outcome and return the redacted message to print. Never raises: the state file is
    bookkeeping for `status`, so failing to save it must not fail a fetch or stop the other sources."""
    try:
        message = fetch_state.clean(error) if error else ""
    except Exception:  # noqa: BLE001 (if redaction itself fails, print nothing that might hold a secret)
        message = "(message withheld: redaction failed)"
    try:
        fetch_state.record(sid, error, kind)
    except Exception as e:  # noqa: BLE001
        typer.echo(f"  WARN  {sid:<22} fetch state not saved ({type(e).__name__})", err=True)
    return message


@app.command()
def fetch(
    sources: list[str] = typer.Argument(None, help="Source ids; omit for all enabled sources."),
    full: bool = typer.Option(False, help="Re-fetch full history instead of the trailing window."),
    due: bool = typer.Option(
        False, help="Only sources whose cadence has passed since their latest fetch; a missing secret is not an error."
    ),
    from_clipboard: bool = typer.Option(False, help="Manual sources: import the clipboard (macOS)."),
    from_file: Path = typer.Option(None, help="Manual sources: import this file."),
    cut: str = typer.Option(None, help="Manual sources: which part of the source the input is."),
) -> None:
    """Download raw data from sources into data/raw (immutable, one folder per fetch).

    Sources with `input: manual` are imported one input at a time with --from-clipboard or
    --from-file; otherwise they are listed as `manual` (with their due date) and never fail a run.
    """
    known = load_sources()
    ids = sources or [s.id for s in known.values() if s.enabled]
    unknown = [s for s in ids if s not in known]
    if unknown:
        raise typer.BadParameter(f"unknown source(s) {', '.join(unknown)}; known: {', '.join(known)}")
    if from_clipboard or from_file is not None or cut is not None:
        _fetch_manual(known, sources or [], from_clipboard, from_file, cut, full, due)
        return
    failed = False
    if due:
        from cachereg.core.schedule import due_date

        today, held = _today(), set()
        for sid in ids:
            try:
                when = due_date(known[sid])
            except ValueError as e:  # e.g. an unknown cadence: report it, keep the other sources going
                failed = True
                held.add(sid)
                typer.echo(f"  FAIL  {sid:<22} {_outcome(sid, str(e))}", err=True)
                continue
            if when is not None and when > today:
                held.add(sid)
                typer.echo(f"  wait  {sid:<22} next due {when}")
        ids = [s for s in ids if s not in held]
    for sid in ids:
        if known[sid].input == "manual":
            _manual_line(known[sid])
            continue
        try:
            raw = known[sid].module("fetch").fetch(full=full)
            out = raw.write()
            _outcome(sid)
            typer.echo(f"  ok    {sid:<22} {len(raw.files)} file(s) -> {repo_relative(out)}")
        except MissingSecretError as e:
            failed = failed or not due  # scheduled runs: a missing key is reported, not a failure
            typer.echo(f"  skip  {sid:<22} {_outcome(sid, str(e), 'skip')}", err=True)
        except Exception as e:  # noqa: BLE001 (report per source, keep going)
            failed = True
            typer.echo(f"  FAIL  {sid:<22} {_outcome(sid, f'{type(e).__name__}: {e}')}", err=True)
    if failed:
        raise typer.Exit(code=1)


def _manual_line(src) -> None:
    """A manual source in a normal or scheduled run: say when it is due and how to import it."""
    from cachereg.core.schedule import due_date

    try:
        when = due_date(src)
    except (ValueError, KeyError, TypeError, OSError):  # a corrupt raw folder or manifest: still list it
        shown = "?"
    else:
        shown = "now" if when is None or when <= _today() else str(when)
    typer.echo(f"  manual {src.id:<21} due {shown}; import with: cachereg fetch {src.id} --from-clipboard --cut …")


def _manual_help(src) -> None:
    hook = getattr(src.module("fetch"), "manual_help", None)
    if hook:
        typer.echo(hook())


def _fetch_manual(known, ids, clipboard: bool, file, cut, full: bool, due: bool) -> None:
    from cachereg.core.manual import read_input

    if full or due:
        raise typer.BadParameter("--from-clipboard/--from-file/--cut cannot be combined with --full or --due")
    if len(ids) != 1:
        raise typer.BadParameter("a manual import takes exactly one source id")
    src = known[ids[0]]
    if src.input != "manual":
        raise typer.BadParameter(f"{src.id} is not a manual source (input: {src.input})")
    if not clipboard and file is None:
        raise typer.BadParameter("--cut needs --from-clipboard or --from-file")
    if cut is None:
        typer.echo(f"  FAIL  {src.id:<22} --cut is required; the cuts are:", err=True)
        _manual_help(src)
        raise typer.Exit(code=1)
    try:
        manual = read_input(clipboard, file, cut)
        raw = src.module("fetch").fetch(full=False, manual=manual)
        out = raw.write()
    except Exception as e:  # noqa: BLE001 (reported like any failed fetch; nothing was written)
        typer.echo(f"  FAIL  {src.id:<22} {_outcome(src.id, f'{type(e).__name__}: {e}')}", err=True)
        raise typer.Exit(code=1) from None
    _outcome(src.id)
    typer.echo(f"  ok    {src.id:<22} {cut} ({manual.via}) -> {repo_relative(out)}")


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
        rev = v.get("revision")
        what = f"{rev.get('date')} {str(rev.get('value'))[:12]} (source revision)" if rev else v["fetch_date"]
        typer.echo(f"  vintage {sid:<24} {what}{flag}")
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
    from cachereg.reproduce import reproduce as run_reproduce

    r = run_reproduce(Path(receipt), latest=latest, no_fetch=no_fetch)
    typer.echo(f"  {r.status} (as of {r.as_of})")
    for reason in r.reasons:
        typer.echo(f"  - {reason}")
    if r.out_dir:
        typer.echo(f"  rendered to {r.out_dir}")
    raise typer.Exit(code={"identical": 0, "rendered-latest": 0, "differs": 1}.get(r.status, 2))


@app.command()
def entities(
    action: str = typer.Argument("check", help="check | suggest"),
    source: str = typer.Option("epoch", help="suggest: openrouter | epoch"),
    write: bool = typer.Option(False, help="suggest: add the proposals to config/entities/models.yaml"),
    min_share: float = typer.Option(0.0001, help="suggest --source openrouter: smallest token share considered"),
) -> None:
    """Suggest canonical model mappings from staged data (review before committing models.yaml)."""
    if action != "suggest":
        _not_yet("Phase 3")
    from cachereg import entities as ent

    if source == "openrouter":
        ent.suggest_openrouter(min_share=min_share, write=write, echo=typer.echo)
    elif source == "epoch":
        ent.suggest_epoch(write=write, echo=typer.echo)
    else:
        raise typer.BadParameter(f"unknown source {source!r}; use openrouter or epoch")


@app.command()
def site(out: str = typer.Option("_site", help="Output folder (gitignored).")) -> None:
    """Build the short-link site published to GitHub Pages (cacheregister.dev/<link>)."""
    from cachereg.site import build_site, short_url

    for link in build_site(Path(out)):  # receipts only
        typer.echo(f"  {short_url(link.slug):<45} -> {link.analysis}")


@app.command()
def status() -> None:
    """Per enabled source: cadence, last fetch, next due date and last error; then which credentials are set."""
    from cachereg.core.schedule import last_fetch_date, next_due

    today = _today()
    try:
        state = fetch_state.load()
    except (ValueError, OSError) as e:
        state = {}
        typer.echo(f"  WARN  fetch state unreadable ({e}); last errors not shown", err=True)
    typer.echo(f"  {'source':<22} {'cadence':<8} {'last fetch':<11} {'next due':<11} last error")
    for src in load_sources().values():
        if not src.enabled:
            continue
        try:
            last = last_fetch_date(src.id)
        except (ValueError, KeyError, TypeError, OSError) as e:  # a corrupt raw folder or manifest: show it, keep going
            typer.echo(f"  {src.id:<22} {src.cadence:<8} {'?':<11} {'?':<11} raw store unreadable ({type(e).__name__})")
            continue
        due = next_due(src.cadence, last) if last else None
        when = "now" if due is None or due <= today else str(due)
        entry = state.get(src.id)
        err = entry.get("last_error") if isinstance(entry, dict) else None
        shown = f"{str(err.get('at'))[:10]} {err.get('kind')}: {err.get('message')}" if isinstance(err, dict) else "-"
        typer.echo(f"  {src.id:<22} {src.cadence:<8} {str(last or 'never'):<11} {when:<11} {shown}")
    typer.echo("")
    configured = secret_status()
    for name, ok in configured.items():
        mark = "set    " if ok else "missing"
        typer.echo(f"  {mark}  {name:<30} {SECRETS[name].purpose}")


if __name__ == "__main__":
    app()
