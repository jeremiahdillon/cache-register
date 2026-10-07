"""`cachereg entities suggest`: propose `config/entities/models.yaml` aliases (PLAN §4.3 bootstrap).

Author tool. Reads local staged Parquet only (after `cachereg fetch` and `cachereg build`) and prints
proposals for review; `--write` adds them to models.yaml without rewriting reviewed lines. Nothing
fuzzy is accepted: every rule is an exact match after the collapses PLAN §4.3 allows (case, provider
or host prefix). Date and version suffixes are never stripped.

Sources:
  openrouter  rankings permaslugs → LiteLLM price keys (formerly scripts/suggest_model_aliases.py)
  epoch       Epoch model groups (ECI `Model`) → canonical models, bridged by LiteLLM keys
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

import polars as pl
import yaml

from cachereg.core.paths import data_dir, entities_dir, repo_relative, staged_dir


def models_yaml() -> Path:
    return entities_dir() / "models.yaml"


def load_models() -> dict:
    f = models_yaml()
    return ((yaml.safe_load(f.read_text()) or {}).get("models") or {}) if f.is_file() else {}


def aliases(entry: dict | None, source: str) -> list[str]:
    """A model entry's aliases for one source; empty `aliases:` or source keys count as none."""
    return list(((entry or {}).get("aliases") or {}).get(source) or [])


# ---- models.yaml writer (append new models; insert aliases into existing ones) ------------------


def _item(value: str) -> str:
    """A YAML list item for ``value``, quoted only when YAML needs it."""
    return yaml.safe_dump([value], default_flow_style=False, allow_unicode=True, width=10_000).rstrip("\n")


def _key(line: str) -> str | None:
    """The model id on a `  <model_id>:` line (comments allowed), else None."""
    if not re.match(r"^  \S", line) or line.lstrip().startswith("#"):
        return None
    try:
        parsed = yaml.safe_load(line.strip())
    except yaml.YAMLError:
        return None
    return next(iter(parsed)) if isinstance(parsed, dict) and len(parsed) == 1 else None


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def write_models(new: dict[str, dict], additions: dict[str, dict[str, list[str]]]) -> None:
    """Append ``new`` models and add ``additions`` ({model_id: {source: [alias, …]}}) to existing ones.

    Line-level edits keep every comment and reviewed line as is. The result is re-parsed and must
    equal the old mapping plus exactly these changes; otherwise nothing is written.
    """
    f = models_yaml()
    text = f.read_text() if f.is_file() else "models:\n"
    old = (yaml.safe_load(text) or {}).get("models") or {}
    lines = text.splitlines()
    for mid, sources in additions.items():
        start = next((i for i, line in enumerate(lines) if _key(line) == mid), None)
        if start is None:
            raise ValueError(f"models.yaml: no entry {mid!r} to add aliases to")
        end = next((i for i in range(start + 1, len(lines)) if lines[i].strip() and _indent(lines[i]) <= 2), len(lines))
        al = next((i for i in range(start + 1, end) if lines[i].strip() == "aliases:" and _indent(lines[i]) == 4), None)
        if al is None:
            raise ValueError(f"models.yaml: {mid!r} has no block-style `aliases:` to add to")
        al_end = next((i for i in range(al + 1, end) if lines[i].strip() and _indent(lines[i]) <= 4), end)
        while al_end > al + 1 and not lines[al_end - 1].strip():  # keep blank lines after the block
            al_end -= 1
        for src, aliases in sources.items():
            items = [f"      {_item(a)}" for a in aliases]
            here = range(al + 1, al_end)
            at = next((i for i in here if lines[i].strip() == f"{src}:" and _indent(lines[i]) == 6), None)
            if at is None:
                lines[al_end:al_end] = [f"      {src}:", *items]
                al_end += 1 + len(items)
                continue
            last = at
            while last + 1 < al_end and lines[last + 1].startswith("      - "):
                last += 1
            lines[last + 1 : last + 1] = items
            al_end += len(items)
    if new:
        block = yaml.safe_dump(dict(sorted(new.items())), sort_keys=False, width=120, allow_unicode=True)
        lines += [f"  {line}" for line in block.splitlines()]
    result = "\n".join(lines) + "\n"

    expected = {
        mid: {"aliases": {s: list(a or []) for s, a in ((m or {}).get("aliases") or {}).items()}}
        for mid, m in old.items()
    }
    for mid, sources in additions.items():
        for src, aliases in sources.items():
            expected[mid]["aliases"].setdefault(src, []).extend(aliases)
    expected.update(new)
    got = (yaml.safe_load(result) or {}).get("models") or {}
    got_cmp = {
        mid: {"aliases": {s: list(a or []) for s, a in ((m or {}).get("aliases") or {}).items()}}
        for mid, m in got.items()
    }
    if got_cmp != expected or set(got) != set(expected):
        raise ValueError("models.yaml edit did not re-parse to the expected mapping; nothing written")
    f.write_text(result)


