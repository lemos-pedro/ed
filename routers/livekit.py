from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models import User, Sala
from auth import get_current_user
from livekit.api import AccessToken, VideoGrants
from dotenv import load_dotenv
import os

load_dotenv()

router = APIRouter(prefix="/livekit", tags=["LiveKit"])

LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")
LIVEKIT_URL = os.getenv("LIVEKIT_URL")


@router.get("/token")
async def gerar_token(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if not user.sala_id:
        raise HTTPException(status_code=400, detail="Utilizador sem sala atribuída")

    # nome da room = id da sala
    room_name = f"sala-{user.sala_id}"

    token = AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET) \
        .with_identity(str(user.id)) \
        .with_name(user.nome) \
        .with_grants(VideoGrants(
            room_join=True,
            room=room_name,
            can_publish=True,
            can_subscribe=True
        )).to_jwt()

    return {
        "token": token,
        "room": room_name,
        "url": LIVEKIT_URL,
        "user": user.nome
    }