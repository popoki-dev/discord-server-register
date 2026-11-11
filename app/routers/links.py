import time

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import discord
from app.database import get_db
from app.deps import current_user
from app.models import Link, User
from app.schemas import InviteCheckIn, LinkIn, LinkOut, ServerInfo

router = APIRouter(prefix="/api/links", tags=["links"])

DUPLICATE_MESSAGE = "This server has already been registered"
REMOVED_MESSAGE = "This server was removed by an administrator and cannot be submitted again"
NOT_CHECKED_MESSAGE = "Please press \"Check\" to verify the invite link before submitting"

# Invites this session has verified with "Check": {invite_code: unix_time}.
CHECKED_KEY = "checked_invites"
CHECK_TTL_SECONDS = 30 * 60
MAX_CHECKED = 10


def _remember_check(request: Request, code: str) -> None:
    now = int(time.time())
    checked = {c: t for c, t in request.session.get(CHECKED_KEY, {}).items() if now - t < CHECK_TTL_SECONDS}
    checked[code] = now
    # Keep the cookie small: only the most recent checks.
    request.session[CHECKED_KEY] = dict(sorted(checked.items(), key=lambda kv: kv[1])[-MAX_CHECKED:])


def _was_checked(request: Request, code: str) -> bool:
    checked_at = request.session.get(CHECKED_KEY, {}).get(code)
    return checked_at is not None and time.time() - checked_at < CHECK_TTL_SECONDS


def _forget_check(request: Request, code: str) -> None:
    checked = dict(request.session.get(CHECKED_KEY, {}))
    checked.pop(code, None)
    request.session[CHECKED_KEY] = checked


def _to_out(link: Link) -> LinkOut:
    return LinkOut.model_validate(link)


async def _lookup(invite: str) -> discord.GuildInfo:
    try:
        return await discord.fetch_guild_info(invite)
    except discord.InviteError as e:
        raise HTTPException(e.status_code, e.message)


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _existing(db: Session, guild_id: str) -> Link | None:
    """The link for this server, including ones an admin has deleted."""
    return db.scalar(select(Link).where(Link.guild_id == guild_id))


def _conflict_message(link: Link) -> str:
    return REMOVED_MESSAGE if link.removed else DUPLICATE_MESSAGE


@router.get("")
def list_links(
    q: str | None = Query(None, max_length=100),
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
) -> list[LinkOut]:
    query = select(Link).where(Link.removed.is_(False)).order_by(Link.register_time.desc())
    if q:
        pattern = f"%{_escape_like(q)}%"
        query = query.where(or_(Link.name.ilike(pattern), Link.description.ilike(pattern), Link.source.ilike(pattern)))
    return [_to_out(link) for link in db.scalars(query)]


@router.post("/check")
async def check_invite(
    body: InviteCheckIn, request: Request, db: Session = Depends(get_db), _: User = Depends(current_user)
) -> ServerInfo:
    info = await _lookup(body.invite)
    existing = _existing(db, info.guild_id)
    if existing is None:
        _remember_check(request, discord.parse_invite_code(body.invite))
    return ServerInfo(
        guild_id=info.guild_id,
        name=info.name,
        icon_url=info.icon_url,
        description=info.description,
        member_count=info.member_count,
        online_count=info.online_count,
        invite_url=info.invite_url,
        expires_at=info.expires_at,
        already_registered=existing is not None,
        removed=existing is not None and existing.removed,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_link(
    body: LinkIn, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)
) -> LinkOut:
    # The invite must have passed "Check" in this session first.
    try:
        code = discord.parse_invite_code(body.invite)
    except discord.InviteError as e:
        raise HTTPException(e.status_code, e.message)
    if not _was_checked(request, code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, NOT_CHECKED_MESSAGE)

    # Resolve again server-side: the guild_id comes from Discord, never from the client,
    # and the invite may have expired since it was checked.
    info = await _lookup(body.invite)
    if (existing := _existing(db, info.guild_id)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, _conflict_message(existing))

    # Store what Check showed, as fetched from Discord just now.
    link = Link(
        guild_id=info.guild_id,
        name=info.name,
        icon_url=info.icon_url,
        description=info.description,
        member_count=info.member_count,
        online_count=info.online_count,
        invite_url=info.invite_url,
        expires_at=info.expires_at,
        source=body.source,
        joined=False,
        register_account=user.id,
        removed=False,
    )
    db.add(link)
    try:
        db.commit()
    except IntegrityError:  # two users submitted the same server at the same moment
        db.rollback()
        existing = _existing(db, info.guild_id)
        raise HTTPException(status.HTTP_409_CONFLICT, _conflict_message(existing) if existing else DUPLICATE_MESSAGE)
    db.refresh(link)
    _forget_check(request, code)
    return _to_out(link)