# ---- openrouter: permaslugs → LiteLLM keys ------------------------------------------------------

VENDOR_PREFIX = {  # OpenRouter author prefix -> LiteLLM first-party key prefix
    "anthropic": [""],
    "openai": [""],
    "google": ["gemini/"],
    "x-ai": ["xai/"],
    "deepseek": ["deepseek/"],
    "mistralai": ["mistral/"],
    "moonshotai": ["moonshot/"],
    "z-ai": ["zai/"],
    "qwen": ["dashscope/"],
    "minimax": ["minimax/"],
    "meta-llama": ["meta_llama/"],
    "cohere": ["cohere_chat/", ""],
    "perplexity": ["perplexity/"],
    "amazon": ["bedrock/", ""],
    "xiaomi": ["xiaomi_mimo/"],
}
# Variants with their own list price that no LiteLLM key carries: never proposed (stay unpriced).
NEVER = re.compile(r"^google/gemini-2\.5-flash-preview-.*:thinking$")
DATE_SUFFIX = re.compile(r"-(\d{8}|\d{4}-\d{2}-\d{2})$")


def _litellm_keys(prices: pl.DataFrame | None = None) -> tuple[pl.DataFrame, set[str], set[str]]:
    """LiteLLM staged prices, every key ever listed, and keys only ever listed at $0 (free tiers)."""
    if prices is None:
        prices = pl.read_parquet(staged_dir("litellm_prices") / "prices.parquet")
    keys = set(prices["key"].to_list())
    priced = prices.filter(pl.col("input_usd_per_token").is_not_null())
    paid = priced.filter((pl.col("input_usd_per_token") > 0) | (pl.col("output_usd_per_token") > 0))
    free = set(priced["key"].to_list()) - set(paid["key"].to_list())
    return prices, keys, free


def _load_openrouter():
    ranks = pl.read_parquet(staged_dir("openrouter_rankings") / "daily.parquet")
    prices = pl.read_parquet(staged_dir("litellm_prices") / "prices.parquet")
    snap = staged_dir("openrouter_models") / "prices.parquet"
    ids, snap_price, snap_day = {}, {}, None
    if snap.is_file():
        s = pl.read_parquet(snap).filter(~pl.col("id").str.contains(":"))
        snap_day = s["snapshot_date"].max()
        s = s.filter(pl.col("snapshot_date") == snap_day)
        for r in s.iter_rows(named=True):
            ids[r["canonical_slug"]] = r["id"]
            if r["prompt_usd_per_token"] is not None and r["completion_usd_per_token"] is not None:
                snap_price[r["canonical_slug"]] = 0.8 * r["prompt_usd_per_token"] + 0.2 * r["completion_usd_per_token"]
    return ranks, prices, ids, snap_price, snap_day


def openrouter_candidates(slug: str, cat_id: str | None, keys: set[str], free: set[str]) -> list[tuple[str, str]]:
    base = slug.split(":", 1)[0]
    author, _, name = base.partition("/")
    out: list[tuple[str, str]] = []

    def add(key: str, rule: str) -> None:
        if key in keys and key not in [k for k, _ in out]:
            out.append((key, rule))

    if cat_id:
        add(f"openrouter/{cat_id}", "1:openrouter/<catalog id>")
    add(f"openrouter/{base}", "2:openrouter/<permaslug>")
    names = [n for n in dict.fromkeys([cat_id.partition("/")[2] if cat_id else None, name]) if n]
    m = DATE_SUFFIX.search(name)
    for prefix in VENDOR_PREFIX.get(author, []):
        for n in names:
            variants = [n, n.replace(".", "-")]
            if m and not DATE_SUFFIX.search(n):  # catalog id without the date: add the permaslug's date
                variants += [f"{v}-{m.group(1)}" for v in list(variants)]
            for v in variants:
                if f"{prefix}{v.lower()}" not in free:  # free-tier listings, not the paid list price
                    add(f"{prefix}{v.lower()}", "3:vendor-direct")
    # dated keys before undated ones within the vendor-direct group (dated = that exact version)
    return sorted(out, key=lambda kr: (kr[1][0], 0 if DATE_SUFFIX.search(kr[0]) else 1))


