import json
import logging
from datetime import date
import os
import hashlib
from pathlib import Path

from aiogram import Router, F, Bot
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, MessageEntity, FSInputFile

from bot.keyboards import (
    kb_terms, kb_main_menu, kb_home, kb_confirm_rewrite, kb_confirm_main_menu_rewrite,
    kb_content_type, kb_choose_year, kb_my_message, kb_my_message_viewed, kb_confirm_delete, 
)
from bot.database import (
    get_or_create_user, get_user_message, save_user_message,
    update_delivery_year, delete_user_message,
)
from bot.models import ContentType
from bot.formatting import entities_to_html, _escape_html

router = Router()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# FSM
# ---------------------------------------------------------------------------

class RecordMessage(StatesGroup):
    choosing_type = State()
    waiting_content = State()
    choosing_year = State()


class ChangeYear(StatesGroup):
    choosing_year = State()


# ---------------------------------------------------------------------------
# Константы
# ---------------------------------------------------------------------------

CONTENT_TYPE_LABELS = {
    ContentType.voice: "🎤 Голосовое",
    ContentType.video_note: "🔘 Кружок",
    ContentType.video: "🎥 Видео",
    ContentType.text: "✍️ Текст",
}

CONTENT_PROMPT = {
    "voice": "🎤 Отправьте голосовое сообщение:",
    "video_note": "🔘 Запишите видеосообщение:",
    "video": "🎥 Отправьте видео:",
    "text": "✍️ Напишите текстовое послание:",
}

VIDEO_SIZE_LIMIT = 20 * 1024 * 1024

MEDIA_DIR = Path("/app/media")

MAIN_PHOTO_PATH = "assets/main_photo.png"
MAIN_PHOTO = FSInputFile(MAIN_PHOTO_PATH)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _download_file(bot: Bot, file_id: str, content_type: str) -> str | None:
    """Скачивает файл в /app/media, возвращает относительный путь или None при ошибке."""
    try:
        MEDIA_DIR.mkdir(parents=True, exist_ok=True)
        tg_file = await bot.get_file(file_id)

        ext_map = {"voice": "ogg", "video_note": "mp4", "video": "mp4"}
        ext = ext_map.get(content_type, "bin")

        # Имя файла — хэш file_id, чтобы не дублировать при перезаписи
        name = hashlib.md5(file_id.encode()).hexdigest()
        filename = f"{content_type}_{name}.{ext}"
        dest = MEDIA_DIR / filename

        await bot.download_file(tg_file.file_path, destination=dest)
        return str(dest)
    except Exception as e:
        logger.error(f"Ошибка скачивания файла {file_id}: {e}")
        return None
    
async def _show_main_menu(target: Message | CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    text = (
        "<b>🎓 Поздравляем с успешным завершением обучения!</b>\n\n"
        "​Сегодняшний день — это знаковый рубеж, момент перехода к новым профессиональным свершениям.\n\n"
        "Чтобы сохранить память об этом важном событии, мы предлагаем Вам оставить послание самому себе. Зафиксируйте свои <i>нынешние цели, мечты и стремления</i> — спустя время это сообщение станет ценным напоминанием о начале <b>Вашего пути</b>.\n\n"
        "Выберите действие из предложенных:"
    )
    if isinstance(target, CallbackQuery):
        await target.message.edit_caption(caption=text, reply_markup=kb_main_menu())
    else:
        await target.answer_photo(MAIN_PHOTO, caption=text, reply_markup=kb_main_menu())


async def _show_my_message_screen(bot_msg: Message, telegram_id: int, session, state: FSMContext) -> None:
    msg = await get_user_message(session, telegram_id)
    label = CONTENT_TYPE_LABELS.get(msg.content_type, msg.content_type.value)
    deliver_at = msg.delivery.deliver_at

    card_text = (
        f"✉️ <b>Ваше послание</b>\n\n"
        f"Тип: {label}\n"
        f"Дата доставки: <b>{deliver_at.strftime('%d.%m.%Y')}</b>"
    )

    # Удаляем предыдущий медиа-контент если был
    data = await state.get_data()
    prev_media_id = data.get("media_msg_id")
    if prev_media_id:
        try:
            await bot_msg.bot.delete_message(chat_id=bot_msg.chat.id, message_id=prev_media_id)
        except Exception:
            pass
        await state.update_data(media_msg_id=None)

    await bot_msg.edit_caption(caption=card_text, reply_markup=kb_my_message(), parse_mode="HTML")

async def _cleanup_media(state: FSMContext, bot: Bot, chat_id: int) -> None:
    data = await state.get_data()
    media_msg_id = data.get("media_msg_id")
    if media_msg_id:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=media_msg_id)
        except Exception:
            pass
        await state.update_data(media_msg_id=None)

