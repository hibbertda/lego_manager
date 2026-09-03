# Classes for interacting with the Brickset API (https://brickset.com/api/v3.asmx)
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from typing import Any, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 10  # seconds
DEFAULT_MAX_DOWNLOAD_BYTES = 25 * 1024 * 1024

# LEGO instruction descriptions look like "BI 3106, 148+4, 75350 V29" where the
# trailing "V<n>" is a revision number. Brickset lists every historical
# revision LEGO has published for the same physical booklet.
_VERSION_SUFFIX_RE = re.compile(r"^(?P<booklet>.*)\s+V(?P<version>\d+)$")


def _dedupe_instructions(instructions: list[dict[str, Any]]) -> list[str]:
    """Keep only the newest revision of each physical instruction booklet.

    Brickset's getInstructions can list the same booklet several times, once
    per LEGO CDN revision (e.g. "...V29" and "...V39"), and multi-booklet sets
    (e.g. "1/2"/"2/2") are kept distinct since their booklet identifier differs.
    """
    best_by_booklet: dict[str, tuple[int, int, str]] = {}
    for instr in instructions:
        url = instr["URL"]
        description = instr.get("description") or url
        match = _VERSION_SUFFIX_RE.match(description)
        if match:
            booklet, version = match.group("booklet"), int(match.group("version"))
        else:
            booklet, version = description, 0

        asset_id_str = os.path.splitext(os.path.basename(url))[0]
        try:
            asset_id = int(asset_id_str)
        except ValueError:
            asset_id = 0

        current = best_by_booklet.get(booklet)
        if current is None or (version, asset_id) > (current[0], current[1]):
            best_by_booklet[booklet] = (version, asset_id, url)
    return [url for _, _, url in best_by_booklet.values()]


def _build_session() -> requests.Session:
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


class BricksetAPI:
    def __init__(self, api_key: Optional[str]):
        self.api_key = api_key or ""
        self.session = _build_session()
        self._userhash_cache: dict[bytes, str] = {}
        self._cache_salt = os.urandom(16)

    def configure(self, api_key: str) -> None:
        """Update the API key at runtime (e.g. after an admin saves new settings)."""
        self.api_key = api_key
        self._userhash_cache.clear()

    def get_instructions(self, set_id: int) -> Optional[list[dict[str, Any]]]:
        logger.info("Fetching instructions for set ID: %s", set_id)
        base_url = "https://brickset.com/api/v3.asmx/getInstructions"
        params = {"setID": str(set_id), "apikey": self.api_key}
        try:
            response = self.session.get(
                base_url, params=params, timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
        except requests.RequestException:
            logger.exception("Failed to fetch instructions for set ID: %s", set_id)
            return None
        return response.json().get("instructions", [])

    def get_login(self, username: str, password: str) -> Optional[str]:
        """Log in and return a userhash, reusing a cached hash for the same credentials."""
        cache_key = hashlib.scrypt(
            f"{username}:{password}".encode(),
            salt=self._cache_salt,
            n=2**14,
            r=8,
            p=1,
        )
        if cache_key in self._userhash_cache:
            logger.info("Reusing cached userhash for user: %s", username)
            return self._userhash_cache[cache_key]

        logger.info("Logging in user: %s", username)
        base_url = "https://brickset.com/api/v3.asmx/login"
        params = {"apiKey": self.api_key, "username": username, "password": password}
        try:
            response = self.session.get(
                base_url, params=params, timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
        except requests.RequestException:
            logger.exception("Failed to log in user: %s", username)
            return None

        userhash = response.json().get("hash")
        if userhash:
            self._userhash_cache[cache_key] = userhash
        return userhash

    def get_sets(
        self, set_number: str, userhash: Optional[str] = None
    ) -> Optional[dict[str, Any]]:
        """Look up a set by number. `userhash` is only needed for owned/wanted
        collection filters, which this app doesn't use, so it's optional."""
        logger.info("Fetching set information for set number: %s", set_number)
        base_url = "https://brickset.com/api/v3.asmx/getSets"
        params = {
            "apiKey": self.api_key,
            "userHash": userhash or "",
            "params": json.dumps({"setNumber": set_number + "-1"}),
        }
        try:
            response = self.session.get(
                base_url, params=params, timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
        except requests.RequestException:
            logger.exception(
                "Failed to fetch set information for set number: %s", set_number
            )
            return None
        return response.json()

    def _download_file(self, url: str, path: str, max_bytes: int) -> bool:
        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT, stream=True)
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

    def download_images(
        self,
        set_data: dict[str, Any],
        base_dir: str = "sets",
        max_bytes: int = DEFAULT_MAX_DOWNLOAD_BYTES,
    ) -> None:
        set_number = set_data.get("number")
        if not set_number:
            return

        logger.info("Downloading images for set number: %s", set_number)
        set_dir = os.path.join(base_dir, set_number)
        images_dir = os.path.join(set_dir, "images")
        os.makedirs(images_dir, exist_ok=True)

        image_url = set_data["image"]["imageURL"]
        local_image_paths = []

        image_name = os.path.basename(image_url)
        local_path = os.path.join(images_dir, image_name)
        if self._download_file(image_url, local_path, max_bytes):
            local_image_paths.append(os.path.join(set_number, "images", image_name))
            logger.info("Downloaded image: %s", local_path)

        set_data["local_images"] = local_image_paths

    def download_instructions(
        self,
        set_data: dict[str, Any],
        base_dir: str = "sets",
        max_bytes: int = DEFAULT_MAX_DOWNLOAD_BYTES,
    ) -> None:
        set_number = set_data.get("number")
        if not set_number:
            return

        logger.info("Downloading instructions for set number: %s", set_number)
        set_dir = os.path.join(base_dir, set_number)
        instructions_dir = os.path.join(set_dir, "instructions")
        os.makedirs(instructions_dir, exist_ok=True)

        core_instructions = [
            instr
            for instr in (set_data.get("instructions") or [])
            if "product.bi.core.pdf" in instr["URL"]
        ]
        instruction_urls = _dedupe_instructions(core_instructions)
        local_instruction_paths = []

        for url in instruction_urls:
            pdf_name = os.path.basename(url)
            local_path = os.path.join(instructions_dir, pdf_name)
            if not self._download_file(url, local_path, max_bytes):
                continue
            local_instruction_paths.append(
                os.path.join(set_number, "instructions", pdf_name)
            )
            logger.info("Downloaded instruction: %s", local_path)

        set_data["local_instructions"] = local_instruction_paths

    def get_combined_data(
        self,
        set_number: str,
        userhash: Optional[str] = None,
        base_dir: str = "sets",
        max_bytes: int = DEFAULT_MAX_DOWNLOAD_BYTES,
    ) -> Optional[dict[str, Any]]:
        logger.info("Combining data for set number: %s", set_number)
        set_info = self.get_sets(set_number, userhash=userhash)
        if not set_info or not set_info.get("sets"):
            logger.error("Failed to combine data for set number: %s", set_number)
            return None

        set_id = set_info["sets"][0].get("setID")
        set_info["sets"][0]["instructions"] = self.get_instructions(set_id)
        self.download_images(set_info["sets"][0], base_dir, max_bytes)
        self.download_instructions(set_info["sets"][0], base_dir, max_bytes)

        set_dir = os.path.join(base_dir, set_number)
        os.makedirs(set_dir, exist_ok=True)
        combined_json_path = os.path.join(set_dir, "combined_data.json")
        with open(combined_json_path, "w") as f:
            json.dump(set_info, f, indent=4)
        logger.info("Combined data saved to: %s", combined_json_path)

        return set_info
