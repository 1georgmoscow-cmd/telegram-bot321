from datetime import date, timedelta

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.config import Settings
from app.database.db import Database
from app.keyboards.admin import (
    admin_menu_kb,
    bookings_manage_kb,
    slots_manage_kb,
)
from app.keyboards.calendar import month_calendar_kb
from app.keyboards.common import back_to_menu_kb
from app.services.scheduler import ReminderService
from app.states.admin import AdminStates
from app.utils.dates import format_date

router = Router()


# =========================
# Utils
# =========================

def _is_admin(user_id: int, settings: Settings) -> bool:
    return user_id == settings.admin_id


def _valid_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def _month_range():
    today = date.today()
    month_later = today + timedelta(days=31)
    return today.strftime("%Y-%m-%d"), month_later.strftime("%Y-%m-%d")


# =========================
# Admin panel
# =========================

@router.callback_query(F.data == "admin:panel")
async def admin_panel(callback: CallbackQuery, settings: Settings, state: FSMContext):
    if not _is_admin(callback.from_user.id, settings):
        await callback.answer("Нет доступа", show_alert=True)
        return

    await state.clear()

    await callback.message.edit_text(
        "<b>Админ-панель</b>\nВыберите действие:",
        parse_mode="HTML",
        reply_markup=admin_menu_kb(),
    )
    await callback.answer()


# =========================
# Add work day
# =========================

@router.callback_query(F.data == "admin:add_day")
async def add_day_start(callback: CallbackQuery, settings: Settings, state: FSMContext):
    if not _is_admin(callback.from_user.id, settings):
        await callback.answer("Нет доступа", show_alert=True)
        return

    await state.set_state(AdminStates.waiting_add_day)

    await callback.message.edit_text(
        "Введите дату рабочего дня (YYYY-MM-DD):",
        reply_markup=back_to_menu_kb(),
    )
    await callback.answer()


@router.message(AdminStates.waiting_add_day)
async def add_day_save(message: Message, db: Database, state: FSMContext):
    if not _valid_date(message.text):
        await message.answer("Неверный формат даты.")
        return

    db.add_work_day(message.text.strip())

    await state.clear()
    await message.answer("Рабочий день добавлен.", reply_markup=admin_menu_kb())


# =========================
# Add slot
# =========================

@router.callback_query(F.data == "admin:add_slot")
async def add_slot_start(callback: CallbackQuery, settings: Settings, state: FSMContext):
    if not _is_admin(callback.from_user.id, settings):
        await callback.answer("Нет доступа", show_alert=True)
        return

    await state.set_state(AdminStates.waiting_add_slot_date)

    await callback.message.edit_text(
        "Введите дату для слота (YYYY-MM-DD):",
        reply_markup=back_to_menu_kb(),
    )
    await callback.answer()


@router.message(AdminStates.waiting_add_slot_date)
async def add_slot_date(message: Message, state: FSMContext):
    if not _valid_date(message.text):
        await message.answer("Неверный формат даты.")
        return

    await state.update_data(date=message.text.strip())
    await state.set_state(AdminStates.waiting_add_slot_time)

    await message.answer("Введите время (HH:MM):")


@router.message(AdminStates.waiting_add_slot_time)
async def add_slot_time(message: Message, db: Database, state: FSMContext):
    time = message.text.strip()
    data = await state.get_data()

    if len(time) != 5 or time[2] != ":":
        await message.answer("Неверный формат времени.")
        return

    db.add_slot(data["date"], time)

    await state.clear()
    await message.answer("Слот добавлен.", reply_markup=admin_menu_kb())


# =========================
# Delete slot
# =========================

@router.callback_query(F.data == "admin:delete_slot")
async def delete_slot_start(callback: CallbackQuery, settings: Settings, state: FSMContext):
    if not _is_admin(callback.from_user.id, settings):
        await callback.answer("Нет доступа", show_alert=True)
        return

    await state.set_state(AdminStates.waiting_delete_slot_date)

    await callback.message.edit_text("Введите дату:")
    await callback.answer()


@router.message(AdminStates.waiting_delete_slot_date)
async def delete_slot_date(message: Message, db: Database, state: FSMContext):
    if not _valid_date(message.text):
        await message.answer("Неверный формат даты.")
        return

    slots = db.get_free_slots(message.text.strip())

    if not slots:
        await message.answer("Нет слотов.", reply_markup=admin_menu_kb())
        await state.clear()
        return

    await state.clear()

    await message.answer(
        "Выберите слот:",
        reply_markup=slots_manage_kb("admin:delete_slot_pick", message.text.strip(), slots),
    )