def get_delivery_date(year_callback: str) -> date:
    years_map = {"year_1": 1, "year_2": 2, "year_3": 3}
    years = years_map[year_callback]
    
    today = date.today()
    return today.replace(year=today.year + years)

async def _wrong_content_type(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    await message.delete()
    await bot.edit_message_caption(
        chat_id=message.chat.id,
        message_id=data["bot_msg_id"],
        caption=f"❌ Неверный тип файла.\n\n{CONTENT_PROMPT.get(data.get('content_type', ''), 'Отправьте правильный тип файла:')}",
        reply_markup=kb_home(),
    )

# ---------------------------------------------------------------------------
# /start
# ---------------------------------------------------------------------------

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, session) -> None:
    await state.clear()
    try:
        await message.delete()
    except Exception:
        pass

    user = await get_or_create_user(
        session,
        telegram_id=message.from_user.id,
        full_name=message.from_user.full_name,
        username=message.from_user.username,
    )

    if user.accepted_terms:
        sent = await message.answer_photo(
            MAIN_PHOTO,
            caption=(
                "<b>🎓 Поздравляем с успешным завершением обучения!</b>\n\n"
                "​Сегодняшний день — это знаковый рубеж, момент перехода к новым профессиональным свершениям.\n\n"
                "Чтобы сохранить память об этом важном событии, мы предлагаем Вам оставить послание самому себе. Зафиксируйте свои <i>нынешние цели, мечты и стремления</i> — спустя время это сообщение станет ценным напоминанием о начале <b>Вашего пути</b>.\n\n"
                "Выберите действие из предложенных:"
            ),
            reply_markup=kb_main_menu(),
        )
    else:
        sent = await message.answer_photo(
            MAIN_PHOTO,
            caption=(
                "Здравствуйте!\n\nДаёте ли Вы согласие на обработку персональных данных в соответствии с 152-ФЗ?"
            ),
            reply_markup=kb_terms(),
        )
    await state.update_data(bot_msg_id=sent.message_id)


# ---------------------------------------------------------------------------
# Экран 1 — согласие
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "terms_accept")
async def cb_terms_accept(callback: CallbackQuery, state: FSMContext, session) -> None:
    await callback.answer()
    user = await get_or_create_user(
        session,
        telegram_id=callback.from_user.id,
        full_name=callback.from_user.full_name,
        username=callback.from_user.username,
    )
    user.accepted_terms = True
    await session.commit()
    await _show_main_menu(callback, state)


