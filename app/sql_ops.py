from __future__ import annotations

import json
import logging
import sqlite3
from typing import Any, Optional

logger = logging.getLogger(__name__)

SET_COLUMNS = (
    "setID",
    "setNumber",
    "name",
    "year",
    "theme",
    "pieces",
    "launchDate",
    "instructions",
    "local_images",
    "local_instructions",
    "build_page",
    "build_status",
    "favorite",
)

VALID_BUILD_STATUSES = ("not_started", "in_progress", "complete", "storage")

# Whitelisted ORDER BY clauses for the sets list "Sort by" control — keyed by
# the query-string value so untrusted input never reaches raw SQL string
# building. Each includes setID as a final tiebreaker for stable pagination.
SORT_OPTIONS = {
    "name": "name COLLATE NOCASE ASC, setID ASC",
    "year": "year DESC, name COLLATE NOCASE ASC, setID ASC",
    "theme": "theme COLLATE NOCASE ASC, name COLLATE NOCASE ASC, setID ASC",
}
DEFAULT_SORT = "name"

# Human-readable labels for the "Sort by" dropdown, in display order.
SORT_LABELS = {
    "name": "Name (A-Z)",
    "year": "Year released (newest first)",
    "theme": "Theme (A-Z)",
}

# Single source of truth for how each build_status renders in the UI (badge
# color/icon on set list/grid cards, dropdown labels, and the sidebar status
# filter) — templates pull this via the status_labels/status_icons/
# status_badge_classes context globals (see app/__init__.py) instead of each
# defining their own copy.
BUILD_STATUS_META = {
    "not_started": {
        "label": "Not Started",
        "icon": "bi-square",
        "badge_class": "bg-secondary-subtle text-secondary-emphasis",
    },
    "in_progress": {
        "label": "In Progress",
        "icon": "bi-tools",
        "badge_class": "bg-warning text-dark",
    },
    "complete": {
        "label": "Complete",
        "icon": "bi-check-circle-fill",
        "badge_class": "bg-success-subtle text-success-emphasis",
    },
    "storage": {
        "label": "Storage",
        "icon": "bi-archive-fill",
        "badge_class": "bg-info-subtle text-info-emphasis",
    },
}


def _strip_sets_prefix(path: str) -> str:
    """Paths are served relative to the 'sets' directory via custom_static,
    so strip any leading 'sets/' left over from how the path was built."""
    return path[len("sets/") :] if path.startswith("sets/") else path


def row_to_dict(row: tuple) -> dict[str, Any]:
    """Map a `SET_COLUMNS`-ordered row into a JSON-decoded, path-normalized dict."""
    data = dict(zip(SET_COLUMNS, row))
    data["instructions"] = (
        json.loads(data["instructions"]) if data["instructions"] else []
    )
    data["local_images"] = [
        _strip_sets_prefix(p)
        for p in (json.loads(data["local_images"]) if data["local_images"] else [])
    ]
    data["local_instructions"] = [
        _strip_sets_prefix(p)
        for p in (
            json.loads(data["local_instructions"]) if data["local_instructions"] else []
        )
    ]
    data["build_page"] = data.get("build_page") or 0
    data["build_status"] = data.get("build_status") or "not_started"
    data["favorite"] = bool(data.get("favorite") or 0)
    return data


