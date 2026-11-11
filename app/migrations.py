"""Minimal, idempotent schema upgrades for databases created by older versions.

``Base.metadata.create_all`` creates missing tables but never alters existing ones,
so columns added after the first release are added here. Each statement is safe to
run on every startup.
"""

from sqlalchemy import text
from sqlalchemy.engine import Engine

UPGRADES = [
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name VARCHAR(100) NOT NULL DEFAULT ''",
    "ALTER TABLE links ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE",
    "CREATE INDEX IF NOT EXISTS ix_links_submitted_by ON links (submitted_by)",
    "CREATE INDEX IF NOT EXISTS ix_links_created_at ON links (created_at)",
]


def upgrade(engine: Engine) -> None:
    with engine.begin() as conn:
        for statement in UPGRADES:
            conn.execute(text(statement))
