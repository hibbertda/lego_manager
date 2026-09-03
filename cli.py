"""CLI for importing LEGO sets into the local collection without the web UI.

Usage:
    python cli.py add-set 75386
"""

from __future__ import annotations

import logging

import click
from dotenv import load_dotenv

# Load .env before Config evaluates its os.getenv() defaults at import time.
load_dotenv()

from app.brickset_ops import BricksetAPI
from app.config import Config
from app.sql_ops import DatabaseOps


@click.group()
def cli():
    """LEGO Manager command-line tools."""
    logging.basicConfig(level=logging.INFO)


@cli.command("add-set")
@click.argument("set_number")
def add_set(set_number: str):
    """Fetch SET_NUMBER from Brickset/LEGO.com and store it in the local database."""
    config = Config()
    brickset_api = BricksetAPI(config.BRICKSET_API_KEY)
    db_ops = DatabaseOps(config.DATABASE_PATH)

    combined_data = brickset_api.get_combined_data(
        set_number, base_dir=config.SETS_DIR, max_bytes=config.MAX_DOWNLOAD_BYTES
    )
    if not combined_data:
        raise click.ClickException(
            f"Failed to retrieve data for set number: {set_number}"
        )

    db_ops.insert_combined_data(combined_data)
    click.echo(f"Set {set_number} added successfully.")


if __name__ == "__main__":
    cli()
