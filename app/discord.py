"""Look up Discord invite links via Discord's public invite endpoint (no bot token needed)."""

import re
from dataclasses import dataclass
from datetime import datetime

import httpx

API_BASE = "https://discord.com/api/v10"
CDN_BASE = "https://cdn.discordapp.com"

# discord.gg/CODE, discord.com/invite/CODE, discordapp.com/invite/CODE, or a bare CODE.
_INVITE_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?"
    r"(?:discord\.gg/|(?:discord|discordapp)\.com/invite/)?"
    r"(?P<code>[A-Za-z0-9-]{2,64})/?(?:\?.*)?$"
)


class InviteError(Exception):
    """Raised with a user-facing message when an invite cannot be used."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass
class GuildInfo:
    invite_code: str
    guild_id: str
    name: str
    icon: str | None
    description: str | None
    member_count: int | None
    online_count: int | None
    expires_at: datetime | None

    @property
    def invite_url(self) -> str:
        return invite_url(self.invite_code)

    @property
    def icon_url(self) -> str | None:
        return icon_url(self.guild_id, self.icon)


def invite_url(code: str) -> str:
    return f"https://discord.gg/{code}"


def icon_url(guild_id: str, icon: str | None) -> str | None:
    if not icon:
        return None
    ext = "gif" if icon.startswith("a_") else "png"
    return f"{CDN_BASE}/icons/{guild_id}/{icon}.{ext}?size=128"


def parse_invite_code(value: str) -> str:
    match = _INVITE_RE.match(value.strip())
    if not match:
        raise InviteError("That doesn't look like a Discord invite link (e.g. https://discord.gg/abc123)")
    return match.group("code")


async def fetch_guild_info(invite: str) -> GuildInfo:
    code = parse_invite_code(invite)
    try:
        async with httpx.AsyncClient(timeout=10, headers={"User-Agent": "DiscordServerRegister/1.0"}) as client:
            resp = await client.get(
                f"{API_BASE}/invites/{code}", params={"with_counts": "true", "with_expiration": "true"}
            )
    except httpx.HTTPError:
        raise InviteError("Could not reach Discord. Please try again.", 502)

    if resp.status_code == 404:
        raise InviteError("This invite is invalid or has expired", 404)
    if resp.status_code == 429:
        raise InviteError("Discord is rate limiting requests. Please wait a moment and try again.", 429)
    if resp.status_code != 200:
        raise InviteError("Discord returned an unexpected error. Please try again.", 502)

    data = resp.json()
    guild = data.get("guild")
    if not guild:
        raise InviteError("This invite is not for a server (e.g. it is a group DM invite)")

    expires_at = data.get("expires_at")
    return GuildInfo(
        invite_code=data.get("code", code),
        guild_id=str(guild["id"]),
        name=guild.get("name", ""),
        icon=guild.get("icon"),
        description=guild.get("description"),
        member_count=data.get("approximate_member_count"),
        online_count=data.get("approximate_presence_count"),
        expires_at=datetime.fromisoformat(expires_at) if expires_at else None,
    )
