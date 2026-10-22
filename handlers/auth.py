import logging
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from config import SUPER_ADMIN_ID
from database import (
    get_or_create_user, 
    is_user_authorized, 
    authenticate_user, 
    get_auth_info,
    get_user_filters,
    is_admin,
    is_super_admin,
    get_poll_interval,
    get_user_language,
    set_user_language
)
from keyboards import (
    get_main_keyboard, 
    get_language_keyboard
)
from locales import t

logger = logging.getLogger(__name__)
router = Router()

class AuthStates(StatesGroup):
    waiting_for_language = State()
    waiting_for_password = State()

KNOWN_MENU_COMMANDS = [
    "🔍 Настройки фильтров", "🔍 Filtr sozlamalari",
    "⚙️ Статус мониторинга", "⚙️ Monitoring holati",
    "⏸ Приостановить", "⏸ To'xtatish",
    "▶️ Возобновить", "▶️ Davom ettirish",
    "🌐 Сменить язык", "🌐 Tilni o'zgartirish",
    "🔑 Сменить пароль", "🔑 Parolni o'zgartirish",
    "📊 Админ-панель", "📊 Admin paneli"
]

# ==================== LANGUAGE CHANGE (FOR AUTHORIZED USERS & ADMINS) ====================

@router.message(F.text.in_(["🌐 Сменить язык", "🌐 Tilni o'zgartirish"]))
@router.message(Command("language", "lang"))
async def cmd_change_language(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if not await is_user_authorized(user_id):
        lang = await get_user_language(user_id)
        await state.set_state(AuthStates.waiting_for_password)
        await message.answer(t("unauthorized_reminder", lang), parse_mode="HTML")
        return

    lang = await get_user_language(user_id)
    await message.answer(
        t("choose_lang", lang), 
        reply_markup=get_language_keyboard(prefix="user_lang_"), 
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("user_lang_"))
async def process_user_language_change(callback: CallbackQuery):
    user_id = callback.from_user.id
    new_lang = callback.data.replace("user_lang_", "")
    await set_user_language(user_id, new_lang)

    user_is_adm = await is_admin(user_id)
    user_filters = await get_user_filters(user_id)
    is_mon = bool(user_filters.get("is_monitoring_active", 1))

    confirm_msg = t("lang_changed", new_lang)
    try:
        await callback.message.delete()
    except Exception:
        pass

    await callback.message.answer(
        confirm_msg,
        reply_markup=get_main_keyboard(is_admin=user_is_adm, is_monitoring=is_mon, lang=new_lang),
        parse_mode="HTML"
    )
    await callback.answer()

# ==================== /START COMMAND ====================

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name

    await get_or_create_user(user_id, username, first_name)
    user_is_adm = await is_admin(user_id)
    user_is_super = is_super_admin(user_id)
    lang = await get_user_language(user_id)

    await state.clear()

    # ALL ADMINISTRATORS HAVE INSTANT PASSWORD-FREE ACCESS ALWAYS
    if user_is_adm:
        user_filters = await get_user_filters(user_id)
        is_mon = bool(user_filters.get("is_monitoring_active", 1))
        poll_int = await get_poll_interval()
        role_label = "👑 Главный Администратор" if user_is_super else "👤 Администратор"
        if lang == "uz":
            role_label = "👑 Bosh Administrator" if user_is_super else "👤 Administrator"
            greeting = (
                f"👋 <b>Xush kelibsiz, {role_label} ({first_name})!</b>\n\n"
                f"⚡️ <b>Monitoring tizimi faol.</b>\n"
                f"⏱ Tekshirish chastotasi: <b>har {poll_int:.1f} soniyada.</b>\n\n"
                f"Sizga botdan parolsiz foydalanish, filtrlarni sozlash "
                f"va <b>«📊 Admin paneli»</b> orqali boshqarish imkoniyati berilgan."
            )
        else:
            greeting = (
                f"👋 <b>Добро пожаловать, {role_label} ({first_name})!</b>\n\n"
                f"⚡️ <b>Система мониторинга активна.</b>\n"
                f"⏱ Частота проверки: <b>каждые {poll_int:.1f} сек.</b>\n\n"
                f"Вам открыт постоянный доступ к боту без паролей, управление фильтрами "
                f"и панель управления по кнопке <b>«📊 Админ-панель»</b>."
            )

        await message.answer(
            greeting,
            reply_markup=get_main_keyboard(is_admin=True, is_monitoring=is_mon, lang=lang),
            parse_mode="HTML"
        )
        return

    # Authorized regular user
    if await is_user_authorized(user_id):
        user_filters = await get_user_filters(user_id)
        is_mon = bool(user_filters.get("is_monitoring_active", 1))
        if lang == "uz":
            greeting = (
                f"👋 <b>Qaytganingiz bilan, {first_name}!</b>\n\n"
                f"🚗 Bot e'lonlarni real vaqt rejimida kuzatmoqda.\n\n"
                f"Filtrlar va monitoringni boshqarish uchun quyidagi menyu tugmalaridan foydalaning."
            )
        else:
            greeting = (
                f"👋 <b>С возвращением, {first_name}!</b>\n\n"
                f"🚗 Бот мониторит новые объявления в режиме реального времени.\n\n"
                f"Используйте кнопки меню ниже для управления фильтрами и статусом."
            )

        await message.answer(
            greeting,
            reply_markup=get_main_keyboard(is_admin=False, is_monitoring=is_mon, lang=lang),
            parse_mode="HTML"
        )
        return

    # NEW / UNAUTHORIZED USER:
    # First message: choose language! (DO NOT REVEAL BOT PURPOSE)
    await state.set_state(AuthStates.waiting_for_language)
    await message.answer(
        "🌐 <b>Выберите язык интерфейса / Tilni tanlang:</b>",
        reply_markup=get_language_keyboard(prefix="preauth_lang_"),
        parse_mode="HTML"
    )

# ==================== PRE-AUTH LANGUAGE SELECTION ====================

@router.callback_query(F.data.startswith("preauth_lang_"))
async def process_preauth_language(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    lang_code = callback.data.replace("preauth_lang_", "")
    await set_user_language(user_id, lang_code)

    await state.set_state(AuthStates.waiting_for_password)
    prompt = t("ask_password", lang_code)

    try:
        await callback.message.edit_text(prompt, parse_mode="HTML")
    except Exception:
        await callback.message.answer(prompt, parse_mode="HTML")

    await callback.answer()

# ==================== PASSWORD ENTRY ====================

@router.message(AuthStates.waiting_for_password)
async def process_password_input(message: Message, state: FSMContext):
    user_id = message.from_user.id
    text = message.text.strip() if message.text else ""
    lang = await get_user_language(user_id)

    user_is_adm = await is_admin(user_id)
    if user_is_adm or await is_user_authorized(user_id):
        await state.clear()
        user_filters = await get_user_filters(user_id)
        is_mon = bool(user_filters.get("is_monitoring_active", 1))
        await message.answer(
            t("already_authorized", lang),
            reply_markup=get_main_keyboard(is_admin=user_is_adm, is_monitoring=is_mon, lang=lang)
        )
        return

    # If user sent a menu button or slash command while not authorized
    if text in KNOWN_MENU_COMMANDS or text.startswith("/"):
        await message.answer(
            t("unauthorized_reminder", lang),
            parse_mode="HTML"
        )
        return

    current_password, _ = await get_auth_info()

    if text == current_password:
        await authenticate_user(user_id)
        await state.clear()

        user_filters = await get_user_filters(user_id)
        is_mon = bool(user_filters.get("is_monitoring_active", 1))

        await message.answer(
            t("access_granted", lang),
            reply_markup=get_main_keyboard(is_admin=False, is_monitoring=is_mon, lang=lang),
            parse_mode="HTML"
        )
        logger.info(f"User {user_id} (@{message.from_user.username}) successfully authenticated with password.")
    else:
        await message.answer(
            t("wrong_password", lang),
            parse_mode="HTML"
        )
