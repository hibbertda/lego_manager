from flask_login import UserMixin


class User(UserMixin):
    """Flask-Login user wrapper around the dict returned by AuthOps.

    AuthOps deliberately strips password_hash before returning user dicts,
    so this object never carries credential material.
    """

    def __init__(self, data: dict):
        self._data = data

    def get_id(self) -> str:
        return str(self._data["id"])

    @property
    def id(self) -> int:
        return self._data["id"]

    @property
    def username(self) -> str:
        return self._data["username"]

    @property
    def email(self):
        return self._data.get("email")

    @property
    def role(self) -> str:
        return self._data["role"]

    @property
    def is_admin(self) -> bool:
        return self._data["role"] == "admin"

    @property
    def auth_provider(self) -> str:
        return self._data["auth_provider"]

    @property
    def is_active(self) -> bool:  # noqa: A003 - overrides UserMixin default
        return bool(self._data.get("is_active", True))
