"""config/entities loaders on synthetic files."""

from __future__ import annotations

import pytest


def test_model_aliases_are_ranked_and_unique(tmp_path, monkeypatch):
    from cachereg import build as build_mod

    (tmp_path / "models.yaml").write_text(
        "models:\n"
        "  a/m1: {aliases: {openrouter: [a/m1-2026], litellm: [openrouter/a/m1, m1]}}\n"
        "  a/m2: {aliases: {openrouter: [a/m2]}}\n"
    )
    monkeypatch.setattr(build_mod, "ENTITIES_DIR", tmp_path)
    f = build_mod._model_alias_frame()
    lk = f.filter((f["model_id"] == "a/m1") & (f["source"] == "litellm"))
    assert lk["alias"].to_list() == ["openrouter/a/m1", "m1"] and lk["rank"].to_list() == [1, 2]
    (tmp_path / "models.yaml").write_text(
        "models:\n  a/m1: {aliases: {openrouter: [x/y]}}\n  a/m2: {aliases: {openrouter: [x/y]}}\n"
    )
    with pytest.raises(ValueError, match="listed under a/m1 and a/m2"):
        build_mod._model_alias_frame()