class DatabaseOps:
    def __init__(self, db_name: str):
        self.db_name = db_name
        self.create_tables()

    def create_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_name, timeout=30)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 30000")
        return conn

    def create_tables(self) -> None:
        logger.info("Creating tables if they do not exist")
        with self.create_connection() as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations "
                "(version INTEGER PRIMARY KEY, applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
            )
            conn.execute("""
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
            """)
            existing_columns = {
                row[1] for row in conn.execute("PRAGMA table_info(sets)")
            }
            for column, ddl in (
                (
                    "build_page",
                    "ALTER TABLE sets ADD COLUMN build_page INTEGER DEFAULT 0",
                ),
                (
                    "build_status",
                    "ALTER TABLE sets ADD COLUMN build_status TEXT DEFAULT 'not_started'",
                ),
                ("favorite", "ALTER TABLE sets ADD COLUMN favorite INTEGER DEFAULT 0"),
            ):
                if column in existing_columns:
                    continue
                logger.info("Migrating sets table: adding %s column", column)
                try:
                    conn.execute(ddl)
                except sqlite3.OperationalError as exc:
                    # Multiple gunicorn workers boot concurrently and each call
                    # create_tables() independently on first startup against a
                    # fresh DB. This PRAGMA-check-then-ALTER isn't atomic across
                    # processes, so another worker can win the race and add the
                    # column first — that's fine, just ignore it here.
                    if "duplicate column name" not in str(exc):
                        raise

            conn.execute("""
                CREATE TABLE IF NOT EXISTS brickset_settings (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    api_key TEXT,
                    username TEXT,
                    password TEXT
                )
            """)
            conn.execute(
                "CREATE TABLE IF NOT EXISTS manual_set_ids "
                "(id INTEGER PRIMARY KEY AUTOINCREMENT)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_sets_filters "
                "ON sets (theme, build_status, favorite, name, setID)"
            )
            conn.execute("INSERT OR IGNORE INTO schema_migrations (version) VALUES (1)")

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
        self,
        api_key: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> None:
        with self.create_connection() as conn:
            conn.execute(
                """
                INSERT INTO brickset_settings (id, api_key, username, password)
                VALUES (1, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    api_key=excluded.api_key, username=excluded.username, password=excluded.password
                """,
                (api_key, username, password),
            )

    def insert_set_data(self, set_data: dict[str, Any]) -> None:
        logger.info("Inserting data for set ID: %s", set_data.get("setID"))
        # Strip 'sets/' prefix from local_images/local_instructions before storing,
        # since they are served relative to the 'sets' directory via custom_static
        local_imgs = [
            _strip_sets_prefix(img) for img in set_data.get("local_images", [])
        ]
        local_instr = [
            _strip_sets_prefix(i) for i in set_data.get("local_instructions", [])
        ]

        # Preserve any existing build progress across refreshes/re-adds, since
        # INSERT OR REPLACE otherwise wipes it back to the column defaults.
        set_id = set_data.get("setID")
        if not isinstance(set_id, int):
            raise ValueError("setID must be an integer")
        existing = self.get_set_by_id(set_id)
        build_page = existing["build_page"] if existing else 0
        build_status = existing["build_status"] if existing else "not_started"
        favorite = int(existing["favorite"]) if existing else 0

        with self.create_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO sets (setID, setNumber, numberVariant, name, year, theme, pieces, launchDate, instructions, local_images, local_instructions, build_page, build_status, favorite)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    set_id,
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
                    favorite,
                ),
            )

    def insert_combined_data(self, combined_data: dict[str, Any]) -> None:
        for set_data in combined_data.get("sets", []):
            self.insert_set_data(set_data)

    def update_build_progress(
        self, set_id: int, build_page: int, build_status: str
    ) -> None:
        if build_status not in VALID_BUILD_STATUSES:
            raise ValueError(f"Invalid build_status: {build_status!r}")
        logger.info(
            "Updating build progress for set ID %s: page=%s status=%s",
            set_id,
            build_page,
            build_status,
        )
        with self.create_connection() as conn:
            conn.execute(
                "UPDATE sets SET build_page = ?, build_status = ? WHERE setID = ?",
                (build_page, build_status, set_id),
            )

    def update_build_page(self, set_id: int, build_page: int) -> None:
        """Update only the current page (e.g. from the PDF viewer's page-tracking),
        leaving build_status untouched unless it's still 'not_started', in which case
        bump it to 'in_progress' since the user has clearly started reading."""
        logger.info("Updating build page for set ID %s: page=%s", set_id, build_page)
        with self.create_connection() as conn:
            conn.execute(
                "UPDATE sets SET build_page = ?, "
                "build_status = CASE WHEN build_status = 'not_started' THEN 'in_progress' ELSE build_status END "
                "WHERE setID = ?",
                (build_page, set_id),
            )

    def update_build_status_only(self, set_id: int, build_status: str) -> None:
        """Update just build_status (e.g. the quick-change dropdown on set list/grid
        cards), leaving build_page untouched — unlike update_build_progress, which
        is used by the full "Save progress" form on the set detail page."""
        if build_status not in VALID_BUILD_STATUSES:
            raise ValueError(f"Invalid build_status: {build_status!r}")
        logger.info(
            "Updating build status for set ID %s: status=%s", set_id, build_status
        )
        with self.create_connection() as conn:
            conn.execute(
                "UPDATE sets SET build_status = ? WHERE setID = ?",
                (build_status, set_id),
            )

    def toggle_favorite(self, set_id: int) -> bool:
        """Flip the favorite flag for a set and return the new value."""
        with self.create_connection() as conn:
            cursor = conn.execute(
                "UPDATE sets SET favorite = 1 - favorite WHERE setID = ? RETURNING favorite",
                (set_id,),
            )
            row = cursor.fetchone()
        if row is None:
            raise ValueError(f"Set does not exist: {set_id}")
        new_value = row[0]
        logger.info(
            "Toggled favorite for set ID %s: favorite=%s", set_id, bool(new_value)
        )
        return bool(new_value)

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
            cursor = conn.execute("INSERT INTO manual_set_ids DEFAULT VALUES")
            if cursor.lastrowid is None:
                raise RuntimeError("Failed to allocate a manual set ID")
            return -cursor.lastrowid

    def update_set_metadata(
        self,
        set_id: int,
        name: str,
        year: Optional[int],
        theme: Optional[str],
        pieces: Optional[int],
    ) -> bool:
        """Manually edit a set's descriptive metadata (e.g. to fill in gaps
        Brickset doesn't have, or to correct a manually-added set). Returns
        False if the set doesn't exist."""
        logger.info("Updating metadata for set ID %s", set_id)
        with self.create_connection() as conn:
            cursor = conn.execute(
                "UPDATE sets SET name = ?, year = ?, theme = ?, pieces = ? WHERE setID = ?",
                (name, year, theme, pieces, set_id),
            )
        return cursor.rowcount > 0

    def append_local_instructions(self, set_id: int, rel_paths: list[str]) -> bool:
        """Add manually-uploaded instruction PDFs to a set's existing list
        (e.g. because Brickset didn't have them at add-time). Returns False
        if the set doesn't exist."""
        existing = self.get_set_by_id(set_id)
        if not existing:
            return False
        # get_set_by_id already strips the 'sets/' prefix, so this stays
        # consistent with insert_set_data's storage format.
        combined = existing["local_instructions"] + [
            p for p in rel_paths if p not in existing["local_instructions"]
        ]
        logger.info(
            "Appending %d instruction file(s) to set ID %s", len(rel_paths), set_id
        )
        with self.create_connection() as conn:
            conn.execute(
                "UPDATE sets SET local_instructions = ? WHERE setID = ?",
                (json.dumps(combined), set_id),
            )
        return True

    def find_sets_missing_metadata(self) -> list[dict[str, Any]]:
        """Scan for sets with gaps a maintenance admin might want to fix:
        missing year/theme/pieces, no cover image, or no instructions.
        Returns each set's data plus a 'missing_fields' list of human-readable
        labels for what's absent."""
        with self.create_connection() as conn:
            rows = conn.execute(
                f"SELECT {', '.join(SET_COLUMNS)} FROM sets "
                "WHERE year IS NULL OR theme IS NULL OR theme = '' "
                "OR pieces IS NULL "
                "OR local_images IS NULL OR local_images = '[]' "
                "OR local_instructions IS NULL OR local_instructions = '[]' "
                "ORDER BY name COLLATE NOCASE ASC"
            ).fetchall()

        results = []
        for row in rows:
            data = row_to_dict(row)
            missing = []
            if not data.get("year"):
                missing.append("year")
            if not data.get("theme"):
                missing.append("theme")
            if not data.get("pieces"):
                missing.append("pieces")
            if not data.get("local_images"):
                missing.append("cover image")
            if not data.get("local_instructions"):
                missing.append("instructions")
            data["missing_fields"] = missing
            results.append(data)
        return results

    def get_all_sets(self) -> list[dict[str, Any]]:
        """All sets, unpaginated — used by the Utility Labels page (and the
        admin missing-metadata task's label check) which need to see the
        whole collection at once rather than one page at a time."""
        with self.create_connection() as conn:
            rows = conn.execute(
                f"SELECT {', '.join(SET_COLUMNS)} FROM sets "
                "ORDER BY name COLLATE NOCASE ASC"
            ).fetchall()
        return [row_to_dict(row) for row in rows]

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

    def search_sets(
        self, query: str, page: int = 1, per_page: int = 10
    ) -> tuple[list[dict[str, Any]], int]:
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
        self,
        page: int = 1,
        per_page: int = 10,
        theme: Optional[str] = None,
        build_status: Optional[str] = None,
        favorite_only: bool = False,
        sort: Optional[str] = None,
    ) -> tuple[list[dict[str, Any]], int]:
        offset = (page - 1) * per_page
        conditions = []
        params: list = []
        if theme:
            conditions.append("theme = ?")
            params.append(theme)
        if build_status:
            conditions.append("build_status = ?")
            params.append(build_status)
        if favorite_only:
            conditions.append("favorite = 1")
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        order_by = SORT_OPTIONS.get(sort or DEFAULT_SORT, SORT_OPTIONS[DEFAULT_SORT])
        with self.create_connection() as conn:
            cursor = conn.execute(
                f"SELECT {', '.join(SET_COLUMNS)} FROM sets {where_clause} "
                f"ORDER BY {order_by} LIMIT ? OFFSET ?",
                (*params, per_page, offset),
            )
            rows = cursor.fetchall()
            total = conn.execute(
                f"SELECT COUNT(*) FROM sets {where_clause}", params
            ).fetchone()[0]
        return [row_to_dict(row) for row in rows], total
