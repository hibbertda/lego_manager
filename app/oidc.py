from authlib.integrations.flask_client import OAuth


class OIDCManager:
    """Wraps an Authlib OAuth registry so the single OIDC client can be
    (re)configured at runtime from the oidc_providers DB row, instead of
    being fixed at process startup via env vars.
    """

    def __init__(self, app=None):
        self.oauth = OAuth()
        self._registered = False
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        self.oauth.init_app(app)
        self.app = app
        self.reload()

    def reload(self) -> None:
        """Re-read the oidc_providers config and (re)register the client."""
        provider = self.app.auth_ops.get_oidc_provider()
        # Authlib does not support re-registering the same name; drop and recreate.
        if "oidc" in self.oauth._clients:
            del self.oauth._clients["oidc"]
        if provider and provider["issuer"] and provider["client_id"]:
            self.oauth.register(
                name="oidc",
                client_id=provider["client_id"],
                client_secret=provider["client_secret"],
                server_metadata_url=provider["issuer"].rstrip("/") + "/.well-known/openid-configuration",
                client_kwargs={"scope": provider["scopes"] or "openid profile email"},
            )
            self._registered = True
        else:
            self._registered = False

    @property
    def oidc(self):
        if not self._registered:
            raise RuntimeError("OIDC provider is not configured.")
        return self.oauth.oidc
