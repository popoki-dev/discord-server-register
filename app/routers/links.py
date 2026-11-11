from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import discord
from app.database import get_db
from app.deps import current_user
from app.models import Link, User
from app.schemas import CATEGORIES, InviteCheckIn, LinkIn, LinkOut, ServerInfo

router = APIRouter(prefix="/api/links", tags=["links"])

DUPLICATE_MESSAGE = "This server has already been registered"


def _to_out(link: Link) -> LinkOut:
    return LinkOut(
        id=link.id,
        guild_id=link.guild_id,
        guild_name=link.guild_name,
        icon_url=discord.icon_url(link.guild_id, link.guild_icon),
        member_count=link.member_count,
        invite_url=discord.invite_url(link.invite_code),
        category=link.category,
        description=link.description,
        source=link.source,
        created_at=link.created_at,
    )


async def _lookup(invite: str) -> discord.GuildInfo:
    try:
        return await discord.fetch_guild_info(invite)
    except discord.InviteError as e:
        raise HTTPException(e.status_code, e.message)


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _is_registered(db: Session, guild_id: str) -> bool:
    return db.scalar(select(Link.id).where(Link.guild_id == guild_id)) is not None


@router.get("/categories")
def categories(_: User = Depends(current_user)) -> list[str]:
    return CATEGORIES


@router.get("")
def list_links(
    category: str | None = None,
    q: str | None = Query(None, max_length=100),
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
) -> list[LinkOut]:
    query = select(Link).order_by(Link.created_at.desc())
    if category:
        query = query.where(Link.category == category)
    if q:
        pattern = f"%{_escape_like(q)}%"
        query = query.where(or_(Link.guild_name.ilike(pattern), Link.description.ilike(pattern)))
    return [_to_out(link) for link in db.scalars(query)]


@router.post("/check")
async def check_invite(
    body: InviteCheckIn, db: Session = Depends(get_db), _: User = Depends(current_user)
) -> ServerInfo:
    info = await _lookup(body.invite)
    return ServerInfo(
        guild_id=info.guild_id,
        name=info.name,
        icon_url=info.icon_url,
        description=info.description,
        member_count=info.member_count,
        online_count=info.online_count,
        invite_url=info.invite_url,
        expires_at=info.expires_at,
        already_registered=_is_registered(db, info.guild_id),
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_link(
    body: LinkIn, db: Session = Depends(get_db), user: User = Depends(current_user)
) -> LinkOut:
    # Always resolve server-side: the guild_id comes from Discord, never from the client.
    info = await _lookup(body.invite)
    if _is_registered(db, info.guild_id):
        raise HTTPException(status.HTTP_409_CONFLICT, DUPLICATE_MESSAGE)

    link = Link(
        guild_id=info.guild_id,
        invite_code=info.invite_code,
        category=body.category,
        description=body.description,
        source=body.source,
        guild_name=info.name,
        guild_icon=info.icon,
        member_count=info.member_count,
        submitted_by=user.id,
    )
    db.add(link)
    try:
        db.commit()
    except IntegrityError:  # two users submitted the same server at the same moment
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, DUPLICATE_MESSAGE)
    db.refresh(link)
    return _to_out(link)
