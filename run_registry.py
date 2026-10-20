"""Run registry loading and validation."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from common.paths import repository_root

SCHEMA_VERSION = "1.1"
_UNKNOWN = "unknown"
_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_CHUNK_SIZE = 1024 * 1024


class RegistryError(ValueError):
    """The registry is missing, malformed, or internally inconsistent."""


class ArtifactVerificationError(RegistryError):
    """One or more artifacts for a run are missing or have drifted."""


REPOSITORY_ROOT = repository_root(start=Path(__file__))
DEFAULT_REGISTRY_PATH = REPOSITORY_ROOT / "manifests" / "run-registry.json"


def _fail(where: str, message: str) -> None:
    raise RegistryError(f"Invalid run registry at {where}: {message}")


def _require_string(value: Any, where: str, *, allow_unknown: bool = True) -> None:
    if not isinstance(value, str) or not value:
        _fail(where, "expected a non-empty string")
    if not allow_unknown and value == _UNKNOWN:
        _fail(where, "'unknown' is not allowed here")


def _validate_sha256(value: Any, where: str) -> None:
    if value == _UNKNOWN:
        return
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        _fail(where, "expected a lowercase 64-character SHA-256 hex digest or 'unknown'")


def _validate_registry(registry: Any) -> None:
    if not isinstance(registry, dict):
        _fail("$", "top-level JSON value must be an object")
    required = {
        "schema_version", "current_run_status", "current_run_ids", "current_experiment_run_ids", "runs"
    }
    missing = sorted(required.difference(registry))
    if missing:
        _fail("$", f"missing required field(s): {', '.join(missing)}")
    if registry["schema_version"] != SCHEMA_VERSION:
        _fail("schema_version", f"expected {SCHEMA_VERSION!r}, got {registry['schema_version']!r}")

    pin_status = registry["current_run_status"]
    _require_string(pin_status, "current_run_status", allow_unknown=False)
    if pin_status not in {"deferred", "pinned"}:
        _fail("current_run_status", "expected 'deferred' or 'pinned'")
    if "current_run_status_note" in registry:
        _require_string(registry["current_run_status_note"], "current_run_status_note", allow_unknown=False)
    if pin_status == "deferred" and "current_run_status_note" not in registry:
        _fail("current_run_status_note", "required while current_run_status is deferred")

    for map_name in ("current_run_ids", "current_experiment_run_ids"):
        mapping = registry[map_name]
        if not isinstance(mapping, dict):
            _fail(map_name, "expected an object mapping keys to run IDs")
        for key, run_id in mapping.items():
            _require_string(key, f"{map_name} key", allow_unknown=False)
            _require_string(run_id, f"{map_name}[{key!r}]", allow_unknown=False)
            if not _RUN_ID_RE.fullmatch(run_id):
                _fail(f"{map_name}[{key!r}]", f"invalid run_id {run_id!r}")

    if pin_status == "deferred" and (registry["current_run_ids"] or registry["current_experiment_run_ids"]):
        _fail("current_run_status", "deferred selection requires both current-run maps to be empty")

    runs = registry["runs"]
    if not isinstance(runs, list):
        _fail("runs", "expected an array of run records")
    by_id: dict[str, dict[str, Any]] = {}
    for run_index, run in enumerate(runs):
        where = f"runs[{run_index}]"
        if not isinstance(run, dict):
            _fail(where, "expected an object")
        required_run_fields = {
            "run_id", "model_key", "model_id", "requested_provider",
            "observed_provider", "scenario_ids", "scenario_source_refs",
            "prompt_hashes", "timestamp_utc", "files",
        }
        absent = sorted(required_run_fields.difference(run))
        if absent:
            _fail(where, f"missing required field(s): {', '.join(absent)}")

        run_id = run["run_id"]
        _require_string(run_id, f"{where}.run_id", allow_unknown=False)
        if not _RUN_ID_RE.fullmatch(run_id):
            _fail(f"{where}.run_id", f"invalid run_id {run_id!r}")
        if run_id in by_id:
            _fail(f"{where}.run_id", f"duplicate run_id {run_id!r}")
        by_id[run_id] = run

        for field in ("model_key", "model_id"):
            _require_string(run[field], f"{where}.{field}")
        if "experiment_key" in run:
            _require_string(run["experiment_key"], f"{where}.experiment_key")

        requested_provider = run["requested_provider"]
        if requested_provider != _UNKNOWN:
            if isinstance(requested_provider, str):
                _require_string(requested_provider, f"{where}.requested_provider", allow_unknown=False)
            elif isinstance(requested_provider, dict):
                provider_fields = {"only", "allow_fallbacks", "require_parameters"}
                if set(requested_provider) != provider_fields:
                    _fail(f"{where}.requested_provider", "provider object must contain only, allow_fallbacks, and require_parameters")
                only = requested_provider["only"]
                if not isinstance(only, list) or not only or not all(isinstance(x, str) and x for x in only):
                    _fail(f"{where}.requested_provider.only", "expected a non-empty array of provider names")
                for field in ("allow_fallbacks", "require_parameters"):
                    if not isinstance(requested_provider[field], bool):
                        _fail(f"{where}.requested_provider.{field}", "expected a boolean")
            else:
                _fail(f"{where}.requested_provider", "expected a string, provider object, or 'unknown'")

        observed_provider = run["observed_provider"]
        if observed_provider != _UNKNOWN:
            if isinstance(observed_provider, str):
                _require_string(observed_provider, f"{where}.observed_provider", allow_unknown=False)
            elif isinstance(observed_provider, list):
                if not all(isinstance(item, str) and item for item in observed_provider):
                    _fail(f"{where}.observed_provider", "expected non-empty provider names")
            else:
                _fail(f"{where}.observed_provider", "expected a provider name, an array of names, or 'unknown'")

        scenario_ids = run["scenario_ids"]
        if scenario_ids != _UNKNOWN:
            if not isinstance(scenario_ids, list):
                _fail(f"{where}.scenario_ids", "expected an array or 'unknown'")
            if not all((isinstance(item, str) and item) or type(item) is int for item in scenario_ids):
                _fail(f"{where}.scenario_ids", "each scenario ID must be a non-empty string or integer")

        source_refs = run["scenario_source_refs"]
        if source_refs != _UNKNOWN:
            if not isinstance(source_refs, list):
                _fail(f"{where}.scenario_source_refs", "expected an array or 'unknown'")
            for ref_index, ref in enumerate(source_refs):
                ref_where = f"{where}.scenario_source_refs[{ref_index}]"
                if not isinstance(ref, dict) or not {"path", "sha256"}.issubset(ref):
                    _fail(ref_where, "each source reference must have path and sha256")
                _require_string(ref["path"], f"{ref_where}.path", allow_unknown=False)
                _validate_sha256(ref["sha256"], f"{ref_where}.sha256")
                if "role" in ref:
                    _require_string(ref["role"], f"{ref_where}.role")

        prompt_hashes = run["prompt_hashes"]
        if prompt_hashes != _UNKNOWN:
            if not isinstance(prompt_hashes, list):
                _fail(f"{where}.prompt_hashes", "expected an array or 'unknown'")
            for prompt_index, prompt in enumerate(prompt_hashes):
                prompt_where = f"{where}.prompt_hashes[{prompt_index}]"
                if not isinstance(prompt, dict) or not {"prompt_id", "sha256"}.issubset(prompt):
                    _fail(prompt_where, "each prompt hash must have prompt_id and sha256")
                _require_string(prompt["prompt_id"], f"{prompt_where}.prompt_id", allow_unknown=False)
                _validate_sha256(prompt["sha256"], f"{prompt_where}.sha256")

        timestamp = run["timestamp_utc"]
        _require_string(timestamp, f"{where}.timestamp_utc")
        if timestamp != _UNKNOWN:
            try:
                parsed_timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except ValueError:
                _fail(f"{where}.timestamp_utc", "expected an ISO 8601/RFC 3339 timestamp with timezone, or 'unknown'")
            if parsed_timestamp.tzinfo is None or parsed_timestamp.utcoffset() is None:
                _fail(f"{where}.timestamp_utc", "timestamp must include a UTC offset")

        files = run["files"]
        if not isinstance(files, list):
            _fail(f"{where}.files", "expected an array")
        seen_paths: set[str] = set()
        for file_index, record in enumerate(files):
            file_where = f"{where}.files[{file_index}]"
            if not isinstance(record, dict):
                _fail(file_where, "expected an artifact object")
            required_file_fields = {"path", "sha256", "size_bytes", "kind", "role"}
            absent_file_fields = sorted(required_file_fields.difference(record))
            if absent_file_fields:
                _fail(file_where, f"missing required field(s): {', '.join(absent_file_fields)}")
            rel = record["path"]
            _require_string(rel, f"{file_where}.path", allow_unknown=False)
            _relative_artifact_parts(rel, file_where)
            if rel in seen_paths:
                _fail(f"{file_where}.path", f"duplicate artifact path {rel!r} in one run")
            seen_paths.add(rel)
            _validate_sha256(record["sha256"], f"{file_where}.sha256")
            size = record["size_bytes"]
            if size != _UNKNOWN and (type(size) is not int or size < 0):
                _fail(f"{file_where}.size_bytes", "expected a non-negative integer or 'unknown'")
            for field in ("kind", "role"):
                _require_string(record[field], f"{file_where}.{field}")

    if pin_status == "pinned" and not (registry["current_run_ids"] or registry["current_experiment_run_ids"]):
        _fail("current_run_status", "pinned selection requires at least one current run ID")

    for model_key, run_id in registry["current_run_ids"].items():
        selected = by_id.get(run_id)
        if selected is None:
            _fail(f"current_run_ids[{model_key!r}]", f"references missing run_id {run_id!r}")
        if selected["model_key"] != model_key:
            _fail(f"current_run_ids[{model_key!r}]", f"run {run_id!r} has model_key {selected['model_key']!r}")

    for experiment_key, run_id in registry["current_experiment_run_ids"].items():
        selected = by_id.get(run_id)
        if selected is None:
            _fail(f"current_experiment_run_ids[{experiment_key!r}]", f"references missing run_id {run_id!r}")
        if selected.get("experiment_key") != experiment_key:
            _fail(f"current_experiment_run_ids[{experiment_key!r}]", f"run {run_id!r} has experiment_key {selected.get('experiment_key')!r}")


def load_registry(path: str | Path | None = None) -> dict[str, Any]:
    """Read and structurally validate the registry JSON.

    Args:
        path: Optional explicit registry path. Relative paths are resolved from
            the process working directory; the default is repository-root based.

    Raises:
        RegistryError: If the file is missing, invalid JSON, or inconsistent.
    """
    registry_path = Path(path).expanduser() if path is not None else DEFAULT_REGISTRY_PATH
    try:
        with registry_path.open("r", encoding="utf-8") as handle:
            registry = json.load(handle)
    except FileNotFoundError as exc:
        raise RegistryError(f"Run registry not found: {registry_path}") from exc
    except json.JSONDecodeError as exc:
        raise RegistryError(
            f"Run registry contains invalid JSON at {registry_path}:{exc.lineno}:{exc.colno}: {exc.msg}"
        ) from exc
    except OSError as exc:
        raise RegistryError(f"Cannot read run registry {registry_path}: {exc}") from exc
    _validate_registry(registry)
    return registry


def current_run_id(model_key: str) -> str:
    """Return the run ID pinned as current for ``model_key``."""
    _require_string(model_key, "model_key", allow_unknown=False)
    registry = load_registry()
    if registry["current_run_status"] == "deferred":
        reason = registry["current_run_status_note"]
        raise RegistryError(f"Current-run selection is deferred: {reason}")
    try:
        return registry["current_run_ids"][model_key]
    except KeyError as exc:
        raise RegistryError(f"No pinned current run for model_key {model_key!r}") from exc


def get_run(run_id: str) -> dict[str, Any]:
    """Return the run record for ``run_id``."""
    _require_string(run_id, "run_id", allow_unknown=False)
    for run in load_registry()["runs"]:
        if run["run_id"] == run_id:
            return run
    raise RegistryError(f"Run registry has no record for run_id {run_id!r}")


def files_for_run(
    run_id: str, kind: str | None = None, role: str | None = None
) -> list[dict[str, Any]]:
    """Return a run's artifact records, optionally filtered by kind and role."""
    run = get_run(run_id)
    return [
        record for record in run["files"]
        if (kind is None or record["kind"] == kind)
        and (role is None or record["role"] == role)
    ]


