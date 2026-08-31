from __future__ import annotations

import json
import logging
import sqlite3
from typing import Any, Optional

logger = logging.getLogger(__name__)

SET_COLUMNS = (
    "setID", "setNumber", "name", "year", "theme", "pieces",
    "launchDate", "instructions", "local_images", "local_instructions",
    "build_page", "build_status",
)

VALID_BUILD_STATUSES = ("not_started", "in_progress", "complete")



def _strip_sets_prefix(path: str) -> str:
    """Paths are served relative to the 'sets' directory via custom_static,
    so strip any leading 'sets/' left over from how the path was built."""
    return path[len("sets/"):] if path.startswith("sets/") else path


def row_to_dict(row: tuple) -> dict[str, Any]:
    """Map a `SET_COLUMNS`-ordered row into a JSON-decoded, path-normalized dict."""
    data = dict(zip(SET_COLUMNS, row))
    data["instructions"] = json.loads(data["instructions"]) if data["instructions"] else []
    data["local_images"] = [
        _strip_sets_prefix(p) for p in (json.loads(data["local_images"]) if data["local_images"] else [])
    ]
    data["local_instructions"] = [
        _strip_sets_prefix(p) for p in (json.loads(data["local_instructions"]) if data["local_instructions"] else [])
    ]
    data["build_page"] = data.get("build_page") or 0
    data["build_status"] = data.get("build_status") or "not_started"
    return data


