import argparse
import os
import sys
import time
import logging
from pathlib import Path
from dotenv import load_dotenv

IMPORT_ROOT = Path(__file__).resolve().parents[2]
if str(IMPORT_ROOT) not in sys.path:
    sys.path.insert(0, str(IMPORT_ROOT))

from common.paths import (
    RUN_OUTPUT_DIR_ENV,
    UnsafeOutputPathError,
    repository_root,
    require_safe_output_directory,
)
PROJECT_ROOT = repository_root(start=__file__)
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from common.model_config import MODEL_KEY, get_model_id

ARCHITECTURES = (
    "Example-Guided_LLM_Scoring",
    "Direct_LLM_Scoring",
    "LLM-Parameterized_Reference_Scoring",
)


def run_architecture(architecture_name: str, output_dir: Path) -> None:
    """Import and run a single architecture's main() function.

    Each architecture module reads API_CONFIG from model_config at import
    time, so no override is needed here — the shared model_config is the
    canonical record of model ID, temperature, and reasoning payload.

    Note: importing Example-Guided_LLM_Scoring triggers a SentenceTransformer
    load (all-MiniLM-L6-v2, ~90 MB).  On first run this downloads the model
    from HuggingFace and can take 30-60 s with no visible output from
    run_benchmarks.py — this is expected, not a stall.
    """
    logger.info(f"  Importing {architecture_name} ...")
    from importlib.util import module_from_spec, spec_from_file_location

    architecture_path = (
        PROJECT_ROOT / "architectures" / f"{architecture_name}.py"
    )
    module_name = f"architectures.{architecture_name}"
    spec = spec_from_file_location(module_name, architecture_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load architecture module {architecture_path}")
    arch_module = module_from_spec(spec)
    spec.loader.exec_module(arch_module)
    logger.info(f"  Import complete. Starting {architecture_name}.main() ...")

    arch_module.main(["--output-dir", str(output_dir)])


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(
        description="Run the three LLM-MCDA architecture benchmarks."
    )
    parser.add_argument(
        "--output-dir",
        default=os.environ.get(RUN_OUTPUT_DIR_ENV),
        help=(
            f"Required safe output directory for all architecture results "
            f"(or set {RUN_OUTPUT_DIR_ENV})."
        ),
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List the architectures that will run and exit.",
    )
    args = parser.parse_args(argv)
    if args.list:
        print("Architectures:")
        for architecture in ARCHITECTURES:
            print(f"- {architecture}")
        return

    try:
        output_dir = require_safe_output_directory(
            args.output_dir,
            option=f"--output-dir (or {RUN_OUTPUT_DIR_ENV})",
            root=PROJECT_ROOT,
        )
    except UnsafeOutputPathError as exc:
        parser.error(str(exc))

    model_id = get_model_id()
    logger.info("=" * 60)
    logger.info(f"run_benchmarks.py  |  MODEL_KEY={MODEL_KEY}")
    logger.info(f"  model    : {model_id}")
    logger.info(f"  outputs  : {output_dir}")
    logger.info("=" * 60)

    overall_start = time.time()
    for arch in ARCHITECTURES:
        logger.info(f"\n{'-' * 60}")
        logger.info(f"Starting : {arch}")
        logger.info(f"{'-' * 60}")
        t0 = time.time()
        try:
            run_architecture(arch, output_dir)
            elapsed = time.time() - t0
            logger.info(f"Finished : {arch}  ({elapsed:.1f}s)")
        except Exception as exc:
            elapsed = time.time() - t0
            logger.error(f"FAILED   : {arch}  ({elapsed:.1f}s) - {exc}")
            raise

    total = time.time() - overall_start
    logger.info(f"\n{'=' * 60}")
    logger.info(f"All benchmarks complete  ({total:.1f}s total)")
    logger.info(f"{'=' * 60}")


if __name__ == "__main__":
    main()
