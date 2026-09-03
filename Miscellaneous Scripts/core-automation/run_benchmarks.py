import os
import sys
import time
import logging
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from model_config import MODEL_KEY, get_model_id, get_output_folder


def run_architecture(architecture_name: str) -> None:
    """Import and run a single architecture's main() function.

    Each architecture module reads API_CONFIG from model_config at import
    time, so no override is needed here — the shared model_config is the
    single source of truth for model ID, temperature, and reasoning payload.

    Note: importing Example-Guided_LLM_Scoring triggers a SentenceTransformer
    load (all-MiniLM-L6-v2, ~90 MB).  On first run this downloads the model
    from HuggingFace and can take 30-60 s with no visible output from
    run_benchmarks.py — this is expected, not a stall.
    """
    from importlib import import_module

    logger.info(f"  Importing {architecture_name} ...")
    arch_module = import_module(f"Architectures.{architecture_name}")
    logger.info(f"  Import complete. Starting {architecture_name}.main() ...")

    arch_module.main()


def main() -> None:
    model_id = get_model_id()
    output_folder = get_output_folder()
    logger.info("=" * 60)
    logger.info(f"run_benchmarks.py  |  MODEL_KEY={MODEL_KEY}")
    logger.info(f"  model    : {model_id}")
    logger.info(f"  outputs  : {output_folder}")
    logger.info("=" * 60)

    architectures = [
        "Example-Guided_LLM_Scoring",
        "Direct_LLM_Scoring",
        "LLM-Parameterized_Reference_Scoring",
    ]

    overall_start = time.time()
    for arch in architectures:
        logger.info(f"\n{'─' * 60}")
        logger.info(f"Starting : {arch}")
        logger.info(f"{'─' * 60}")
        t0 = time.time()
        try:
            run_architecture(arch)
            elapsed = time.time() - t0
            logger.info(f"Finished : {arch}  ({elapsed:.1f}s)")
        except Exception as exc:
            elapsed = time.time() - t0
            logger.error(f"FAILED   : {arch}  ({elapsed:.1f}s) — {exc}")
            raise

    total = time.time() - overall_start
    logger.info(f"\n{'=' * 60}")
    logger.info(f"All benchmarks complete  ({total:.1f}s total)")
    logger.info(f"{'=' * 60}")


if __name__ == "__main__":
    main()
