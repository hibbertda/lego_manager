#!/bin/sh
# Entrypoint: fix ownership of bind-mounted paths, then drop from root to the
# unprivileged `appuser` before running the real command.
#
# Why this is needed:
# 1. The image runs as non-root `appuser`, but docker-compose bind-mounts
#    are created/owned by whatever UID exists on the host (often root,
#    since dockerd creates missing bind-mount targets as root). That leaves
#    `appuser` unable to write to them. Fixing ownership as root once per
#    container start (before dropping to appuser) avoids requiring the
#    operator to manually chown/chmod paths on the host.
# 2. Bind-mounting a *file* path that doesn't exist yet on the host is a
#    classic Docker footgun: Docker silently creates a *directory* there
#    instead, which then makes sqlite3.connect() fail with "unable to open
#    database file". docker-compose.yml avoids this by mounting a `data/`
#    *directory* (always created correctly, file or not) and pointing
#    DATABASE_PATH inside it, rather than bind-mounting the .db file itself.
set -e

DB_PATH="${DATABASE_PATH:-lego_sets.db}"
SETS_DIR="${SETS_DIR:-sets}"

# Make paths absolute relative to the app's working directory if needed.
case "$DB_PATH" in /*) : ;; *) DB_PATH="/app/$DB_PATH" ;; esac
case "$SETS_DIR" in /*) : ;; *) SETS_DIR="/app/$SETS_DIR" ;; esac

DATA_DIR="$(dirname "$DB_PATH")"
mkdir -p "$SETS_DIR" "$DATA_DIR"
touch "$DB_PATH" 2>/dev/null || true
# Skip recursively chowning /app itself (already owned by appuser from the
# build) when DATABASE_PATH isn't pointed at a separate mounted directory.
if [ "$DATA_DIR" != "/app" ]; then
    chown -R appuser:appuser "$DATA_DIR" 2>/dev/null || true
fi
chown -R appuser:appuser "$DB_PATH" "$SETS_DIR" 2>/dev/null || true

exec gosu appuser "$@"
