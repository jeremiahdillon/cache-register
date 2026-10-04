"""Propose `config/entities/models.yaml` entries mapping OpenRouter permaslugs to LiteLLM keys.

Author tool (PLAN §4.3 bootstrap; folded into `cachereg entities suggest` in Phase 3). Reads the
local staged Parquet only, after `cachereg fetch` and `cachereg build`:
  openrouter_rankings.daily   permaslugs and their tokens
  litellm_prices.prices       every LiteLLM key that ever existed, with its price intervals
  openrouter_models.prices    optional: the author's catalog snapshot, used only for identifiers
                              (canonical_slug -> id) and as a price cross-check; nothing from it
                              is written except model ids.

Rules, in preference order (the order of the `litellm` list):
  1. openrouter/<catalog id>
  2. openrouter/<permaslug without :variant>
  3. vendor-direct key: <prefix><name>, name taken from the catalog id or the permaslug, with only
     case and "." -> "-" normalised; a dated permaslug also tries <name>-<its date suffix>. Keys only
     ever listed at $0 (free tiers such as Google AI Studio's) are skipped.
Date or version suffixes are never stripped. Every proposal is printed with its token share and
a price check against the snapshot; review before committing.

usage: uv run python scripts/suggest_model_aliases.py [--min-share 0.0001] [--write]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import polars as pl
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cachereg.core.paths import staged_dir  # noqa: E402

MODELS_YAML = ROOT / "config" / "entities" / "models.yaml"
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


def load():
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


def candidates(slug: str, cat_id: str | None, keys: set[str], free: set[str]) -> list[tuple[str, str]]:
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-share", type=float, default=0.0001)
    ap.add_argument("--write", action="store_true", help="append proposals to models.yaml")
    args = ap.parse_args()

    ranks, prices, ids, snap_price, snap_day = load()
    keys = set(prices["key"].to_list())
    priced = prices.filter(pl.col("input_usd_per_token").is_not_null())
    paid = priced.filter((pl.col("input_usd_per_token") > 0) | (pl.col("output_usd_per_token") > 0))
    free = set(priced["key"].to_list()) - set(paid["key"].to_list())  # only ever listed at $0
    existing = yaml.safe_load(MODELS_YAML.read_text())["models"] if MODELS_YAML.is_file() else {}
    mapped = {s for m in (existing or {}).values() for s in m["aliases"].get("openrouter", [])}

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
        if slug in mapped or share < args.min_share or NEVER.match(slug):
            continue
        cat = ids.get(slug.split(":", 1)[0])
        cands = candidates(slug, cat, keys, free)
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
        print(f"{share:7.3%}  {slug}  ->  {rules}{check}")

    print(f"\ncoverage with existing + proposed aliases: {covered / total:.2%} of non-free, non-other tokens")
    print("\nunmapped (largest first):")
    for slug, share, first in unmapped[:40]:
        print(f"{share:7.3%}  {slug}  (first seen {first})")

    if args.write and proposals:
        # Append-only, so the reviewed file (and its `# manual` comments) is never rewritten. Aliases
        # proposed for a model that already has an entry are printed for a manual merge instead.
        new = {mid: e for mid, e in proposals.items() if mid not in (existing or {})}
        for mid in sorted(set(proposals) - set(new)):
            print(f"merge by hand: {mid} += {proposals[mid]['aliases']}")
        if new:
            text = MODELS_YAML.read_text() if MODELS_YAML.is_file() else "models:\n"
            block = yaml.safe_dump(dict(sorted(new.items())), sort_keys=False, width=120)
            MODELS_YAML.write_text(text.rstrip("\n") + "\n" + "".join(f"  {line}\n" for line in block.splitlines()))
        print(f"\nappended {len(new)} new model(s) to {MODELS_YAML.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
