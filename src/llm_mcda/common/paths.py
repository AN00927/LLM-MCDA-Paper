"""Stable repository and local-only document path resolution."""
from __future__ import annotations

import os
from pathlib import Path


REPOSITORY_ROOT_ENV = "LLM_MCDA_REPO_ROOT"
LOCAL_MANUSCRIPTS_ENV = "LLM_MCDA_LOCAL_MANUSCRIPTS_DIR"
LOCAL_DOCUMENTATION_ENV = "LLM_MCDA_LOCAL_DOCUMENTATION_DIR"
RUN_OUTPUT_DIR_ENV = "LLM_MCDA_RUN_OUTPUT_DIR"


_FROZEN_OUTPUT_PREFIXES = (
    ("analysis",),
    ("archive",),
    ("paper",),
    ("workbooks", "ground_truth"),
    ("workbooks", "older_runs"),
    ("workbooks", "scenarios"),
)


class UnsafeOutputPathError(ValueError):
    """Raised when an output destination is missing or targets frozen data."""


def _output_destination(value: str | Path | None, *, option: str, root: str | Path | None) -> tuple[Path, Path]:
    if value is None or not str(value).strip():
        raise UnsafeOutputPathError(
            f"An explicit {option} is required. Choose a scratch or run-specific "
            "directory outside frozen repository paths."
        )
    base = Path(root).expanduser().resolve() if root is not None else repository_root()
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = base / candidate
    return candidate.resolve(), base


def _reject_frozen_output_destination(destination: Path, base: Path, *, option: str) -> None:
    try:
        relative = destination.relative_to(base)
    except ValueError:
        return

    parts = tuple(part.casefold() for part in relative.parts)
    if not parts:
        raise UnsafeOutputPathError(
            f"{option} resolves to the repository root. Choose a dedicated scratch "
            "or run-specific destination."
        )
    frozen = any(parts[: len(prefix)] == prefix for prefix in _FROZEN_OUTPUT_PREFIXES)
    frozen = frozen or parts[0].startswith("output files")
    if frozen:
        shown = relative.as_posix()
        raise UnsafeOutputPathError(
            f"{option} resolves into frozen repository data ({shown}). Choose a "
            "scratch or run-specific destination outside Analysis/, archive/, paper/, "
            "Output Files*/, and frozen workbook inputs."
        )


def require_safe_output_directory(
    value: str | Path | None,
    *,
    option: str = "--output-dir",
    root: str | Path | None = None,
) -> Path:
    """Require an explicit output directory outside known frozen paths.

    Relative paths are rooted at the repository. Resolution follows existing
    symlinks before checking the frozen-path rules, so an apparently safe alias
    cannot redirect writes into a protected directory.
    """
    destination, base = _output_destination(value, option=option, root=root)
    _reject_frozen_output_destination(destination, base, option=option)
    if destination.exists():
        if not destination.is_dir():
            raise UnsafeOutputPathError(
                f"{option} already exists and is not a directory: {destination}. "
                "Choose a new output directory."
            )
    return destination


def require_safe_output_path(
    value: str | Path | None,
    *,
    option: str = "--output",
    root: str | Path | None = None,
) -> Path:
    """Require an explicit output file outside frozen paths.

    Existing regular files are valid destinations so callers can resume or
    recompute outputs. A directory (including a symlink resolved to a
    directory) cannot be used as a file target.
    """
    if value is None or not str(value).strip():
        raise UnsafeOutputPathError(
            f"An explicit {option} is required. Choose a destination outside frozen repository paths."
        )
    destination, base = _output_destination(value, option=option, root=root)
    if not destination.name:
        raise UnsafeOutputPathError(f"{option} must name a file, not a directory: {destination}")
    _reject_frozen_output_destination(destination, base, option=option)
    if destination.exists() and destination.is_dir():
        raise UnsafeOutputPathError(
            f"{option} target is a directory: {destination}. Choose a file destination."
        )
    return destination


