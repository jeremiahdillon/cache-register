"""config/entities loaders on synthetic files."""

from __future__ import annotations

import pytest

from cachereg.core import paths


def test_model_aliases_are_ranked_and_unique(tmp_path, monkeypatch):
    from cachereg import build as build_mod

    (tmp_path / "models.yaml").write_text(
        "models:\n"
        "  a/m1: {aliases: {openrouter: [a/m1-2026], litellm: [openrouter/a/m1, m1]}}\n"
        "  a/m2: {aliases: {openrouter: [a/m2]}}\n"
    )
    monkeypatch.setattr(paths, "ENTITIES_DIR", tmp_path)
    f = build_mod._model_alias_frame()
    lk = f.filter((f["model_id"] == "a/m1") & (f["source"] == "litellm"))
    assert lk["alias"].to_list() == ["openrouter/a/m1", "m1"] and lk["rank"].to_list() == [1, 2]
    (tmp_path / "models.yaml").write_text(
        "models:\n  a/m1: {aliases: {openrouter: [x/y]}}\n  a/m2: {aliases: {openrouter: [x/y]}}\n"
    )
    with pytest.raises(ValueError, match="listed under a/m1 and a/m2"):
        build_mod._model_alias_frame()


# ---- cachereg entities suggest ------------------------------------------------------------------

MODELS_YAML = """# header comment kept
models:
  openai/gpt-9:  # manual: kept as written
    aliases:
      openrouter:
      - openai/gpt-9-20260101
      litellm:
      - openrouter/openai/gpt-9
      - gpt-9-20260101

  x/amb-a:
    aliases:
      litellm:
      - a/amb-1
  x/amb-b:
    aliases:
      litellm:
      - b/amb-1
  x/old:
    aliases:
      litellm:
      - old-1
      epoch:
      - Old Model
  x/flow: {aliases: {litellm: [flow-1]}}
  x/empty:
    aliases:
  anthropic/claude-sonnet-9:
    aliases:
      openrouter:
      - anthropic/claude-sonnet-9-20260101
      litellm:
      - openrouter/anthropic/claude-sonnet-9
"""


def _epoch_zip(groups: dict[str, tuple[float | None, list[str]]]) -> bytes:
    """A synthetic benchmark_data.zip: group -> (ECI or None, model versions)."""
    from tests.test_epoch import _csv, _zip

    meta = [[v, g, "2026-01-01", "", "Vendor", "US", "API access", ""] for g, (_, vs) in groups.items() for v in vs]
    eci = [
        [g, g, e, e - 1, e + 1, "2026-01-01", "Vendor", "US", "API access", "Closed weights", ""]
        for g, (e, _) in groups.items()
        if e is not None
    ]
    no_eci = [vs[0] for g, (e, vs) in groups.items() if e is None]
    return _zip(
        {
            "README.md": "synthetic\n",
            "model_metadata.csv": _csv(
                [
                    "model_version",
                    "model_group",
                    "date",
                    "display_name",
                    "organization",
                    "country",
                    "accessibility",
                    "training_compute_flop",
                ],
                meta,
            ),
            "epoch_capabilities_index/eci_scores.csv": _csv(
                [
                    "Model",
                    "Display name",
                    "eci",
                    "eci_ci_low",
                    "eci_ci_high",
                    "date",
                    "Organization",
                    "Country (of organization)",
                    "Model accessibility",
                    "Accessibility group",
                    "model_versions",
                ],
                eci,
            ),
            "benchmark_metadata.csv": _csv(
                [
                    "benchmark",
                    "in_eci",
                    "source_file",
                    "score_column",
                    "scale",
                    "random_baseline",
                    "score_ceiling",
                    "release_date",
                    "superseded_by",
                ],
                [["B", "True", "b.csv", "Score", "1.0", "0", "1", "2024-01-01", ""]],
            ),
            "b.csv": _csv(["Model version", "Score"], [[v, "0.5"] for v in no_eci]),
        }
    )


@pytest.fixture
def epoch_entities(data_env, tmp_path, monkeypatch):
    from datetime import UTC, date, datetime

    from cachereg import entities
    from cachereg.build import build
    from tests.test_epoch import _write

    d = tmp_path / "entities"
    d.mkdir()
    (d / "models.yaml").write_text(MODELS_YAML)
    (d / "vendors.yaml").write_text((paths.entities_dir() / "vendors.yaml").read_text())
    monkeypatch.setattr(paths, "ENTITIES_DIR", d)
    groups = {
        "GPT 9": (150.0, ["gpt-9-20260101_high", "gpt-9-20260101_16k"]),  # E1 via vendor-direct key
        "GPT 9 Again": (149.0, ["gpt-9-20260101_low"]),  # same model: second claimant
        "Amb": (140.0, ["amb-1"]),  # two owners: ambiguous
        "New One": (130.0, ["chutes/New-1_max"]),  # E2: host prefix collapses, case folds
        "Quant": (120.0, ["phi4:14b-q8_0"]),  # _0 is not effort: no match for "phi4:14b-q8"
        "Old Model": (110.0, ["old-1"]),  # already mapped
        "No ECI": (None, ["gpt-9-mini-20260101"]),  # scored, not in ECI: not considered
        "chutes/Hosted": (100.0, ["chutes/gpt-9-mini-20260101"]),  # a host's run: unresolved
        "GPT 9 Mini": (90.0, ["gpt-9-mini-20260101_high"]),  # vendor key only, no openrouter/ key
        "Sonnet 9": (80.0, ["claude-sonnet-9-20260215"]),  # E3: same as anthropic/claude-sonnet-9 undated
        "Shared A": (70.0, ["share-a"]),  # E2: new model shareco/share-a, which now owns its key
        "Shared B": (60.0, ["share-a_high", "share-b"]),  # matches that key: conflict, not a second owner
    }
    _write("epoch_benchmarks", "benchmark_data.zip", _epoch_zip(groups), datetime(2026, 9, 1, 6, tzinfo=UTC))
    build(date(2026, 9, 1), ["epoch_benchmarks"])
    keys = {
        "openrouter/openai/gpt-9",
        "gpt-9-20260101",
        "a/amb-1",
        "b/amb-1",
        "old-1",
        "flow-1",
        "openrouter/newco/new-1",
        "newco/new-1-20260101",
        "NewCo/New-1",
        "free/new-1",
        "phi4:14b-q8",
        "gpt-9-mini-20260101",
        "claude-sonnet-9-20260215",
        "openrouter/shareco/share-a",
        "openrouter/shareco/share-b",
    }
    monkeypatch.setattr(entities, "_litellm_keys", lambda: (None, keys, {"free/new-1"}))
    return d


