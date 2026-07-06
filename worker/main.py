import asyncio
import logging
from datetime import datetime, date
from zoneinfo import ZoneInfo

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from bot.config import settings
from bot.database import async_session_maker
from bot.models import Delivery, Message
from worker.sender import send_delivery

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

MSK = ZoneInfo("Europe/Moscow")
SEND_HOUR = 3
SEND_MINUTE = 18
CHECK_INTERVAL = 60


async def process_due_messages() -> None:
    bot = Bot(token=settings.bot_token)
    today = datetime.now(MSK).date()

    async with async_session_maker() as session:
        result = await session.execute(
            select(Delivery)
            .where(
                Delivery.sent == False,
                Delivery.failed == False,
                Delivery.deliver_at <= today,
            )
            .options(selectinload(Delivery.message).selectinload(Message.user))
        )
        deliveries = list(result.scalars().all())

        if not deliveries:
            logger.info("Нет сообщений для отправки")
            await bot.session.close()
            return

        logger.info("Найдено %s сообщений для отправки", len(deliveries))

        for delivery in deliveries:
            try:
                await send_delivery(bot, delivery)
                delivery.sent = True
                delivery.sent_at = datetime.now(MSK)
                logger.info("Отправлено delivery_id=%s", delivery.id)
            except Exception as e:
                delivery.failed = True
                delivery.fail_reason = str(e)[:500]
                logger.exception("Ошибка отправки delivery_id=%s: %s", delivery.id, e)

        await session.commit()
    await bot.session.close()


async def main() -> None:
    logger.info(
        "Worker запущен. Проверка каждые %s сек, рассылка в %02d:%02d МСК",
        CHECK_INTERVAL, SEND_HOUR, SEND_MINUTE,
    )
    last_run_date: date | None = None

    while True:
        now = datetime.now(MSK)

        if now.hour == SEND_HOUR and now.minute >= SEND_MINUTE and last_run_date != now.date():
            try:
                await process_due_messages()
                last_run_date = now.date()
            except Exception:
                logger.exception("Worker cycle failed")

        await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())