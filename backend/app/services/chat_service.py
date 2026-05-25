from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chat, User
from app.schemas.chat import ChatCreate, ChatUpdate


class ChatService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_chats(self, user: User) -> list[Chat]:
        result = await self.db.scalars(
            select(Chat).where(Chat.user_id == user.id).order_by(Chat.updated_at.desc())
        )
        return list(result)

    async def get_chat(self, user: User, chat_id: int) -> Chat:
        chat = await self.db.get(Chat, chat_id)
        if not chat or chat.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
        return chat

    async def create_chat(self, user: User, data: ChatCreate) -> Chat:
        chat = Chat(user_id=user.id, title=data.title)
        self.db.add(chat)
        await self.db.commit()
        await self.db.refresh(chat)
        return chat

    async def update_chat(self, user: User, chat_id: int, data: ChatUpdate) -> Chat:
        chat = await self.get_chat(user, chat_id)
        chat.title = data.title
        chat.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(chat)
        return chat

    async def delete_chat(self, user: User, chat_id: int) -> None:
        chat = await self.get_chat(user, chat_id)
        await self.db.delete(chat)
        await self.db.commit()
