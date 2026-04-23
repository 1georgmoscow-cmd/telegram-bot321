import asyncio
import logging
import sys


from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import load_settings
from app.database.db import Database
from app.handlers import admin, booking, misc, start, subscription
from app.services.scheduler import ReminderService
from app.core.bot_factory import create_bot  # 👈 СЮДА



async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    settings = load_settings()

    db = Database(settings.database_path)
    db.init()
    db.generate_work_days()

    bot = create_bot(settings.bot_token)  # 👈 теперь нормально

    dp = Dispatcher()

    scheduler = AsyncIOScheduler(timezone=settings.timezone)
    scheduler.start()

    reminder_service = ReminderService(
        scheduler=scheduler,
        db=db,
        bot=bot,
    )
    reminder_service.restore_jobs_from_db()

    dp.include_router(start.router)
    dp.include_router(subscription.router)
    dp.include_router(booking.router)
    dp.include_router(misc.router)
    dp.include_router(admin.router)

    await dp.start_polling(
        bot,
        settings=settings,
        db=db,
        reminder_service=reminder_service,
    )


if __name__ == "__main__":
    asyncio.run(main())