"""Shared initialization for architecture modules."""

import os

from dotenv import load_dotenv

load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")


def has_openrouter_api_key() -> bool:
    return bool(OPENROUTER_API_KEY)
