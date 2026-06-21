import os
from peewee import SqliteDatabase

db = SqliteDatabase(os.getenv("DATABASE_PATH", "agrosafe_edge.db"))


def init_db() -> None:
    db.connect(reuse_if_open=True)
    from iam.infrastructure.models import Device
    from soil.infrastructure.models import SoilReading
    from pir.infrastructure.models import PirEvent
    db.create_tables([Device, SoilReading, PirEvent], safe=True)
    _migrate()
    db.close()


def _migrate() -> None:
    """Add columns introduced after initial schema creation."""
    _add_column_if_missing("soil_readings", "is_valid", "INTEGER NOT NULL DEFAULT 1")
    _add_column_if_missing("soil_readings", "synced",   "INTEGER NOT NULL DEFAULT 0")
    _add_column_if_missing("soil_readings", "ambient_temperature", "REAL")
    _add_column_if_missing("soil_readings", "security_pir_status", "VARCHAR(32)")
    _add_column_if_missing("pir_events", "synced", "INTEGER NOT NULL DEFAULT 0")


def _add_column_if_missing(table: str, column: str, definition: str) -> None:
    try:
        db.execute_sql(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
    except Exception:
        pass  # column already exists