def suggest_openrouter(min_share: float = 0.0001, write: bool = False, echo=print) -> dict[str, dict]:
    """Rules, in preference order (the order of the `litellm` list):
      1. openrouter/<catalog id>
      2. openrouter/<permaslug without :variant>
      3. vendor-direct key: <prefix><name>, name from the catalog id or the permaslug, with only case
         and "." -> "-" normalised; a dated permaslug also tries <name>-<its date suffix>. Keys only
         ever listed at $0 (free tiers such as Google AI Studio's) are skipped.
    The openrouter_models snapshot, if staged, is used only for identifiers (canonical_slug -> id)
    and as a price cross-check; nothing from it is written except model ids.
    """
    ranks, prices, ids, snap_price, snap_day = _load_openrouter()
    _, keys, free = _litellm_keys(prices)
    existing = load_models()
    mapped = {s for m in existing.values() for s in aliases(m, "openrouter")}

    tok = (
        ranks.filter((pl.col("model_permaslug") != "other") & ~pl.col("model_permaslug").str.ends_with(":free"))
        .group_by("model_permaslug")
        .agg(pl.col("total_tokens").sum().alias("tokens"), pl.col("date").min().alias("first"))
        .sort("tokens", descending=True)
    )
    total = tok["tokens"].sum()
    # LiteLLM's price on the snapshot's own day (its openrouter/ entries change almost daily)
    on_day = (
        pl.col("valid_to").is_null()
        if snap_day is None
        else ((pl.col("valid_from") <= snap_day) & (pl.col("valid_to").is_null() | (pl.col("valid_to") > snap_day)))
    )
    last_price = (
        prices.filter(on_day & pl.col("input_usd_per_token").is_not_null())
        .with_columns((0.8 * pl.col("input_usd_per_token") + 0.2 * pl.col("output_usd_per_token")).alias("blend"))
        .select("key", "blend")
    )
    blend = dict(zip(last_price["key"], last_price["blend"], strict=True))

    proposals: dict[str, dict] = {}
    covered = sum(t for s, t in zip(tok["model_permaslug"], tok["tokens"], strict=True) if s in mapped)
    unmapped = []
    for slug, tokens, first in tok.iter_rows():
        share = tokens / total
        if slug in mapped or share < min_share or NEVER.match(slug):
            continue
        cat = ids.get(slug.split(":", 1)[0])
        cands = openrouter_candidates(slug, cat, keys, free)
        if not cands:
            unmapped.append((slug, share, first))
            continue
        covered += tokens
        model_id = cat or slug.split(":", 1)[0]
        entry = proposals.setdefault(model_id, {"aliases": {"openrouter": [], "litellm": []}})
        entry["aliases"]["openrouter"].append(slug)
        for k, _ in cands:
            if k not in entry["aliases"]["litellm"]:
                entry["aliases"]["litellm"].append(k)
        snap = snap_price.get(slug.split(":", 1)[0])
        lp = blend.get(cands[0][0])
        check = ""
        if snap and lp:
            diff = lp / snap - 1
            check = f"  price vs snapshot {diff:+.0%}" + ("  <-- REVIEW" if abs(diff) > 0.10 else "")
        elif snap is not None and lp is None:
            check = "  first key not listed today"
        rules = ", ".join(f"{k} [{r}]" for k, r in cands)
        echo(f"{share:7.3%}  {slug}  ->  {rules}{check}")

    echo(f"\ncoverage with existing + proposed aliases: {covered / total:.2%} of non-free, non-other tokens")
    echo("\nunmapped (largest first):")
    for slug, share, first in unmapped[:40]:
        echo(f"{share:7.3%}  {slug}  (first seen {first})")

    if write and proposals:
        # New models are appended; aliases proposed for a model that already has an entry are
        # printed for a manual merge (an openrouter permaslug changes which prices a model gets).
        new = {mid: e for mid, e in proposals.items() if mid not in existing}
        for mid in sorted(set(proposals) - set(new)):
            echo(f"merge by hand: {mid} += {proposals[mid]['aliases']}")
        if new:
            write_models(new, {})
        echo(f"\nappended {len(new)} new model(s) to {repo_relative(models_yaml())}")
    return proposals


# ---- epoch: model groups → canonical models -----------------------------------------------------

# Reasoning-effort / thinking-budget settings Epoch appends to a version: a variant of one model.
# Quantisation suffixes such as `-q8_0` are NOT effort and are never stripped.
EFFORT = re.compile(r"_(none|minimal|low|medium|high|xhigh|max|unknown|\d+[kK])$")


