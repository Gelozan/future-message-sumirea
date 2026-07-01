from datetime import date
from typing import Callable, Awaitable, Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from bot.config import settings
from bot.database import async_session_maker


class DbSessionMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        async with async_session_maker() as session:
            data["session"] = session
            return await handler(event, data)


ALLOWED_CONTENT_TYPES = {"text", "voice", "video_note", "video"}


class ContentGuardMiddleware(BaseMiddleware):
    """Отклоняет любые типы контента кроме text/voice/video_note/video."""

    async def __call__(self, handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        if isinstance(event, Message):
            fsm_context = data.get("state")
            if fsm_context:
                current_state = await fsm_context.get_state()
                if current_state == "RecordMessage:waiting_content":
                    return await handler(event, data)

            if event.content_type not in ALLOWED_CONTENT_TYPES:
                try:
                    await event.delete()
                except Exception:
                    pass
                return
        return await handler(event, data)


def is_collection_open() -> bool:
    today = date.today()
    return settings.collection_start <= today <= settings.collection_end


class CollectionWindowMiddleware(BaseMiddleware):
    """
    Блокирует запись новых посланий вне окна COLLECTION_START..COLLECTION_END.
    Просмотр/удаление/смену года уже существующего послания не трогает.
    """

    BLOCKED_CALLBACKS = {
        "menu_record", "confirm_rewrite", "msg_rewrite",
        "type_voice", "type_video_note", "type_video", "type_text",
    }

    async def __call__(self, handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        state = data.get("state")
        blocked = False

        if isinstance(event, CallbackQuery) and event.data in self.BLOCKED_CALLBACKS:
            blocked = True
        elif isinstance(event, Message) and state:
            current = await state.get_state()
            if current and current.startswith("RecordMessage:"):
                blocked = True

        if blocked and not is_collection_open():
            text = "⏳ Приём сообщений завершён."
            if isinstance(event, CallbackQuery):
                await event.answer(text, show_alert=True)
            else:
                try:
                    await event.delete()
                except Exception:
                    pass
            return

        return await handler(event, data)