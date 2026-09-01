# Dev: Testing

```bash
pytest -q
```

The suite covers the SQLite data-access layer (`sql_ops.py`, `auth_ops.py`),
routes (blueprints), and authentication smoke tests (local login, setup
flow, OIDC wiring). Run it before opening a PR/pushing, and after any change
touching routes, templates, or the data layer.