def epoch_base(version: str) -> str:
    """Identity of an Epoch model version for matching: effort suffix and host/provider path removed,
    lowercased (PLAN §4.3 collapses). Dates and versions are kept."""
    return EFFORT.sub("", version.strip()).rsplit("/", 1)[-1].lower()


DATED = re.compile(r"-(\d{8}|\d{4}-\d{2}-\d{2}|\d{2}-\d{4}|\d{4})$")


def _undated(name: str) -> str:
    """Comparison form for review-only candidates: no date suffix, "." -> "-", lowercase."""
    return DATED.sub("", name.lower()).replace(".", "-")


# LiteLLM key prefixes that are the vendor's own API (as in VENDOR_PREFIX), by OpenRouter author.
OWN_PREFIXES = {author: [p for p in prefixes if p] for author, prefixes in VENDOR_PREFIX.items()}


def _own_keys(author: str, keys: list[str], bases: list[str]) -> list[str]:
    """`openrouter/<author>/…` and the vendor's own keys (bare or its LiteLLM prefix); no resellers."""
    out = []
    for k in keys:
        lk = k.lower()
        if lk.startswith(f"openrouter/{author}/"):
            out.append(k)
        elif lk in bases and "" in VENDOR_PREFIX.get(author, []):
            out.append(k)
        elif any(lk == f"{p}{b}" for p in OWN_PREFIXES.get(author, []) for b in bases):
            out.append(k)
    return out


def _litellm_order(keys: list[str]) -> list[str]:
    """openrouter/ keys first, then the rest; dated before undated within each group."""
    return sorted(keys, key=lambda k: (0 if k.startswith("openrouter/") else 1, 0 if DATE_SUFFIX.search(k) else 1, k))


@dataclass
class EpochSuggestion:
    proposals: dict[str, str] = field(default_factory=dict)  # group -> existing model_id (E1)
    new_models: dict[str, dict] = field(default_factory=dict)  # model_id -> entry (E2)
    unresolved: list[dict] = field(default_factory=list)


