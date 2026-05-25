import json

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal, get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas.message import MessageCreate, MessageOut
from app.services.chat_service import ChatService
from app.services.llm_service import LLMService
from app.services.message_service import MessageService

router = APIRouter(prefix="/api/chats", tags=["messages"])
llm_service = LLMService()


@router.post("/{chat_id}/messages", response_model=MessageOut)
async def send_message(
    chat_id: int,
    data: MessageCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    chat_service = ChatService(db)
    message_service = MessageService(db)
    chat = await chat_service.get_chat(user, chat_id)

    await message_service.add_user_message(user, chat, data.content)
    prompt = llm_service.build_prompt(data.content)
    try:
        answer = llm_service.generate(prompt)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    assistant_msg = await message_service.add_assistant_message(chat, answer)
    return assistant_msg


@router.post("/{chat_id}/messages/stream")
async def send_message_stream(
    chat_id: int,
    data: MessageCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    chat_service = ChatService(db)
    message_service = MessageService(db)
    chat = await chat_service.get_chat(user, chat_id)

    await message_service.add_user_message(user, chat, data.content)
    prompt = llm_service.build_prompt(data.content)
    chat_id_for_save = chat.id
    user_id = user.id

    async def event_stream():
        full = []
        try:
            for chunk in llm_service.generate_stream(prompt):
                full.append(chunk)
                yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"
        except RuntimeError as exc:
            yield f"data: {json.dumps({'type': 'error', 'content': str(exc)})}\n\n"
            return

        content = "".join(full)
        async with AsyncSessionLocal() as save_db:
            try:
                save_user = await save_db.get(User, user_id)
                if not save_user:
                    yield f"data: {json.dumps({'type': 'error', 'content': 'User not found'})}\n\n"
                    return
                save_chat = await ChatService(save_db).get_chat(save_user, chat_id_for_save)
                msg = await MessageService(save_db).add_assistant_message(save_chat, content)
                payload = MessageOut.model_validate(msg).model_dump(mode="json")
                yield f"data: {json.dumps({'type': 'done', 'message': payload})}\n\n"
            except Exception as exc:
                yield f"data: {json.dumps({'type': 'error', 'content': str(exc)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
