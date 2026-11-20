"""Tests never write outside their tmp folder, whatever path variables the shell exports."""

from __future__ import annotations

import pytest

from cachereg.core import paths


@pytest.fixture
def exported_paths(tmp_path_factory, monkeypatch):
    """A shell that exported a private build folder (the worktree procedure) before pytest started."""
    sentinel = tmp_path_factory.mktemp("sentinel")
    monkeypatch.setenv("CACHEREG_BUILD_DIR", str(sentinel / "build"))
    monkeypatch.setenv("CACHEREG_OUTPUTS_DIR", str(sentinel / "outputs"))
    return sentinel


def test_data_env_overrides_an_exported_build_dir(exported_paths, data_env):
    for p in (paths.build_dir(), paths.warehouse_path(), paths.staged_dir("x"), paths.outputs_dir()):
        assert p.is_relative_to(data_env), p
        assert not p.is_relative_to(exported_paths), p


def test_a_build_in_a_test_leaves_the_exported_folder_empty(exported_paths, synthetic_raw):
    from datetime import date

    from cachereg.build import build

    build(date(2026, 8, 31), ["openrouter_rankings", "litellm_prices"])
    assert paths.warehouse_path().exists() and paths.warehouse_path().is_relative_to(synthetic_raw)
    assert not any(exported_paths.rglob("*"))
