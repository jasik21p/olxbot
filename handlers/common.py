import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from config import SUPER_ADMIN_ID
from database import (
    is_user_authorized,
    toggle_monitoring,
    get_user_filters,
    count_seen_ads,
    get_poll_interval,
    is_admin,
    get_user_language
)
from keyboards import get_main_keyboard, format_filter_summary
from handlers.auth import AuthStates
from locales import t

logger = logging.getLogger(__name__)
router = Router()

@router.message(F.text.in_(["⏸ Приостановить", "▶️ Возобновить", "⏸ To'xtatish", "▶️ Davom ettirish"]))
async def toggle_monitoring_handler(message: Message, state: FSMContext):
    user_id = message.from_user.id
    lang = await get_user_language(user_id)
    if not await is_user_authorized(user_id):
        await state.set_state(AuthStates.waiting_for_password)
        await message.answer(t("unauthorized_reminder", lang), parse_mode="HTML")
        return

    await state.clear()
    new_state = await toggle_monitoring(user_id)
    user_is_adm = await is_admin(user_id)

    text = t("monitoring_resumed", lang) if new_state else t("monitoring_paused", lang)

    await message.answer(
        text, 
        reply_markup=get_main_keyboard(is_admin=user_is_adm, is_monitoring=new_state, lang=lang),
        parse_mode="HTML"
    )

@router.message(F.text.in_(["⚙️ Статус мониторинга", "⚙️ Monitoring holati"]))
@router.message(Command("status"))
async def status_handler(message: Message, state: FSMContext):
    user_id = message.from_user.id
    lang = await get_user_language(user_id)
    if not await is_user_authorized(user_id):
        await state.set_state(AuthStates.waiting_for_password)
        await message.answer(t("unauthorized_reminder", lang), parse_mode="HTML")
        return

    await state.clear()
    filters = await get_user_filters(user_id)
    is_mon = bool(filters.get("is_monitoring_active", 1))
    user_is_adm = await is_admin(user_id)
    total_ads = await count_seen_ads()
    current_interval = await get_poll_interval()

    if lang == "uz":
        status_icon = "🟢 <b>FAOL</b>" if is_mon else "🔴 <b>TO'XTATILGAN</b>"
        text = (
            f"📊 <b>Botning ish holati:</b>\n\n"
            f"📡 <b>Monitoring holati:</b> {status_icon}\n"
            f"⏱ <b>Tekshirish chastotasi:</b> har {current_interval:.1f} soniyada.\n"
            f"🏎 <b>Jami qayta ishlangan e'lonlar:</b> {total_ads}\n\n"
            f"{format_filter_summary(filters, lang=lang)}"
        )
    else:
        status_icon = "🟢 <b>АКТИВЕН</b>" if is_mon else "🔴 <b>ПРИОСТАНОВЛЕН</b>"
        text = (
            f"📊 <b>Статус работы бота:</b>\n\n"
            f"📡 <b>Статус мониторинга:</b> {status_icon}\n"
            f"⏱ <b>Частота проверки:</b> каждые {current_interval:.1f} сек.\n"
            f"🏎 <b>Всего обработано объявлений:</b> {total_ads}\n\n"
            f"{format_filter_summary(filters, lang=lang)}"
        )

    await message.answer(
        text, 
        reply_markup=get_main_keyboard(is_admin=user_is_adm, is_monitoring=is_mon, lang=lang),
        parse_mode="HTML"
    )

# Fallback for unauthorized messages
@router.message()
async def fallback_unauthorized(message: Message, state: FSMContext):
    user_id = message.from_user.id
    lang = await get_user_language(user_id)
    if not await is_user_authorized(user_id):
        await state.set_state(AuthStates.waiting_for_password)
        await message.answer(
            t("unauthorized_reminder", lang),
            parse_mode="HTML"
        )