def _relative_artifact_parts(relative_path: str, where: str = "artifact path") -> tuple[str, ...]:
    """Validate and split a repository-relative POSIX path safely."""
    if not relative_path or "\\" in relative_path or "\x00" in relative_path:
        _fail(where, "expected a non-empty repository-relative POSIX path")
    pure = PurePosixPath(relative_path)
    parts = tuple(relative_path.split("/"))
    if (
        pure.is_absolute()
        or relative_path.startswith("//")
        or ":" in parts[0]
        or any(part in ("", ".", "..") for part in parts)
    ):
        _fail(where, f"unsafe repository-relative path {relative_path!r}")
    return parts


def _artifact_path(file_record: Mapping[str, Any]) -> Path:
    relative = file_record.get("path")
    _require_string(relative, "artifact path", allow_unknown=False)
    parts = _relative_artifact_parts(relative)
    root = REPOSITORY_ROOT.resolve()
    target = root.joinpath(*parts).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise RegistryError(f"Artifact path escapes the repository root: {relative!r}") from exc
    return target


def artifact_path(run_id: str, file_record: Mapping[str, Any]) -> Path:
    """Resolve a listed artifact to a safe absolute path inside this checkout."""
    if not isinstance(file_record, Mapping):
        raise TypeError("file_record must be an artifact mapping from the run registry")
    run = get_run(run_id)
    if file_record not in run["files"]:
        raise RegistryError(f"Artifact record is not listed under run_id {run_id!r}")
    return _artifact_path(file_record)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_run(run_id: str) -> bool:
    """Verify all listed artifact sizes and SHA-256 hashes for ``run_id``.

    Returns ``True`` only when every artifact is verifiable and matches the
    registry. Unknown hashes and missing files are reported as verification
    failures rather than silently treated as verified.
    """
    run = get_run(run_id)
    failures: list[str] = []
    for record in run["files"]:
        relative = record["path"]
        expected_hash = record["sha256"]
        if expected_hash == _UNKNOWN:
            failures.append(f"{relative}: SHA-256 is 'unknown'; cannot verify this artifact")
            continue
        path = _artifact_path(record)
        if not path.is_file():
            failures.append(f"{relative}: file is missing")
            continue
        try:
            actual_size = path.stat().st_size
            actual_hash = _file_sha256(path)
        except OSError as exc:
            failures.append(f"{relative}: cannot read file ({exc})")
            continue
        expected_size = record["size_bytes"]
        if expected_size != _UNKNOWN and actual_size != expected_size:
            failures.append(
                f"{relative}: size drift (registry {expected_size} bytes, disk {actual_size} bytes)"
            )
        if actual_hash != expected_hash:
            failures.append(
                f"{relative}: SHA-256 drift (registry {expected_hash}, disk {actual_hash})"
            )
    if failures:
        details = "\n".join(f"  - {message}" for message in failures)
        raise ArtifactVerificationError(f"Artifact verification failed for run_id {run_id!r}:\n{details}")
    return True


__all__ = [
    "ArtifactVerificationError",
    "DEFAULT_REGISTRY_PATH",
    "REPOSITORY_ROOT",
    "RegistryError",
    "artifact_path",
    "current_run_id",
    "files_for_run",
    "get_run",
    "load_registry",
    "verify_run",
]