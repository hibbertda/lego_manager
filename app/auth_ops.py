from __future__ import annotations

import logging
import sqlite3
from typing import Any, Optional

from werkzeug.security import check_password_hash, generate_password_hash

logger = logging.getLogger(__name__)

VALID_ROLES = ("admin", "user")
VALID_AUTH_PROVIDERS = ("local", "oidc")


class OidcUsernameConflictError(RuntimeError):
    """Raised when the username derived from OIDC claims (preferred_username,
    email, or subject) collides with an existing account that isn't linked to
    this OIDC subject. The users table has a single global UNIQUE constraint
    on username shared by both local and OIDC accounts, so this is a genuine,
    user-recoverable configuration conflict rather than a server bug — the
    caller should show it to the user/admin rather than let it crash the
    request."""


USER_COLUMNS = (
    "id",
    "username",
    "email",
    "password_hash",
    "role",
    "auth_provider",
    "oidc_subject",
    "is_active",
    "created_at",
)

PROVIDER_COLUMNS = (
    "id",
    "name",
    "issuer",
    "client_id",
    "client_secret",
    "scopes",
    "enabled",
    "default_role",
    "disable_local_login",
)


def _user_row_to_dict(row: tuple) -> dict[str, Any]:
    data = dict(zip(USER_COLUMNS, row))
    data["is_active"] = bool(data["is_active"])
    data.pop("password_hash", None)  # never leak the hash to callers that don't need it
    return data


def _provider_row_to_dict(row: tuple) -> dict[str, Any]:
    data = dict(zip(PROVIDER_COLUMNS, row))
    data["enabled"] = bool(data["enabled"])
    data["disable_local_login"] = bool(data["disable_local_login"])
    return data