def suggest_epoch(write: bool = False, echo=print) -> EpochSuggestion:
    """For each ECI model group not yet mapped, in ECI order (groups without ECI are left alone: many
    are raw version names or moving aliases, and the coverage measure is defined on ECI):
    E1  a version's base equals the last path segment of a LiteLLM key already listed under exactly
        one canonical model (or one created earlier in this run) → add the group to that model's
        `epoch` aliases;
    E2  no canonical model owns a matching key, but an `openrouter/<author>/<name>` key matches →
        a new model `<author>/<name>`; its `litellm` list is that key plus the vendor's own matching
        keys (bare or the vendor's LiteLLM prefix), never resellers' or free-tier keys;
    E3  (review only, never written) the group's undated name matches exactly one canonical model
        whose id or openrouter alias is the same once dates and "."/"-" are ignored; printed with
        the candidate for a human to confirm (PLAN §4.3: dates are never stripped automatically);
    else unresolved (ambiguous, a host-run group such as `chutes/…`, or no LiteLLM key), queued to
    data/entities/unresolved_epoch.csv. A canonical model receives at most one Epoch group: a
    second claimant is unresolved.
    """
    vint = pl.read_parquet(staged_dir("epoch_benchmarks") / "vintages.parquet")
    if vint.is_empty():
        raise ValueError("epoch_benchmarks has no staged vintages; run `cachereg fetch epoch_benchmarks` and build")
    vid = vint.sort("fetched_at")["vintage_id"][-1]
    models = pl.read_parquet(staged_dir("epoch_benchmarks") / "models.parquet").filter(pl.col("vintage_id") == vid)
    eci = pl.read_parquet(staged_dir("epoch_benchmarks") / "eci.parquet").filter(pl.col("vintage_id") == vid)
    _, keys, free = _litellm_keys()
    existing = load_models()

    by_undated: dict[str, set[str]] = {}
    for mid, m in existing.items():
        names = [mid, *aliases(m, "openrouter")]
        for n in names:
            by_undated.setdefault(_undated(n.split(":", 1)[0].rsplit("/", 1)[-1]), set()).add(mid)

    by_last: dict[str, list[str]] = {}  # a key matches a base when its last path segment equals it
    for k in keys:
        by_last.setdefault(k.lower().rsplit("/", 1)[-1], []).append(k)

    owner: dict[str, str] = {}
    for mid, m in existing.items():
        for k in aliases(m, "litellm"):
            owner[k] = mid
    mapped = {g: mid for mid, m in existing.items() for g in aliases(m, "epoch")}
    claimed = {mid for mid in mapped.values()}

    versions: dict[str, list[str]] = {}
    for v, g in models.select("model_version", "model_group").iter_rows():
        if g:
            versions.setdefault(g, []).append(v)
    eci_rows = eci.sort("eci", descending=True, nulls_last=True)
    order = [(g, e, o) for g, e, o in eci_rows.select("model_group", "eci", "organization").iter_rows()]
    in_eci = {g for g, _, _ in order}
    rank = {g: i for i, (g, _, _) in enumerate(order, start=1)}

    out = EpochSuggestion()
    for group, score, organization in order:
        if group in mapped:
            continue
        bases = sorted({epoch_base(v) for v in versions.get(group, [])})
        matched = sorted({k for b in bases for k in by_last.get(b, [])})
        owners = sorted({owner[k] for k in matched if k in owner})
        label = f"#{rank[group]:<3} {group}" + (f" (ECI {score:.1f})" if score is not None else "")

        def unresolved(reason: str, candidates=(), group=group, score=score, organization=organization, bases=bases):
            out.unresolved.append(
                {
                    "model_group": group,
                    "eci": score,
                    "organization": organization,
                    "versions": ";".join(bases),
                    "reason": reason,
                    "candidates": ";".join(candidates),
                }
            )

        if "/" in group:  # a group named after one host's run, not a model
            unresolved("host-run group")
            continue
        if len(owners) == 1:
            mid = owners[0]
            if mid in claimed:
                unresolved("model already has an epoch group", owners)
                echo(f"  conflict  {label}  ->  {mid} (already claimed)")
                continue
            claimed.add(mid)
            out.proposals[group] = mid
            echo(f"  E1        {label}  ->  {mid}")
        elif len(owners) > 1:
            unresolved("ambiguous", owners)
            echo(f"  ambiguous {label}  ->  {', '.join(owners)}")
        else:
            paid = [k for k in matched if k not in free]
            review = sorted({mid for b in bases for mid in by_undated.get(_undated(b), set())} - claimed)
            ids = sorted(
                {k.removeprefix("openrouter/") for k in paid if k.startswith("openrouter/") and k.count("/") == 2}
            )
            if len(review) == 1:
                unresolved("review: same model if the date is ignored", review)
                echo(f"  E3 review {label}  ->  {review[0]}  (confirm by hand; versions: {', '.join(bases)})")
            elif len(ids) == 1 and ids[0] not in existing and ids[0] not in claimed and ids[0] not in out.new_models:
                mid = ids[0]
                claimed.add(mid)
                own = _litellm_order(_own_keys(mid.split("/", 1)[0], paid, bases))
                out.new_models[mid] = {"aliases": {"litellm": own, "epoch": [group]}}
                owner.update(dict.fromkeys(own, mid))  # a later group matching these keys conflicts
                echo(f"  E2 new    {label}  ->  {mid}  litellm: {', '.join(own)}")
            elif ids:
                unresolved("new model id ambiguous or taken", ids)
                echo(f"  review    {label}  ->  {', '.join(ids)} (new id ambiguous or already used)")
            else:
                unresolved("no LiteLLM key" if not matched else "no openrouter/ key for a new id", matched)

    total = len(in_eci)
    top = [g for g, _, _ in order[:50]]

    def share(groups, extra):
        hit = sum(1 for g in groups if g in mapped or g in extra)
        return f"{hit}/{len(groups)} ({hit / len(groups):.0%})" if groups else "-"

    resolved = set(out.proposals) | {e["aliases"]["epoch"][0] for e in out.new_models.values()}
    echo(f"\nECI models mapped: {share(sorted(in_eci), set())} now, {share(sorted(in_eci), resolved)} with proposals")
    echo(f"top 50 by ECI:     {share(top, set())} now, {share(top, resolved)} with proposals (of {total} ECI models)")

    queue = data_dir() / "entities" / "unresolved_epoch.csv"
    queue.parent.mkdir(parents=True, exist_ok=True)
    with queue.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["model_group", "eci", "organization", "versions", "reason", "candidates"])
        w.writeheader()
        w.writerows(out.unresolved)
    echo(f"unresolved: {len(out.unresolved)} group(s) -> {repo_relative(queue)}")

    if write and (out.proposals or out.new_models):
        additions = {mid: {"epoch": [g]} for g, mid in out.proposals.items()}
        write_models(out.new_models, additions)
        echo(
            f"wrote {len(additions)} epoch alias(es) and {len(out.new_models)} new model(s)"
            f" to {repo_relative(models_yaml())}"
        )
    return out
