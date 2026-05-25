from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas.chat import ChatCreate, ChatOut, ChatUpdate
from app.schemas.message import MessageOut
from app.services.chat_service import ChatService
from app.services.message_service import MessageService

router = APIRouter(prefix="/api/chats", tags=["chats"])


@router.get("", response_model=list[ChatOut])
async def list_chats(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await ChatService(db).list_chats(user)


@router.post("", response_model=ChatOut, status_code=201)
async def create_chat(
    data: ChatCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ChatService(db).create_chat(user, data)


@router.get("/{chat_id}", response_model=ChatOut)
async def get_chat(
    chat_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ChatService(db).get_chat(user, chat_id)


@router.patch("/{chat_id}", response_model=ChatOut)
async def update_chat(
    chat_id: int,
    data: ChatUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ChatService(db).update_chat(user, chat_id, data)


@router.delete("/{chat_id}", status_code=204)
async def delete_chat(
    chat_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await ChatService(db).delete_chat(user, chat_id)


@router.get("/{chat_id}/messages", response_model=list[MessageOut])
async def list_messages(
    chat_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await MessageService(db).list_messages(user, chat_id)
