# Client for the Rebrickable API (https://rebrickable.com/api/v3/docs/),
# used only to fetch a set's part-level inventory (part number, color, image,
# quantity) — data Brickset's API doesn't expose at all. See brickset_ops.py
# for the set metadata/images/instructions client.
from __future__ import annotations

import logging
import os
from typing import Any, Optional

import requests
from werkzeug.utils import secure_filename

from app.http_utils import (
    DEFAULT_MAX_DOWNLOAD_BYTES,
    REQUEST_TIMEOUT,
    build_session,
    download_file,
)

logger = logging.getLogger(__name__)

API_BASE = "https://rebrickable.com/api/v3/lego"
# Shared across every set, keyed by part number + color, so the same part
# (e.g. a common 2x4 brick) is only ever downloaded once regardless of how
# many sets include it.
PARTS_CACHE_SUBDIR = "_parts_cache"
# Same idea as PARTS_CACHE_SUBDIR but for minifig images, keyed by fig number
# (e.g. "fig-012345") — minifigs reappear across many sets too.
MINIFIGS_CACHE_SUBDIR = "_minifigs_cache"


class RebrickableAPI:
    def __init__(self, api_key: Optional[str]):
        self.api_key = api_key or ""
        self.session = build_session()

    def configure(self, api_key: str) -> None:
        """Update the API key at runtime (e.g. after an admin saves new settings)."""
        self.api_key = api_key

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"key {self.api_key}"}

    def _get_paginated(
        self, start_url: str, error_context: str
    ) -> Optional[list[dict[str, Any]]]:
        """Shared GET-and-follow-`next` loop used by both the parts and
        minifigs endpoints, which share the same Rebrickable pagination
        shape. Returns None on any request failure (distinct from an empty
        list, which means Rebrickable genuinely has no rows for this set)."""
        url: Optional[str] = start_url
        params: Optional[dict[str, Any]] = {"page_size": 1000}
        results: list[dict[str, Any]] = []
        while url:
            try:
                response = self.session.get(
                    url,
                    params=params,
                    headers=self._headers(),
                    timeout=REQUEST_TIMEOUT,
                )
                response.raise_for_status()
            except requests.RequestException:
                logger.exception("Failed to fetch %s", error_context)
                return None
            data = response.json()
            results.extend(data.get("results") or [])
            url = data.get("next")
            # `next` is already a full URL with its own query string.
            params = None
        return results

    def get_set_parts(self, set_number: str) -> Optional[list[dict[str, Any]]]:
        """Fetch every part+color line in a set's inventory, paginating as
        needed. Returns None on any request failure (distinct from an empty
        list, which means the set genuinely has no parts data on Rebrickable)."""
        logger.info("Fetching parts for set number: %s", set_number)
        return self._get_paginated(
            f"{API_BASE}/sets/{set_number}-1/parts/",
            f"parts for set number: {set_number}",
        )

    def get_set_minifigs(self, set_number: str) -> Optional[list[dict[str, Any]]]:
        """Fetch every minifig included in a set's inventory, paginating as
        needed."""
        logger.info("Fetching minifigs for set number: %s", set_number)
        return self._get_paginated(
            f"{API_BASE}/sets/{set_number}-1/minifigs/",
            f"minifigs for set number: {set_number}",
        )

    def _download_part_images(
        self,
        raw_parts: list[dict[str, Any]],
        base_dir: str,
        max_bytes: int,
    ) -> None:
        cache_dir = os.path.join(base_dir, PARTS_CACHE_SUBDIR)
        os.makedirs(cache_dir, exist_ok=True)
        for raw in raw_parts:
            part = raw.get("part") or {}
            img_url = part.get("part_img_url")
            part_num = part.get("part_num")
            color_id = (raw.get("color") or {}).get("id", 0)
            if not img_url or not part_num:
                raw["_local_image"] = None
                continue
            ext = os.path.splitext(img_url)[1] or ".jpg"
            filename = secure_filename(f"{part_num}_{color_id}{ext}")
            local_path = os.path.join(cache_dir, filename)
            if not os.path.isfile(local_path):
                if not download_file(self.session, img_url, local_path, max_bytes):
                    raw["_local_image"] = None
                    continue
            raw["_local_image"] = os.path.join(PARTS_CACHE_SUBDIR, filename)

    def get_combined_set_parts(
        self,
        set_number: str,
        base_dir: str = "sets",
        max_bytes: int = DEFAULT_MAX_DOWNLOAD_BYTES,
    ) -> Optional[list[dict[str, Any]]]:
        """Fetch + download images, then collapse spare/non-spare lines for the
        same (part_num, color) into a single row with a combined quantity —
        matches how part lists are conventionally displayed (spares are just
        extra copies of a part, not a separate thing to call out)."""
        raw_parts = self.get_set_parts(set_number)
        if raw_parts is None:
            return None

        self._download_part_images(raw_parts, base_dir, max_bytes)

        combined: dict[tuple[str, int], dict[str, Any]] = {}
        for raw in raw_parts:
            part = raw.get("part") or {}
            color = raw.get("color") or {}
            part_num = part.get("part_num") or ""
            color_id = color.get("id", 0)
            key = (part_num, color_id)
            if key not in combined:
                combined[key] = {
                    "part_num": part_num,
                    "name": part.get("name") or part_num,
                    "color_id": color_id,
                    "color_name": color.get("name") or "",
                    "quantity": 0,
                    "image_path": raw.get("_local_image"),
                }
            combined[key]["quantity"] += raw.get("quantity") or 0

        return sorted(
            combined.values(), key=lambda p: (p["name"].lower(), p["part_num"])
        )

    def _download_minifig_images(
        self,
        raw_minifigs: list[dict[str, Any]],
        base_dir: str,
        max_bytes: int,
    ) -> None:
        cache_dir = os.path.join(base_dir, MINIFIGS_CACHE_SUBDIR)
        os.makedirs(cache_dir, exist_ok=True)
        for raw in raw_minifigs:
            img_url = raw.get("img_url") or raw.get("set_img_url")
            fig_num = raw.get("set_num")
            if not img_url or not fig_num:
                raw["_local_image"] = None
                continue
            ext = os.path.splitext(img_url)[1] or ".jpg"
            filename = secure_filename(f"{fig_num}{ext}")
            local_path = os.path.join(cache_dir, filename)
            if not os.path.isfile(local_path):
                if not download_file(self.session, img_url, local_path, max_bytes):
                    raw["_local_image"] = None
                    continue
            raw["_local_image"] = os.path.join(MINIFIGS_CACHE_SUBDIR, filename)

    def get_combined_set_minifigs(
        self,
        set_number: str,
        base_dir: str = "sets",
        max_bytes: int = DEFAULT_MAX_DOWNLOAD_BYTES,
    ) -> Optional[list[dict[str, Any]]]:
        """Fetch a set's minifigs + download their images."""
        raw_minifigs = self.get_set_minifigs(set_number)
        if raw_minifigs is None:
            return None

        self._download_minifig_images(raw_minifigs, base_dir, max_bytes)

        minifigs = [
            {
                "fig_num": raw.get("set_num") or "",
                "name": raw.get("set_name") or raw.get("set_num") or "",
                "quantity": raw.get("quantity") or 0,
                "image_path": raw.get("_local_image"),
            }
            for raw in raw_minifigs
        ]
        return sorted(minifigs, key=lambda m: (m["name"].lower(), m["fig_num"]))
