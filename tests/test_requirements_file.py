from pathlib import Path

from packaging.requirements import Requirement


def test_requirements_file_has_no_utf8_bom_and_valid_specs() -> None:
    requirements_path = Path(__file__).resolve().parents[1] / "requirements.txt"
    raw = requirements_path.read_bytes()

    assert not raw.startswith(b"\xef\xbb\xbf"), "requirements.txt must not have a UTF-8 BOM"

    text = raw.decode("utf-8")
    for line in text.splitlines():
        spec = line.strip()
        if not spec or spec.startswith("#"):
            continue
        Requirement(spec)
