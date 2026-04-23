from datetime import date, timedelta

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.config import Settings
from app.database.db import Database
from app.keyboards.calendar import month_calendar_kb, slots_kb, confirm_booking_kb
from app.keyboards.common import back_to_menu_kb, subscription_kb
from app.services.scheduler import ReminderService
from app.services.subscription import is_subscribed
from app.states.booking import BookingStates
from app.utils.dates import format_date

router = Router()


# ----------------------------
# utils
# ----------------------------

def month_range() -> tuple[str, str]:
    today = date.today()
    end = today + timedelta(days=31)
    return today.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


async def show_calendar(callback: CallbackQuery, db: Database, offset: int = 0):
    start, end = month_range()

    days = db.get_month_work_days(start, end)
    if not days:
        await callback.message.edit_text(
            "📅 Пока нет доступных дат.",
            reply_markup=back_to_menu_kb(),
        )
        return

    await callback.message.edit_text(
        "📅 Выберите дату:",
        reply_markup=month_calendar_kb(set(days), month_offset=offset),
    )


# ----------------------------
# start booking
# ----------------------------

@router.callback_query(StateFilter(None), F.data == "booking:start")
async def start_booking(
    callback: CallbackQuery,
    db: Database,
    bot: Bot,
    settings: Settings,
):
    if db.has_active_booking(callback.from_user.id):
        b = db.get_active_booking(callback.from_user.id)
        await callback.message.edit_text(
            f"⚠️ У вас уже есть запись:\n"
            f"Дата: <b>{format_date(b['date'])}</b>\n"
            f"Время: <b>{b['time']}</b>",
            parse_mode="HTML",
            reply_markup=back_to_menu_kb(),
        )
        await callback.answer()
        return

    if not await is_subscribed(bot, settings.channel_id, callback.from_user.id):
        await callback.message.edit_text(
            "❗ Нужно подписаться на канал",
            reply_markup=subscription_kb(settings.channel_link),
        )
        await callback.answer()
        return

    await show_calendar(callback, db)
    await callback.answer()


# ----------------------------
# calendar navigation
# ----------------------------

@router.callback_query(StateFilter(None), F.data.startswith("cal:"))
async def calendar_nav(callback: CallbackQuery, db: Database):
    offset = int(callback.data.split(":")[1])
    await show_calendar(callback, db, offset)
    await callback.answer()


@router.callback_query(StateFilter(None), F.data.startswith("date:"))
async def pick_date(callback: CallbackQuery, db: Database, state: FSMContext):
    date_str = callback.data.split(":")[1]

    slots = db.get_free_slots(date_str)
    if not slots:
        await callback.answer("Нет свободных слотов", show_alert=True)
        return

    await state.update_data(date=date_str)

    await callback.message.edit_text(
        f"📅 {format_date(date_str)}\nВыберите время:",
        reply_markup=slots_kb(date_str, slots),
    )
    await callback.answer()


# ----------------------------
# pick time
# ----------------------------

@router.callback_query(StateFilter(None), F.data.startswith("time:"))
async def pick_time(callback: CallbackQuery, state: FSMContext):
    try:
        _, payload = callback.data.split(":")
        date_str, time_str = payload.split("|")
    except ValueError:
        await callback.answer("Ошибка данных", show_alert=True)
        return

    await state.update_data(date=date_str, time=time_str)
    await state.set_state(BookingStates.name)

    await callback.message.edit_text("Введите имя:")
    await callback.answer()


# ----------------------------
# name
# ----------------------------

@router.message(BookingStates.name)
async def get_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(BookingStates.phone)
    await message.answer("Введите телефон:")


# ----------------------------
# phone + confirm
# ----------------------------

@router.message(BookingStates.phone)
async def get_phone(message: Message, state: FSMContext):
    data = await state.get_data()

    await state.update_data(phone=message.text.strip())

    await message.answer(
        "📌 Проверьте:\n"
        f"Дата: <b>{format_date(data['date'])}</b>\n"
        f"Время: <b>{data['time']}</b>\n"
        f"Имя: <b>{data['name']}</b>\n"
        f"Телефон: <b>{message.text}</b>",
        parse_mode="HTML",
        reply_markup=confirm_booking_kb(),
    )


# ----------------------------
# confirm booking
# ----------------------------

@router.callback_query(F.data == "booking:confirm")
async def confirm(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
    settings: Settings,
    reminder_service: ReminderService,
):
    data = await state.get_data()

    if not data:
        await callback.answer("Сессия устарела", show_alert=True)
        return

    booking_id = db.create_booking(
        user_id=callback.from_user.id,
        name=data["name"],
        phone=data["phone"],
        date=data["date"],
        time=data["time"],
    )

    if not booking_id:
        await callback.message.edit_text(
            "❌ Слот уже занят",
            reply_markup=back_to_menu_kb(),
        )
        await state.clear()
        return

    job_id = reminder_service.schedule_booking_reminder(
        booking_id,
        callback.from_user.id,
        data["date"],
        data["time"],
    )

    db.set_reminder_job_id(booking_id, job_id)

    await state.clear()

    await callback.message.edit_text(
        f"✅ Запись создана:\n"
        f"{format_date(data['date'])} {data['time']}",
        reply_markup=back_to_menu_kb(),
    )

    await callback.answer()