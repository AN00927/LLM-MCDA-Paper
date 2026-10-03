"""Safety checks for local-only document roots."""
from __future__ import annotations

import os

import pytest

from llm_mcda.common import paths


@pytest.mark.parametrize(
    ("env_name", "root_getter", "frozen_name"),
    [
        (paths.LOCAL_MANUSCRIPTS_ENV, paths.local_manuscripts_root, "Analysis"),
        (paths.LOCAL_MANUSCRIPTS_ENV, paths.local_manuscripts_root, "paper"),
        (paths.LOCAL_DOCUMENTATION_ENV, paths.local_documentation_root, "Analysis"),
        (paths.LOCAL_DOCUMENTATION_ENV, paths.local_documentation_root, "paper"),
    ],
)
def test_local_root_override_cannot_target_frozen_repository_data(
    tmp_path, monkeypatch, env_name, root_getter, frozen_name
):
    repo = tmp_path / "repo"
    protected = repo / frozen_name
    protected.mkdir(parents=True)
    monkeypatch.setattr(paths, "repository_root", lambda: repo)
    monkeypatch.setenv(env_name, str(protected))

    with pytest.raises(paths.UnsafeOutputPathError, match="frozen repository data"):
        root_getter()


@pytest.mark.parametrize(
    ("env_name", "default_name", "root_getter", "frozen_name"),
    [
        (
            paths.LOCAL_MANUSCRIPTS_ENV,
            "local_manuscripts",
            paths.local_manuscripts_root,
            "Analysis",
        ),
        (
            paths.LOCAL_DOCUMENTATION_ENV,
            "local_documentation",
            paths.local_documentation_root,
            "paper",
        ),
    ],
)
def test_default_local_root_cannot_symlink_into_frozen_repository_data(
    tmp_path, monkeypatch, env_name, default_name, root_getter, frozen_name
):
    repo = tmp_path / "repo"
    protected = repo / frozen_name
    protected.mkdir(parents=True)
    monkeypatch.setattr(paths, "repository_root", lambda: repo)
    monkeypatch.delenv(env_name, raising=False)

    try:
        (repo / default_name).symlink_to(protected, target_is_directory=True)
    except OSError:
        if os.name == "nt":
            pytest.skip("Windows does not permit creating a directory symlink here")
        raise

    with pytest.raises(paths.UnsafeOutputPathError, match="frozen repository data"):
        root_getter()
