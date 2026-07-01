from datetime import date
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import selectinload

from bot.config import settings
from bot.models import User, Message, Delivery, ContentType

engine = create_async_engine(settings.database_url, echo=False)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncSession:
    async with async_session_maker() as session:
        yield session


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

async def get_or_create_user(session: AsyncSession, telegram_id: int, full_name: str, username: str | None = None) -> User:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if not user:
        user = User(telegram_id=telegram_id, full_name=full_name, username=username)
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

async def get_user_message(session: AsyncSession, telegram_id: int) -> Message | None:
    """Возвращает актуальное послание пользователя вместе с Delivery."""
    result = await session.execute(
        select(Message)
        .join(User, Message.user_id == User.id)
        .where(User.telegram_id == telegram_id)
        .options(selectinload(Message.delivery))
        .order_by(Message.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def save_user_message(
    session: AsyncSession,
    telegram_id: int,
    content_type: ContentType,
    deliver_at: date,
    telegram_file_id: str | None = None,
    file_size: int | None = None,
    text: str | None = None,
    entities: str | None = None,
) -> Message:
    """Удаляет старое послание (если есть) и сохраняет новое."""
    # Удаляем старое
    user = await get_or_create_user(session, telegram_id, "")
    old = await get_user_message(session, telegram_id)
    if old:
        if old.delivery:
            await session.delete(old.delivery)
        await session.delete(old)
        await session.flush()

    msg = Message(
        user_id=user.id,
        content_type=content_type,
        telegram_file_id=telegram_file_id,
        file_size=file_size,
        text=text,
        entities=entities,
    )
    session.add(msg)
    await session.flush()  # получаем msg.id

    delivery = Delivery(message_id=msg.id, deliver_at=deliver_at)
    session.add(delivery)
    await session.commit()
    await session.refresh(msg)
    return msg


async def update_delivery_year(session: AsyncSession, telegram_id: int, deliver_at: date) -> None:
    msg = await get_user_message(session, telegram_id)
    if msg and msg.delivery:
        msg.delivery.deliver_at = deliver_at
        await session.commit()


async def delete_user_message(session: AsyncSession, telegram_id: int) -> None:
    msg = await get_user_message(session, telegram_id)
    if msg:
        if msg.delivery:
            await session.delete(msg.delivery)
        await session.delete(msg)
        await session.commit()