def test_epoch_base_strips_effort_and_host_only():
    from cachereg.entities import epoch_base

    assert epoch_base("claude-opus-4-5-20251101_16K") == "claude-opus-4-5-20251101"
    assert epoch_base("gpt-6.1-sol_max") == "gpt-6.1-sol"
    assert epoch_base("accounts/fireworks/models/qwen3-235b-a22b-thinking-2507") == "qwen3-235b-a22b-thinking-2507"
    assert epoch_base("phi4:14b-q8_0") == "phi4:14b-q8_0"  # quantisation, not effort
    assert epoch_base("gpt-5.6-sol_promax") == "gpt-5.6-sol_promax"  # a different product
    assert epoch_base("DeepSeek-V3.1_thinking") == "deepseek-v3.1_thinking"


def test_suggest_epoch_rules(epoch_entities):
    import csv

    from cachereg import entities
    from cachereg.core.paths import data_dir

    lines: list[str] = []
    out = entities.suggest_epoch(echo=lines.append)
    assert out.proposals == {"GPT 9": "openai/gpt-9"}
    assert out.new_models == {
        "newco/new-1": {"aliases": {"litellm": ["openrouter/newco/new-1"], "epoch": ["New One"]}},
        "shareco/share-a": {"aliases": {"litellm": ["openrouter/shareco/share-a"], "epoch": ["Shared A"]}},
    }
    reasons = {u["model_group"]: u["reason"] for u in out.unresolved}
    assert reasons == {
        "GPT 9 Again": "model already has an epoch group",
        "Amb": "ambiguous",
        "Quant": "no LiteLLM key",
        "chutes/Hosted": "host-run group",
        "GPT 9 Mini": "no openrouter/ key for a new id",
        "Sonnet 9": "review: same model if the date is ignored",
        "Shared B": "model already has an epoch group",
    }
    assert "Old Model" not in reasons  # mapped already: skipped
    with (data_dir() / "entities" / "unresolved_epoch.csv").open() as fh:
        assert {r["model_group"] for r in csv.DictReader(fh)} == set(reasons)
    assert any("ECI models mapped: 1/11 (9%) now, 4/11 (36%) with proposals" in line for line in lines)
    assert any("E3 review" in line and "anthropic/claude-sonnet-9" in line for line in lines)
    assert (epoch_entities / "models.yaml").read_text() == MODELS_YAML  # nothing written without --write


def test_suggest_epoch_write_keeps_comments_and_reparses(epoch_entities):
    import yaml

    from cachereg import build as build_mod
    from cachereg import entities

    entities.suggest_epoch(write=True, echo=lambda *_: None)
    text = (epoch_entities / "models.yaml").read_text()
    assert text.startswith(
        MODELS_YAML.split("\n  x/amb-a")[0].replace(
            "      - gpt-9-20260101\n", "      - gpt-9-20260101\n      epoch:\n      - GPT 9\n"
        )
    )
    assert "# header comment kept" in text and "# manual: kept as written" in text
    models = yaml.safe_load(text)["models"]
    assert models["openai/gpt-9"]["aliases"]["epoch"] == ["GPT 9"]
    assert models["newco/new-1"]["aliases"]["epoch"] == ["New One"]
    assert models["x/old"]["aliases"]["epoch"] == ["Old Model"]
    build_mod._model_alias_frame()  # still loads: aliases stay unique


def test_write_models_refuses_flow_style_and_unknown_models(epoch_entities):
    from cachereg.entities import write_models

    before = (epoch_entities / "models.yaml").read_text()
    with pytest.raises(ValueError, match="no block-style"):
        write_models({}, {"x/flow": {"epoch": ["Flow"]}})
    with pytest.raises(ValueError, match="no entry 'x/missing'"):
        write_models({}, {"x/missing": {"epoch": ["Missing"]}})
    write_models({}, {"x/old": {"epoch": ["Old Model 2"]}})  # appends to an existing list
    import yaml

    after = yaml.safe_load((epoch_entities / "models.yaml").read_text())["models"]
    assert after["x/old"]["aliases"]["epoch"] == ["Old Model", "Old Model 2"]
    assert (epoch_entities / "models.yaml").read_text() != before


def test_suggest_openrouter_matches_the_bootstrap_rules(synthetic_raw, synthetic_entities):
    from datetime import date

    from cachereg import entities
    from cachereg.build import build
    from tests.conftest import SLICE, SYNTHETIC_MODELS

    build(date(2026, 8, 31), SLICE)
    (synthetic_entities / "models.yaml").write_text("models: {}\n")
    props = entities.suggest_openrouter(min_share=0, echo=lambda *_: None)
    assert props == {m: {"aliases": {"openrouter": o, "litellm": lk}} for m, (o, lk) in SYNTHETIC_MODELS.items()}