@router.callback_query(F.data.startswith("admin:delete_slot_pick"))
async def delete_slot_pick(callback: CallbackQuery, db: Database, settings: Settings):
    if not _is_admin(callback.from_user.id, settings):
        await callback.answer("Нет доступа", show_alert=True)
        return

    _, date_str, time_str = callback.data.split(":")

    db.delete_slot(date_str, time_str)

    await callback.message.edit_text("Слот удалён.", reply_markup=admin_menu_kb())
    await callback.answer()


# =========================
# Close day
# =========================

@router.callback_query(F.data == "admin:close_day")
async def close_day_start(callback: CallbackQuery, settings: Settings, state: FSMContext):
    if not _is_admin(callback.from_user.id, settings):
        await callback.answer("Нет доступа", show_alert=True)
        return

    await state.set_state(AdminStates.waiting_close_day)

    await callback.message.edit_text("Введите дату закрытия:")
    await callback.answer()


@router.message(AdminStates.waiting_close_day)
async def close_day_save(message: Message, db: Database, state: FSMContext):
    if not _valid_date(message.text):
        await message.answer("Неверный формат даты.")
        return

    db.close_day(message.text.strip())

    await state.clear()
    await message.answer("День закрыт.", reply_markup=admin_menu_kb())


# =========================
# View schedule
# =========================

@router.callback_query(F.data == "admin:view_schedule")
async def view_schedule(callback: CallbackQuery, settings: Settings, state: FSMContext, db: Database):
    if not _is_admin(callback.from_user.id, settings):
        await callback.answer("Нет доступа", show_alert=True)
        return

    await state.set_state(AdminStates.waiting_view_schedule)

    today = date.today()
    month_later = today + timedelta(days=31)

    days = set(db.get_month_work_days(today.strftime("%Y-%m-%d"), month_later.strftime("%Y-%m-%d")))

    await callback.message.edit_text(
        "Выберите дату:",
        reply_markup=month_calendar_kb(days),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:pick_date"))
async def view_schedule_pick(callback: CallbackQuery, db: Database, state: FSMContext):
    _, date_str = callback.data.split(":")

    schedule = db.get_schedule_by_date(date_str)

    if not schedule:
        await callback.message.edit_text("Нет слотов.", reply_markup=admin_menu_kb())
        await state.clear()
        await callback.answer()
        return

    text = [f"<b>{format_date(date_str)}</b>"]

    for row in schedule:
        if row["booking_id"]:
            text.append(f"{row['time']} — занято ({row['name']})")
        else:
            text.append(f"{row['time']} — свободно")

    await callback.message.edit_text("\n".join(text), parse_mode="HTML", reply_markup=admin_menu_kb())

    await state.clear()
    await callback.answer()


# =========================
# Cancel booking
# =========================

@router.callback_query(F.data == "admin:cancel_booking")
async def cancel_booking_start(callback: CallbackQuery, settings: Settings, state: FSMContext):
    if not _is_admin(callback.from_user.id, settings):
        await callback.answer("Нет доступа", show_alert=True)
        return

    await state.set_state(AdminStates.waiting_cancel_booking_date)

    await callback.message.edit_text("Введите дату:")
    await callback.answer()


@router.message(AdminStates.waiting_cancel_booking_date)
async def cancel_booking_date(message: Message, db: Database, state: FSMContext):
    if not _valid_date(message.text):
        await message.answer("Неверный формат даты.")
        return

    bookings = db.get_bookings_for_date(message.text.strip())

    if not bookings:
        await message.answer("Нет записей.", reply_markup=admin_menu_kb())
        await state.clear()
        return

    await state.clear()

    prepared = [
        {"id": b["id"], "name": b["name"], "time": b["time"]}
        for b in bookings
    ]

    await message.answer(
        "Выберите запись:",
        reply_markup=bookings_manage_kb(message.text.strip(), prepared),
    )


@router.callback_query(F.data.startswith("admin:cancel_by_id"))
async def cancel_by_id(
    callback: CallbackQuery,
    db: Database,
    settings: Settings,
    reminder_service: ReminderService,
):
    if not _is_admin(callback.from_user.id, settings):
        await callback.answer("Нет доступа", show_alert=True)
        return

    booking_id = int(callback.data.split(":")[1])

    booking = db.cancel_booking_by_id(booking_id)

    if not booking:
        await callback.message.edit_text("Не найдено.", reply_markup=admin_menu_kb())
        await callback.answer()
        return

    reminder_service.cancel_reminder(booking["reminder_job_id"])

    await callback.message.edit_text("Отменено.", reply_markup=admin_menu_kb())
    await callback.answer()