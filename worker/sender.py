import json
import logging

from aiogram import Bot

from bot.models import Delivery, ContentType
from bot.formatting import entities_to_html, _escape_html

logger = logging.getLogger(__name__)

INTRO_TEXT_TEMPLATE = (
    "🎓 Привет из прошлого!\n\n"
    "Это послание, которое ты записал сам себе {date} на выпускном. "
    "Вот оно 👇"
)


async def send_delivery(bot: Bot, delivery: Delivery) -> None:
    message = delivery.message
    user = message.user
    chat_id = user.telegram_id

    intro = INTRO_TEXT_TEMPLATE.format(date=message.created_at.strftime("%d.%m.%Y"))
    await bot.send_message(chat_id, intro)

    if message.content_type == ContentType.voice:
        await bot.send_voice(chat_id, message.telegram_file_id)
    elif message.content_type == ContentType.video_note:
        await bot.send_video_note(chat_id, message.telegram_file_id)
    elif message.content_type == ContentType.video:
        await bot.send_video(chat_id, message.telegram_file_id)
    elif message.content_type == ContentType.text:
        if message.entities:
            html_text = entities_to_html(message.text, json.loads(message.entities))
        else:
            html_text = _escape_html(message.text or "")
        await bot.send_message(chat_id, html_text, parse_mode="HTML")