class DatabaseOps:
    def __init__(self, db_name: str):
        self.db_name = db_name
        self.create_tables()

    def create_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_name)

    def create_tables(self) -> None:
        logger.info("Creating tables if they do not exist")
        with self.create_connection() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS sets (
                    setID INTEGER PRIMARY KEY,
                    numberVariant INTEGER,
                    setNumber INTEGER,
                    name TEXT,
                    year INTEGER,
                    theme TEXT,
                    pieces INTEGER,
                    launchDate TIMESTAMP,
                    instructions TEXT,
                    local_images TEXT,
                    local_instructions TEXT
                )
            ''')
            existing_columns = {row[1] for row in conn.execute("PRAGMA table_info(sets)")}
            if "build_page" not in existing_columns:
                logger.info("Migrating sets table: adding build_page column")
                conn.execute("ALTER TABLE sets ADD COLUMN build_page INTEGER DEFAULT 0")
            if "build_status" not in existing_columns:
                logger.info("Migrating sets table: adding build_status column")
                conn.execute("ALTER TABLE sets ADD COLUMN build_status TEXT DEFAULT 'not_started'")

            conn.execute('''
                CREATE TABLE IF NOT EXISTS brickset_settings (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    api_key TEXT,
                    username TEXT,
                    password TEXT
                )
            ''')

    # -- Brickset API settings --------------------------------------------

    def get_brickset_settings(self) -> Optional[dict[str, Any]]:
        with self.create_connection() as conn:
            row = conn.execute(
                "SELECT api_key, username, password FROM brickset_settings WHERE id = 1"
            ).fetchone()
        if not row:
            return None
        return {"api_key": row[0], "username": row[1], "password": row[2]}

    def save_brickset_settings(
        self, api_key: str, username: Optional[str] = None, password: Optional[str] = None
    ) -> None:
        with self.create_connection() as conn:
            conn.execute(
                '''
                INSERT INTO brickset_settings (id, api_key, username, password)
                VALUES (1, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    api_key=excluded.api_key, username=excluded.username, password=excluded.password
                ''',
                (api_key, username, password),
            )

    def insert_set_data(self, set_data: dict[str, Any]) -> None:
        logger.info("Inserting data for set ID: %s", set_data.get("setID"))
        # Strip 'sets/' prefix from local_images/local_instructions before storing,
        # since they are served relative to the 'sets' directory via custom_static
        local_imgs = [_strip_sets_prefix(img) for img in set_data.get("local_images", [])]
        local_instr = [_strip_sets_prefix(i) for i in set_data.get("local_instructions", [])]

        # Preserve any existing build progress across refreshes/re-adds, since
        # INSERT OR REPLACE otherwise wipes it back to the column defaults.
        existing = self.get_set_by_id(set_data.get("setID"))
        build_page = existing["build_page"] if existing else 0
        build_status = existing["build_status"] if existing else "not_started"

        with self.create_connection() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO sets (setID, setNumber, numberVariant, name, year, theme, pieces, launchDate, instructions, local_images, local_instructions, build_page, build_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                set_data.get("setID"),
                set_data.get("number"),
                set_data.get("numberVariant"),
                set_data.get("name"),
                set_data.get("year"),
                set_data.get("theme"),
                set_data.get("pieces"),
                set_data.get("launchDate"),
                json.dumps(set_data.get("instructions", [])),
                json.dumps(local_imgs),
                json.dumps(local_instr),
                build_page,
                build_status,
            ))

    def insert_combined_data(self, combined_data: dict[str, Any]) -> None:
        for set_data in combined_data.get("sets", []):
            self.insert_set_data(set_data)

    def update_build_progress(self, set_id: int, build_page: int, build_status: str) -> None:
        if build_status not in VALID_BUILD_STATUSES:
            raise ValueError(f"Invalid build_status: {build_status!r}")
        logger.info("Updating build progress for set ID %s: page=%s status=%s", set_id, build_page, build_status)
        with self.create_connection() as conn:
            conn.execute(
                "UPDATE sets SET build_page = ?, build_status = ? WHERE setID = ?",
                (build_page, build_status, set_id),
            )

    def delete_set(self, set_id: int) -> bool:
        """Delete a set's DB record. Returns True if a row was removed."""
        logger.info("Deleting set with setID: %s", set_id)
        with self.create_connection() as conn:
            cursor = conn.execute("DELETE FROM sets WHERE setID = ?", (set_id,))
        return cursor.rowcount > 0

    def get_next_manual_set_id(self) -> int:
        """Manually-added sets use negative IDs so they never collide with
        Brickset's real (always-positive) setIDs."""
        with self.create_connection() as conn:
            min_id = conn.execute("SELECT MIN(setID) FROM sets").fetchone()[0]
        if min_id is None or min_id > 0:
            return -1
        return min_id - 1

    def get_distinct_themes(self) -> list[str]:
        with self.create_connection() as conn:
            rows = conn.execute(
                "SELECT DISTINCT theme FROM sets WHERE theme IS NOT NULL AND theme != '' ORDER BY theme"
            ).fetchall()
        return [row[0] for row in rows]


    def get_set_by_id(self, set_id: int) -> Optional[dict[str, Any]]:
        logger.info("Fetching set with setID: %s", set_id)
        with self.create_connection() as conn:
            cursor = conn.execute(
                f"SELECT {', '.join(SET_COLUMNS)} FROM sets WHERE setID = ?", (set_id,)
            )
            row = cursor.fetchone()
        return row_to_dict(row) if row else None

    def search_sets(self, query: str, page: int = 1, per_page: int = 10) -> tuple[list[dict[str, Any]], int]:
        offset = (page - 1) * per_page
        like_query = f"%{query}%"
        with self.create_connection() as conn:
            cursor = conn.execute(
                f"SELECT {', '.join(SET_COLUMNS)} FROM sets "
                "WHERE name LIKE ? OR setNumber LIKE ? "
                "ORDER BY name LIMIT ? OFFSET ?",
                (like_query, like_query, per_page, offset),
            )
            rows = cursor.fetchall()
            total = conn.execute(
                "SELECT COUNT(*) FROM sets WHERE name LIKE ? OR setNumber LIKE ?",
                (like_query, like_query),
            ).fetchone()[0]
        return [row_to_dict(row) for row in rows], total

    def list_sets(
        self, page: int = 1, per_page: int = 10, theme: Optional[str] = None
    ) -> tuple[list[dict[str, Any]], int]:
        offset = (page - 1) * per_page
        where_clause = "WHERE theme = ?" if theme else ""
        params: tuple = (theme,) if theme else ()
        with self.create_connection() as conn:
            cursor = conn.execute(
                f"SELECT {', '.join(SET_COLUMNS)} FROM sets {where_clause} LIMIT ? OFFSET ?",
                (*params, per_page, offset),
            )
            rows = cursor.fetchall()
            total = conn.execute(
                f"SELECT COUNT(*) FROM sets {where_clause}", params
            ).fetchone()[0]
        return [row_to_dict(row) for row in rows], total