def repository_root(start: str | Path | None = None) -> Path:
    """Find the checkout root independently of the process working directory.

    Set LLM_MCDA_REPO_ROOT when this package is imported from an installed
    location that is no longer nested inside the source checkout.
    """
    override = os.environ.get(REPOSITORY_ROOT_ENV)
    if override:
        root = Path(override).expanduser().resolve()
        if not root.is_dir():
            raise RuntimeError(f"{REPOSITORY_ROOT_ENV} does not name a directory: {root}")
        return root

    origin = Path(start).expanduser().resolve() if start is not None else Path(__file__).resolve()
    if origin.is_file() or origin.suffix:
        origin = origin.parent
    for candidate in (origin, *origin.parents):
        has_package = (candidate / "src" / "llm_mcda").is_dir()
        has_metadata = (candidate / "requirements.txt").is_file() and (
            (candidate / ".gitattributes").is_file() or has_package
        )
        if has_metadata:
            return candidate
    raise RuntimeError(
        "Cannot locate the repository root from "
        f"{origin}; set {REPOSITORY_ROOT_ENV} for an installed package."
    )


def repository_path(*parts: str, root: str | Path | None = None) -> Path:
    """Resolve a repository-relative path from the checkout root."""
    if any(Path(part).is_absolute() for part in parts):
        raise ValueError("repository_path accepts relative path components only")
    base = Path(root).expanduser().resolve() if root is not None else repository_root()
    return base.joinpath(*parts)


def _local_root(env_name: str, default_name: str) -> Path:
    base = repository_root()
    override = os.environ.get(env_name)
    if override:
        candidate = Path(override).expanduser()
        if not candidate.is_absolute():
            candidate = base / candidate
    else:
        candidate = base / default_name

    resolved = candidate.resolve()
    _reject_frozen_output_destination(resolved, base, option=env_name)
    return resolved


def local_manuscripts_root() -> Path:
    """Return the ignored manuscript-copy root for this checkout."""
    return _local_root(LOCAL_MANUSCRIPTS_ENV, "local_manuscripts")


def local_documentation_root() -> Path:
    """Return the ignored archival-document root for this checkout."""
    return _local_root(LOCAL_DOCUMENTATION_ENV, "local_documentation")


def _local_file(root: Path, *parts: str) -> Path:
    if any(Path(part).is_absolute() for part in parts):
        raise ValueError("local-only file paths must be relative")
    target = root.joinpath(*parts).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("local-only path escapes its configured root") from exc
    return target


def local_manuscript_path(*parts: str) -> Path:
    """Resolve a local-only manuscript input without requiring it to exist."""
    return _local_file(local_manuscripts_root(), *parts)


def local_manuscript_input_path(*parts: str) -> Path:
    """Prefer a local-only copy and fall back to an existing repository copy."""
    local = local_manuscript_path(*parts)
    if local.is_file():
        return local
    repository_copy = repository_path(*parts)
    if repository_copy.is_file():
        return repository_copy
    return local


def require_local_manuscript_path(*parts: str) -> Path:
    """Resolve a local-only input or raise a clear error when it is unavailable."""
    path = local_manuscript_path(*parts)
    if not path.is_file():
        relative = "/".join(parts)
        raise FileNotFoundError(
            f"Required local-only manuscript input is missing: {path}. "
            f"Restore {relative} under local_manuscripts/ or set "
            f"{LOCAL_MANUSCRIPTS_ENV}."
        )
    return path


def local_documentation_path(*parts: str) -> Path:
    """Resolve a local-only documentation input without requiring it to exist."""
    return _local_file(local_documentation_root(), *parts)


__all__ = [
    "LOCAL_DOCUMENTATION_ENV",
    "LOCAL_MANUSCRIPTS_ENV",
    "REPOSITORY_ROOT_ENV",
    "RUN_OUTPUT_DIR_ENV",
    "UnsafeOutputPathError",
    "local_documentation_path",
    "local_documentation_root",
    "local_manuscript_input_path",
    "local_manuscript_path",
    "require_local_manuscript_path",
    "local_manuscripts_root",
    "repository_path",
    "repository_root",
    "require_safe_output_directory",
    "require_safe_output_path",
]
