from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def kb_terms() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да", callback_data="terms_accept")
    builder.button(text="❌ Нет", callback_data="terms_decline")
    builder.adjust(2)
    return builder.as_markup()


def kb_main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Записать послание", callback_data="menu_record")
    builder.button(text="📋 Моё послание", callback_data="menu_my_message")
    builder.adjust(1)
    return builder.as_markup()


def kb_home() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ На главную", callback_data="menu_home")
    return builder.as_markup()


def kb_confirm_rewrite() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, перезаписать", callback_data="confirm_rewrite")
    builder.button(text="❌ Отмена", callback_data="menu_my_message")
    builder.adjust(1)
    return builder.as_markup()

def kb_confirm_main_menu_rewrite() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, перезаписать", callback_data="confirm_rewrite")
    builder.button(text="❌ Отмена", callback_data="menu_home")
    builder.adjust(1)
    return builder.as_markup()


def kb_content_type() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🎤 Голосовое", callback_data="type_voice")
    builder.button(text="⭕ Кружок", callback_data="type_video_note")
    builder.button(text="🎥 Видео", callback_data="type_video")
    builder.button(text="✍️ Текст", callback_data="type_text")
    builder.button(text="⬅️ Назад", callback_data="menu_home")
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def kb_choose_year() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Через 1 год", callback_data="year_2027")
    builder.button(text="Через 2 года", callback_data="year_2028")
    builder.button(text="Через 3 года", callback_data="year_2029")
    builder.adjust(3)
    return builder.as_markup()


def kb_my_message() -> InlineKeyboardMarkup:
    """Карточка послания — без контента (первый показ)."""
    builder = InlineKeyboardBuilder()
    builder.button(text="👁 Посмотреть послание", callback_data="msg_view")
    builder.button(text="✏️ Перезаписать", callback_data="msg_rewrite")
    builder.button(text="📅 Изменить год", callback_data="msg_change_year")
    builder.button(text="🗑 Удалить", callback_data="msg_delete")
    builder.button(text="⬅️ Назад", callback_data="menu_home")
    builder.adjust(1, 2, 1, 1)
    return builder.as_markup()


def kb_my_message_viewed() -> InlineKeyboardMarkup:
    """Карточка послания — после просмотра контента."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Перезаписать", callback_data="msg_rewrite")
    builder.button(text="📅 Изменить год", callback_data="msg_change_year")
    builder.button(text="🗑 Удалить", callback_data="msg_delete")
    builder.button(text="⬅️ Назад", callback_data="menu_home")
    builder.adjust(2, 1, 1)
    return builder.as_markup()


def kb_confirm_delete() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, удалить", callback_data="confirm_delete")
    builder.button(text="❌ Отмена", callback_data="msg_my_message_back")
    builder.adjust(1)
    return builder.as_markup()