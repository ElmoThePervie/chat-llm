from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chat, Message, User
from app.services.chat_service import ChatService


class MessageService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.chat_service = ChatService(db)

    async def list_messages(self, user: User, chat_id: int) -> list[Message]:
        await self.chat_service.get_chat(user, chat_id)
        result = await self.db.scalars(
            select(Message).where(Message.chat_id == chat_id).order_by(Message.created_at)
        )
        return list(result)

    async def add_user_message(self, user: User, chat: Chat, content: str) -> Message:
        msg = Message(chat_id=chat.id, role="user", content=content)
        self.db.add(msg)
        chat.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(msg)
        return msg

    async def add_assistant_message(self, chat: Chat, content: str) -> Message:
        msg = Message(chat_id=chat.id, role="assistant", content=content)
        self.db.add(msg)
        chat.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(msg)
        return msg