@router.callback_query(F.data == "terms_decline")
async def cb_terms_decline(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await callback.message.edit_caption(
        caption="❌ Без согласия использование бота невозможно.\n\nНапишите /start, если передумаете.",
        reply_markup=None,
    )


# ---------------------------------------------------------------------------
# Навигация — главное меню
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "menu_home")
async def cb_menu_home(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await _cleanup_media(state, callback.bot, callback.message.chat.id)
    await _show_main_menu(callback, state)


@router.callback_query(F.data == "menu_record")
async def cb_menu_record(callback: CallbackQuery, state: FSMContext, session) -> None:
    await callback.answer()
    existing = await get_user_message(session, callback.from_user.id)
    if existing:
        await callback.message.edit_caption(
            caption="⚠️ У Вас уже есть послание. Перезаписать его?",
            reply_markup=kb_confirm_main_menu_rewrite(),
        )
    else:
        await state.set_state(RecordMessage.choosing_type)
        await callback.message.edit_caption(caption="Выберите тип послания:", reply_markup=kb_content_type())


@router.callback_query(F.data == "menu_my_message")
async def cb_menu_my_message(callback: CallbackQuery, state: FSMContext, session) -> None:
    await callback.answer()
    existing = await get_user_message(session, callback.from_user.id)
    if not existing:
        await callback.message.edit_caption(caption="📭 У Вас пока нет послания.", reply_markup=kb_home())
    else:
        await _show_my_message_screen(callback.message, callback.from_user.id, session, state)


# ---------------------------------------------------------------------------
# Экран 3 — подтверждение перезаписи
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "confirm_rewrite")
async def cb_confirm_rewrite(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(RecordMessage.choosing_type)
    await callback.message.edit_caption(caption="Выберите тип послания:", reply_markup=kb_content_type())
    await _cleanup_media(state, callback.bot, callback.message.chat.id)


# ---------------------------------------------------------------------------
# Экран 4 — выбор типа контента
# ---------------------------------------------------------------------------

@router.callback_query(F.data.in_({"type_voice", "type_video_note", "type_video", "type_text"}))
async def cb_choose_type(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    type_map = {
        "type_voice": "voice",
        "type_video_note": "video_note",
        "type_video": "video",
        "type_text": "text",
    }
    content_type = type_map[callback.data]
    await state.update_data(
        content_type=content_type,
        bot_msg_id=callback.message.message_id,
    )
    await state.set_state(RecordMessage.waiting_content)
    await callback.message.edit_caption(caption=CONTENT_PROMPT[content_type], reply_markup=kb_home())


# ---------------------------------------------------------------------------
# Экран 5 — ожидание контента
# ---------------------------------------------------------------------------

async def _proceed_to_year(message: Message, state: FSMContext, bot: Bot) -> None:
    try:
        await message.delete()
    except Exception:
        pass
    data = await state.get_data()
    await state.set_state(RecordMessage.choosing_year)
    await bot.edit_message_caption(
        chat_id=message.chat.id,
        message_id=data["bot_msg_id"],
        caption="📅 Через сколько лет Вы хотите получить послание?",
        reply_markup=kb_choose_year(),
    )


@router.message(RecordMessage.waiting_content, F.voice)
async def msg_got_voice(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    if data.get("content_type") != "voice":
        await _wrong_content_type(message, state, bot)
        return
    local_path = await _download_file(bot, message.voice.file_id, "voice")
    await state.update_data(
        file_id=message.voice.file_id, 
        file_size=message.voice.file_size,
        local_path=local_path
    )
    await _proceed_to_year(message, state, bot)


@router.message(RecordMessage.waiting_content, F.video_note)
async def msg_got_video_note(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    if data.get("content_type") != "video_note":
        await _wrong_content_type(message, state, bot)
        return
    if message.video_note.file_size and message.video_note.file_size > VIDEO_SIZE_LIMIT:
        await message.delete()
        await bot.edit_message_caption(
            chat_id=message.chat.id,
            message_id=data["bot_msg_id"],
            caption=f"⚠️ Файл слишком большой (максимум 20 МБ).\n\n{CONTENT_PROMPT['video_note']}",
            reply_markup=kb_home(),
        )
        return
    local_path = await _download_file(bot, message.video_note.file_id, "video_note")
    await state.update_data(
        file_id=message.video_note.file_id,
        file_size=message.video_note.file_size,
        local_path=local_path,
    )
    await _proceed_to_year(message, state, bot)


@router.message(RecordMessage.waiting_content, F.video)
async def msg_got_video(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    if data.get("content_type") != "video":
        await _wrong_content_type(message, state, bot)
        return
    if message.video.file_size and message.video.file_size > VIDEO_SIZE_LIMIT:
        await message.delete()
        await bot.edit_message_caption(
            chat_id=message.chat.id,
            message_id=data["bot_msg_id"],
            caption=f"⚠️ Файл слишком большой (максимум 20 МБ).\n\n{CONTENT_PROMPT['video']}",
            reply_markup=kb_home(),
        )
        return
    local_path = await _download_file(bot, message.video.file_id, "video")
    await state.update_data(
        file_id=message.video.file_id,
        file_size=message.video.file_size,
        local_path=local_path,
    )
    await _proceed_to_year(message, state, bot)


@router.message(RecordMessage.waiting_content, F.text)
async def msg_got_text(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    if data.get("content_type") != "text":
        await _wrong_content_type(message, state, bot)
        return
    entities_json = None
    if message.entities:
        entities_json = json.dumps([e.model_dump() for e in message.entities], ensure_ascii=False)
    await state.update_data(text_content=message.text, entities_json=entities_json)
    await _proceed_to_year(message, state, bot)


@router.message(RecordMessage.waiting_content)
async def msg_wrong_type(message: Message, state: FSMContext, bot: Bot) -> None:
    await _wrong_content_type(message, state, bot)


# ---------------------------------------------------------------------------
# Экран 6 — выбор года (первая запись)
# ---------------------------------------------------------------------------

@router.callback_query(RecordMessage.choosing_year, F.data.in_({"year_1", "year_2", "year_3"}))
async def cb_year_record(callback: CallbackQuery, state: FSMContext, session) -> None:
    await callback.answer()
    deliver_at = get_delivery_date(callback.data)
    data = await state.get_data()
    ct_str = data["content_type"]

    await save_user_message(
        session=session,
        telegram_id=callback.from_user.id,
        content_type=ContentType(ct_str),
        deliver_at=deliver_at,
        telegram_file_id=data.get("file_id"),
        file_size=data.get("file_size"),
        local_path=data.get("local_path"),
        text=data.get("text_content"),
        entities=data.get("entities_json"),
    )
    await state.clear()

    label = CONTENT_TYPE_LABELS.get(ContentType(ct_str), ct_str)
    await callback.message.edit_caption(
        caption=(
            f"✅ Послание сохранено!\n\n"
            f"Тип: {label}\n"
            f"Дата доставки: <b>{deliver_at.strftime('%d.%m.%Y')}</b>\n\n"
            f"Мы пришлём его Вам в этот день 🎉"
        ),
        reply_markup=kb_home(),
        parse_mode="HTML",
    )


# ---------------------------------------------------------------------------
# Экран 6 — выбор года (изменение)
# ---------------------------------------------------------------------------

@router.callback_query(ChangeYear.choosing_year, F.data.in_({"year_1", "year_2", "year_3"}))
async def cb_year_change(callback: CallbackQuery, state: FSMContext, session) -> None:
    await callback.answer()
    deliver_at = get_delivery_date(callback.data)
    await update_delivery_year(session, callback.from_user.id, deliver_at)
    await state.clear()
    await callback.message.edit_caption(
        caption=f"✅ Год доставки изменён на <b>{deliver_at.year}</b>.",
        reply_markup=kb_home(),
        parse_mode="HTML",
    )


# ---------------------------------------------------------------------------
# Экран 7 — кнопки карточки
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "msg_view")
async def cb_msg_view(callback: CallbackQuery, state: FSMContext, session) -> None:
    await callback.answer()
    msg = await get_user_message(session, callback.from_user.id)

    if msg.content_type == ContentType.voice:
        sent = await callback.message.answer_voice(msg.telegram_file_id)
    elif msg.content_type == ContentType.video_note:
        sent = await callback.message.answer_video_note(msg.telegram_file_id)
    elif msg.content_type == ContentType.video:
        sent = await callback.message.answer_video(msg.telegram_file_id)
    elif msg.content_type == ContentType.text:
        if msg.entities:
            raw = json.loads(msg.entities)
            html_text = entities_to_html(msg.text, raw)
        else:
            html_text = _escape_html(msg.text)
        sent = await callback.message.answer(html_text, parse_mode="HTML")

    await state.update_data(media_msg_id=sent.message_id)
    # Меняем клавиатуру карточки — убираем кнопку "Посмотреть"
    await callback.message.edit_reply_markup(reply_markup=kb_my_message_viewed())

    
@router.callback_query(F.data == "msg_rewrite")
async def cb_msg_rewrite(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await callback.message.edit_caption(
        caption="⚠️ У Вас уже есть послание. Перезаписать его?",
        reply_markup=kb_confirm_rewrite(),
    )
    await _cleanup_media(state, callback.bot, callback.message.chat.id) 

@router.callback_query(F.data == "msg_change_year")
async def cb_msg_change_year(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(ChangeYear.choosing_year)
    await callback.message.edit_caption(
        caption="📅 Через сколько лет Вы хотите получить послание?",
        reply_markup=kb_choose_year(),
    )
    await _cleanup_media(state, callback.bot, callback.message.chat.id)


@router.callback_query(F.data == "msg_delete")
async def cb_msg_delete(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await callback.message.edit_caption(
        caption="⚠️ Вы уверены? Послание будет удалено безвозвратно.",
        reply_markup=kb_confirm_delete(),
    )
    await _cleanup_media(state, callback.bot, callback.message.chat.id)


@router.callback_query(F.data == "msg_my_message_back")
async def cb_msg_my_message_back(callback: CallbackQuery, state: FSMContext, session) -> None:
    await callback.answer()
    existing = await get_user_message(session, callback.from_user.id)
    if existing:
        await _show_my_message_screen(callback.message, callback.from_user.id, session, state)
    else:
        await _cleanup_media(state, callback.bot, callback.message.chat.id)
        await _show_main_menu(callback, state)


# ---------------------------------------------------------------------------
# Экран 8 — подтверждение удаления
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "confirm_delete")
async def cb_confirm_delete_exec(callback: CallbackQuery, state: FSMContext, session) -> None:
    await callback.answer()
    await delete_user_message(session, callback.from_user.id)
    await state.clear()
    await _cleanup_media(state, callback.bot, callback.message.chat.id)
    await callback.message.edit_caption(caption="🗑 Послание удалено.", reply_markup=kb_home())