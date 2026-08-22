"""
Supabase client singleton.
All backend services import `sb` from here to query the database.
"""
from __future__ import annotations

import os
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

_client = None


def get_client():
    """Return (and lazily initialise) the Supabase client singleton."""
    global _client
    if _client is not None:
        return _client

    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_KEY", "")

    if not url or not key or "YOUR_SUPABASE" in url or "YOUR_SUPABASE" in key:
        logger.warning(
            "SUPABASE_URL / SUPABASE_SERVICE_KEY not configured. "
            "All DB operations will be skipped (in-memory fallback active)."
        )
        return None

    try:
        from supabase import create_client, Client  # type: ignore
        _client = create_client(url, key)
        logger.info(f"Supabase client initialised → {url}")
        return _client
    except Exception as exc:
        logger.error(f"Failed to initialise Supabase client: {exc}")
        return None


# Convenience shortcut — may be None if not configured
sb = get_client()
