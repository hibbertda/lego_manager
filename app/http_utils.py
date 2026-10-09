# Shared HTTP helpers for talking to third-party set/part data APIs
# (Brickset, Rebrickable). Factored out of brickset_ops.py so rebrickable_ops.py
# doesn't have to duplicate the same retrying-session/streamed-download logic.
from __future__ import annotations

import logging
import os

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 10  # seconds
DEFAULT_MAX_DOWNLOAD_BYTES = 25 * 1024 * 1024


def build_session() -> requests.Session:
    """A requests.Session with retry/backoff for transient network errors."""
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def download_file(
    session: requests.Session,
    url: str,
    path: str,
    max_bytes: int = DEFAULT_MAX_DOWNLOAD_BYTES,
    timeout: int = REQUEST_TIMEOUT,
) -> bool:
    try:
        response = session.get(url, timeout=timeout, stream=True)
        response.raise_for_status()
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > max_bytes:
            logger.warning("Download exceeds size limit: %s", url)
            return False
        total = 0
        with open(path, "wb") as file:
            for chunk in response.iter_content(chunk_size=64 * 1024):
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError("download exceeds size limit")
                file.write(chunk)
        return True
    except (requests.RequestException, OSError, ValueError):
        logger.exception("Failed to download: %s", url)
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        return False
