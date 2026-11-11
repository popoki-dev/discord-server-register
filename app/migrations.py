"""Minimal, idempotent schema upgrades for databases created by older versions.

``Base.metadata.create_all`` creates missing tables but never alters existing ones,
so schema changes after the first release are applied here on every startup.
"""

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection, Engine

USERS_UPGRADES = [
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name VARCHAR(100) NOT NULL DEFAULT ''",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS session_version INTEGER NOT NULL DEFAULT 0",
]

# Converts the original links table (guild_name, guild_icon, invite_code, category, a
# submitter-written description, created_at, submitted_by, deleted_at) to the current one.
LEGACY_LINKS_UPGRADE = [
    "ALTER TABLE links ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE",
    "ALTER TABLE links RENAME COLUMN guild_name TO name",
    "ALTER TABLE links ADD COLUMN icon_url VARCHAR(255)",
    """UPDATE links SET icon_url = 'https://cdn.discordapp.com/icons/' || guild_id || '/' || guild_icon
         || CASE WHEN guild_icon LIKE 'a\\_%' THEN '.gif' ELSE '.png' END || '?size=128'
       WHERE guild_icon IS NOT NULL""",
    "ALTER TABLE links DROP COLUMN guild_icon",
    "ALTER TABLE links ADD COLUMN invite_url VARCHAR(255)",
    "UPDATE links SET invite_url = 'https://discord.gg/' || invite_code",
    "ALTER TABLE links ALTER COLUMN invite_url SET NOT NULL",
    "ALTER TABLE links DROP COLUMN invite_code",
    "ALTER TABLE links DROP COLUMN category",
    # The old description was written by the submitter; the column now holds Discord's.
    "ALTER TABLE links ALTER COLUMN description DROP NOT NULL",
    "UPDATE links SET description = NULL",
    "ALTER TABLE links ADD COLUMN IF NOT EXISTS online_count INTEGER",
    "ALTER TABLE links ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP WITH TIME ZONE",
    "ALTER TABLE links RENAME COLUMN created_at TO register_time",
    "ALTER TABLE links RENAME COLUMN submitted_by TO register_account",
    "ALTER TABLE links ADD COLUMN removed BOOLEAN NOT NULL DEFAULT false",
    "UPDATE links SET removed = deleted_at IS NOT NULL",
    "ALTER TABLE links DROP COLUMN deleted_at",
    "DROP INDEX IF EXISTS ix_links_created_at",
    "DROP INDEX IF EXISTS ix_links_submitted_by",
    "CREATE INDEX IF NOT EXISTS ix_links_register_time ON links (register_time)",
    "CREATE INDEX IF NOT EXISTS ix_links_register_account ON links (register_account)",
    "CREATE INDEX IF NOT EXISTS ix_links_removed ON links (removed)",
]


# Brings any earlier development version of the links table to the current columns.
# Each statement is a no-op when the table is already up to date.
LINKS_UPGRADES = [
    "ALTER TABLE links ADD COLUMN IF NOT EXISTS joined BOOLEAN NOT NULL DEFAULT false",
    "ALTER TABLE links DROP COLUMN IF EXISTS already_registered",
    "ALTER TABLE links DROP COLUMN IF EXISTS admin_verified",
]

# An interim version kept Discord's description in a separate guild_description column.
GUILD_DESCRIPTION_UPGRADE = [
    "UPDATE links SET description = guild_description WHERE description IS NULL OR description = ''",
    "ALTER TABLE links DROP COLUMN guild_description",
]


def _run(conn: Connection, statements: list[str]) -> None:
    for statement in statements:
        conn.execute(text(statement))


def upgrade(engine: Engine) -> None:
    link_columns = {c["name"] for c in inspect(engine).get_columns("links")}
    with engine.begin() as conn:
        _run(conn, USERS_UPGRADES)
        if "guild_name" in link_columns:
            _run(conn, LEGACY_LINKS_UPGRADE)
        _run(conn, LINKS_UPGRADES)
        if "guild_description" in link_columns:
            _run(conn, GUILD_DESCRIPTION_UPGRADE)