class AuthOps:
    """Manages local user accounts, roles, and OIDC provider configuration.

    Shares the same SQLite file as DatabaseOps for operational simplicity in
    this single-file-database app.
    """

    def __init__(self, db_name: str):
        self.db_name = db_name
        self.create_tables()

    def create_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_name, timeout=30)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 30000")
        return conn

    def create_tables(self) -> None:
        logger.info("Creating auth tables if they do not exist")
        with self.create_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT,
                    password_hash TEXT,
                    role TEXT NOT NULL DEFAULT 'user',
                    auth_provider TEXT NOT NULL DEFAULT 'local',
                    oidc_subject TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS oidc_providers (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    name TEXT NOT NULL DEFAULT 'OIDC Provider',
                    issuer TEXT,
                    client_id TEXT,
                    client_secret TEXT,
                    scopes TEXT NOT NULL DEFAULT 'openid profile email',
                    enabled INTEGER NOT NULL DEFAULT 0,
                    default_role TEXT NOT NULL DEFAULT 'user',
                    disable_local_login INTEGER NOT NULL DEFAULT 0
                )
            """)

            existing_columns = {
                row[1] for row in conn.execute("PRAGMA table_info(oidc_providers)")
            }
            if "disable_local_login" not in existing_columns:
                conn.execute(
                    "ALTER TABLE oidc_providers ADD COLUMN disable_local_login INTEGER NOT NULL DEFAULT 0"
                )

    # -- Users -----------------------------------------------------------

    def has_any_users(self) -> bool:
        with self.create_connection() as conn:
            return conn.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None

    def create_local_user(
        self,
        username: str,
        password: str,
        role: str = "user",
        email: Optional[str] = None,
    ) -> int:
        if role not in VALID_ROLES:
            raise ValueError(f"Invalid role: {role!r}")
        password_hash = generate_password_hash(password)
        with self.create_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO users (username, email, password_hash, role, auth_provider) "
                "VALUES (?, ?, ?, ?, 'local')",
                (username, email, password_hash, role),
            )
            if cursor.lastrowid is None:
                raise RuntimeError("Failed to create user")
            return cursor.lastrowid

    def get_or_create_oidc_user(
        self, oidc_subject: str, username: str, email: Optional[str], default_role: str
    ) -> dict[str, Any]:
        """Find an existing OIDC-linked user by subject, or create one."""
        with self.create_connection() as conn:
            row = conn.execute(
                f"SELECT {', '.join(USER_COLUMNS)} FROM users WHERE oidc_subject = ? AND auth_provider = 'oidc'",
                (oidc_subject,),
            ).fetchone()
            if row:
                return _user_row_to_dict(row)

            try:
                cursor = conn.execute(
                    "INSERT INTO users (username, email, role, auth_provider, oidc_subject) "
                    "VALUES (?, ?, ?, 'oidc', ?)",
                    (username, email, default_role, oidc_subject),
                )
            except sqlite3.IntegrityError as exc:
                raise OidcUsernameConflictError(
                    f"Single sign-on could not create an account: the username "
                    f"'{username}' from your identity provider is already taken "
                    "by another account. Ask an admin to rename or remove the "
                    "existing account, or configure the identity provider to "
                    "send a different username claim, then try again."
                ) from exc
            user_id = cursor.lastrowid
        if user_id is None:
            raise RuntimeError("Failed to create OIDC user")
        user = self.get_user_by_id(user_id)
        if user is None:
            raise RuntimeError("Created OIDC user could not be loaded")
        return user

    def get_user_by_id(self, user_id: int) -> Optional[dict[str, Any]]:
        with self.create_connection() as conn:
            row = conn.execute(
                f"SELECT {', '.join(USER_COLUMNS)} FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        return _user_row_to_dict(row) if row else None

    def get_user_by_username(self, username: str) -> Optional[dict[str, Any]]:
        with self.create_connection() as conn:
            row = conn.execute(
                f"SELECT {', '.join(USER_COLUMNS)} FROM users WHERE username = ?",
                (username,),
            ).fetchone()
        return _user_row_to_dict(row) if row else None

    def verify_local_login(
        self, username: str, password: str
    ) -> Optional[dict[str, Any]]:
        """Return the user dict if username/password match an active local account."""
        with self.create_connection() as conn:
            row = conn.execute(
                f"SELECT {', '.join(USER_COLUMNS)}, password_hash FROM users "
                "WHERE username = ? AND auth_provider = 'local'",
                (username,),
            ).fetchone()
        if not row:
            return None
        *user_row, password_hash = row
        if not password_hash or not check_password_hash(password_hash, password):
            return None
        user = _user_row_to_dict(tuple(user_row))
        if not user["is_active"]:
            return None
        return user

    def list_users(self) -> list[dict[str, Any]]:
        with self.create_connection() as conn:
            rows = conn.execute(
                f"SELECT {', '.join(USER_COLUMNS)} FROM users ORDER BY created_at"
            ).fetchall()
        return [_user_row_to_dict(row) for row in rows]

    def count_active_admins(self) -> int:
        with self.create_connection() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM users WHERE role = 'admin' AND is_active = 1"
            ).fetchone()[0]

    def update_user_role(self, user_id: int, role: str) -> None:
        if role not in VALID_ROLES:
            raise ValueError(f"Invalid role: {role!r}")
        with self.create_connection() as conn:
            conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))

    def set_user_active(self, user_id: int, is_active: bool) -> None:
        with self.create_connection() as conn:
            conn.execute(
                "UPDATE users SET is_active = ? WHERE id = ?", (int(is_active), user_id)
            )

    def delete_user(self, user_id: int) -> bool:
        with self.create_connection() as conn:
            cursor = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        return cursor.rowcount > 0

    # -- OIDC provider configuration --------------------------------------

    def get_oidc_provider(self) -> Optional[dict[str, Any]]:
        with self.create_connection() as conn:
            row = conn.execute(
                f"SELECT {', '.join(PROVIDER_COLUMNS)} FROM oidc_providers WHERE id = 1"
            ).fetchone()
        return _provider_row_to_dict(row) if row else None

    def save_oidc_provider(
        self,
        name: str,
        issuer: str,
        client_id: str,
        client_secret: str,
        scopes: str = "openid profile email",
        enabled: bool = False,
        default_role: str = "user",
        disable_local_login: bool = False,
    ) -> None:
        if default_role not in VALID_ROLES:
            raise ValueError(f"Invalid default_role: {default_role!r}")
        with self.create_connection() as conn:
            conn.execute(
                """
                INSERT INTO oidc_providers
                    (id, name, issuer, client_id, client_secret, scopes, enabled, default_role, disable_local_login)
                VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name, issuer=excluded.issuer, client_id=excluded.client_id,
                    client_secret=excluded.client_secret, scopes=excluded.scopes,
                    enabled=excluded.enabled, default_role=excluded.default_role,
                    disable_local_login=excluded.disable_local_login
                """,
                (
                    name,
                    issuer,
                    client_id,
                    client_secret,
                    scopes,
                    int(enabled),
                    default_role,
                    int(disable_local_login),
                ),
            )
