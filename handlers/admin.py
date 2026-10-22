import re
import logging
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from config import SUPER_ADMIN_ID
from database import (
    get_auth_info,
    update_password,
    get_stats,
    get_user_filters,
    is_admin,
    is_super_admin,
    add_admin,
    remove_admin,
    get_all_admins,
    get_poll_interval,
    set_poll_interval,
    get_user_language
)
from keyboards import (
    get_main_keyboard, 
    get_cancel_reply_keyboard, 
    get_admin_panel_keyboard,
    get_poll_interval_keyboard,
    get_admins_management_keyboard,
    get_remove_admin_keyboard
)

logger = logging.getLogger(__name__)
router = Router()

class AdminChangePasswordStates(StatesGroup):
    waiting_for_old_password = State()
    waiting_for_new_password = State()

class AdminIntervalStates(StatesGroup):
    waiting_for_custom_interval = State()

class AdminUserManagementStates(StatesGroup):
    waiting_for_add_admin_id = State()

@router.message(F.text.in_(["❌ Отмена", "❌ Bekor qilish"]))
@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        return
    await state.clear()
    user_id = message.from_user.id
    user_is_adm = await is_admin(user_id)
    user_filters = await get_user_filters(user_id)
    is_mon = bool(user_filters.get("is_monitoring_active", 1))
    lang = await get_user_language(user_id)
    cancel_text = "Bekor qilindi." if lang == "uz" else "Действие отменено."
    await message.answer(
        cancel_text,
        reply_markup=get_main_keyboard(is_admin=user_is_adm, is_monitoring=is_mon, lang=lang)
    )

# ==================== MAIN ADMIN PANEL ====================

@router.message(F.text.in_(["📊 Админ-панель", "📊 Admin paneli"]))
@router.message(Command("admin"))
async def admin_panel(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if not await is_admin(user_id):
        await message.answer("⛔️ Эта панель доступна только администраторам.")
        return

    await state.clear()
    stats = await get_stats()
    is_super = is_super_admin(user_id)
    role_str = "👑 <b>Главный администратор</b>" if is_super else "👤 <b>Администратор</b>"

    text = (
        f"📊 <b>Панель управления администратора</b>\n\n"
        f"Ваш статус: {role_str}\n\n"
        f"👥 <b>Всего пользователей в базе:</b> {stats['total_users']}\n"
        f"🟢 <b>Авторизованных пользователей:</b> {stats['authorized_users']}\n"
        f"🛡 <b>Администраторов:</b> {stats['total_admins']}\n"
        f"🏎 <b>Просканировано объявлений OLX:</b> {stats['seen_ads']}\n"
        f"⏱ <b>Текущая частота проверки:</b> каждые <b>{stats['poll_interval']:.1f} сек.</b>\n\n"
        f"🔑 <b>Текущий пароль для пользователей:</b> <code>{stats['current_password']}</code> (v{stats['password_version']})\n\n"
        f"<i>Администраторам доступ к боту всегда открыт без пароля.</i>"
    )
    await message.answer(text, reply_markup=get_admin_panel_keyboard(is_super, stats['poll_interval']), parse_mode="HTML")

@router.callback_query(F.data == "admin_panel_main")
async def back_to_admin_panel(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not await is_admin(user_id):
        await callback.answer("⛔️ Нет прав администратора.", show_alert=True)
        return

    await state.clear()
    stats = await get_stats()
    is_super = is_super_admin(user_id)
    role_str = "👑 <b>Главный администратор</b>" if is_super else "👤 <b>Администратор</b>"

    text = (
        f"📊 <b>Панель управления администратора</b>\n\n"
        f"Ваш статус: {role_str}\n\n"
        f"👥 <b>Всего пользователей в базе:</b> {stats['total_users']}\n"
        f"🟢 <b>Авторизованных пользователей:</b> {stats['authorized_users']}\n"
        f"🛡 <b>Администраторов:</b> {stats['total_admins']}\n"
        f"🏎 <b>Просканировано объявлений OLX:</b> {stats['seen_ads']}\n"
        f"⏱ <b>Текущая частота проверки:</b> каждые <b>{stats['poll_interval']:.1f} сек.</b>\n\n"
        f"🔑 <b>Текущий пароль для пользователей:</b> <code>{stats['current_password']}</code> (v{stats['password_version']})\n\n"
        f"<i>Администраторам доступ к боту всегда открыт без пароля.</i>"
    )
    try:
        await callback.message.edit_text(text, reply_markup=get_admin_panel_keyboard(is_super, stats['poll_interval']), parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()

@router.callback_query(F.data == "admin_refresh_stats")
async def refresh_admin_stats(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await is_admin(user_id):
        await callback.answer("⛔️ Нет прав.", show_alert=True)
        return

    stats = await get_stats()
    is_super = is_super_admin(user_id)
    role_str = "👑 <b>Главный администратор</b>" if is_super else "👤 <b>Администратор</b>"

    text = (
        f"📊 <b>Панель управления администратора</b> (Обновлено)\n\n"
        f"Ваш статус: {role_str}\n\n"
        f"👥 <b>Всего пользователей в базе:</b> {stats['total_users']}\n"
        f"🟢 <b>Авторизованных пользователей:</b> {stats['authorized_users']}\n"
        f"🛡 <b>Администраторов:</b> {stats['total_admins']}\n"
        f"🏎 <b>Просканировано объявлений OLX:</b> {stats['seen_ads']}\n"
        f"⏱ <b>Текущая частота проверки:</b> каждые <b>{stats['poll_interval']:.1f} сек.</b>\n\n"
        f"🔑 <b>Текущий пароль для пользователей:</b> <code>{stats['current_password']}</code> (v{stats['password_version']})\n\n"
        f"<i>Администраторам доступ к боту всегда открыт без пароля.</i>"
    )
    try:
        await callback.message.edit_text(text, reply_markup=get_admin_panel_keyboard(is_super, stats['poll_interval']), parse_mode="HTML")
    except Exception:
        pass
    await callback.answer("Статистика обновлена!")

@router.callback_query(F.data == "close_admin")
async def close_admin_panel(callback: CallbackQuery):
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer()

# ==================== POLL INTERVAL CONFIGURATION ====================

@router.callback_query(F.data == "admin_open_interval")
async def open_poll_interval_menu(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await is_admin(user_id):
        await callback.answer("⛔️ Нет прав.", show_alert=True)
        return

    current_int = await get_poll_interval()
    text = (
        f"⏱ <b>Настройка частоты проверки сайта OLX.uz</b>\n\n"
        f"Текущая частота: <b>каждые {current_int:.1f} сек.</b>\n\n"
        f"Выберите готовый интервал или нажмите «✏️ Ввести вручную»:"
    )
    try:
        await callback.message.edit_text(text, reply_markup=get_poll_interval_keyboard(current_int), parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()

@router.callback_query(F.data.startswith("set_interval_"))
async def set_interval_preset(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await is_admin(user_id):
        return

    val_str = callback.data.replace("set_interval_", "")
    try:
        val = float(val_str)
        await set_poll_interval(val)
        await callback.answer(f"✅ Частота установлена: {val} сек.")
    except Exception as e:
        logger.error(f"Error setting interval: {e}")
        await callback.answer("Ошибка сохранения.")

    current_int = await get_poll_interval()
    is_super = is_super_admin(user_id)
    text = (
        f"⏱ <b>Настройка частоты проверки сайта OLX.uz</b>\n\n"
        f"✅ Установлена новая частота: <b>каждые {current_int:.1f} сек.</b>\n"
        f"Монитор мгновенно применил новую скорость."
    )
    try:
        await callback.message.edit_text(text, reply_markup=get_poll_interval_keyboard(current_int), parse_mode="HTML")
    except Exception:
        pass

@router.callback_query(F.data == "admin_custom_interval")
async def ask_custom_interval(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not await is_admin(user_id):
        return

    await state.set_state(AdminIntervalStates.waiting_for_custom_interval)
    await callback.message.answer(
        "✏️ <b>Введите желаемый интервал проверки в секундах:</b>\n\n"
        "Например: <code>1</code>, <code>0.5</code>, <code>2.5</code> или <code>5</code>\n"
        "<i>Минимальный интервал: 0.5 сек.</i>\n\n"
        "<i>Для отмены нажмите кнопку «❌ Отмена» ниже.</i>",
        reply_markup=get_cancel_reply_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(AdminIntervalStates.waiting_for_custom_interval)
async def process_custom_interval(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if not await is_admin(user_id):
        return

    raw = message.text.strip().replace(",", ".") if message.text else ""
    if raw == "❌ Отмена" or raw.startswith("/"):
        await state.clear()
        user_filters = await get_user_filters(user_id)
        is_mon = bool(user_filters.get("is_monitoring_active", 1))
        lang = await get_user_language(user_id)
        cancel_text = "Bekor qilindi." if lang == "uz" else "Отменено."
        await message.answer(cancel_text, reply_markup=get_main_keyboard(is_admin=True, is_monitoring=is_mon, lang=lang))
        return

    try:
        val = float(raw)
        if val < 0.5:
            await message.answer(
                "⚠️ Минимальный безопасный интервал — 0.5 секунды. Введите число от 0.5:",
                reply_markup=get_cancel_reply_keyboard()
            )
            return

        await set_poll_interval(val)
        await state.clear()
        user_filters = await get_user_filters(user_id)
        is_mon = bool(user_filters.get("is_monitoring_active", 1))
        lang = await get_user_language(user_id)

        await message.answer(
            f"✅ <b>Частота обновления успешно изменена!</b>\n\n"
            f"Новое значение: <b>каждые {val:.1f} сек.</b>\n"
            f"Бот немедленно перешёл на новую скорость мониторинга.",
            reply_markup=get_main_keyboard(is_admin=True, is_monitoring=is_mon, lang=lang),
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer(
            "⚠️ Не удалось распознать число. Введите число секунд (например <code>1.0</code> или <code>2</code>):",
            reply_markup=get_cancel_reply_keyboard(),
            parse_mode="HTML"
        )

# ==================== SUPER ADMIN: ADMINS MANAGEMENT ====================

@router.callback_query(F.data == "admin_manage_admins")
async def manage_admins_menu(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not is_super_admin(user_id):
        await callback.answer("⛔️ Управлять администраторами может только Главный Администратор.", show_alert=True)
        return

    await state.clear()
    admins = await get_all_admins()

    lines = ["👥 <b>Список администраторов бота:</b>\n"]
    for i, a in enumerate(admins, 1):
        crown = "👑 <b>Главный:</b>" if a.get("is_super") else "👤 <b>Админ:</b>"
        uname = f"@{a['username']}" if a.get("username") else "без @username"
        lines.append(f"{i}. {crown} {a['display_name']} (ID: <code>{a['user_id']}</code>, {uname})")

    lines.append(
        "\n<i>Главный администратор может добавлять новых администраторов и лишать прав. "
        "Обычные администраторы могут менять частоту, пароль и смотреть статистику.</i>"
    )

    text = "\n".join(lines)
    try:
        await callback.message.edit_text(text, reply_markup=get_admins_management_keyboard(admins), parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()

@router.callback_query(F.data == "admin_add_admin_start")
async def add_admin_start(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not is_super_admin(user_id):
        await callback.answer("⛔️ Доступно только Главному Администратору.", show_alert=True)
        return

    await state.set_state(AdminUserManagementStates.waiting_for_add_admin_id)
    await callback.message.answer(
        "➕ <b>Назначение нового администратора</b>\n\n"
        "Отправьте <b>Telegram User ID</b> пользователя (число, например: <code>1234567890</code>).\n"
        "<i>Пользователь может узнать свой ID через бота @userinfobot или переслав вам сообщение.</i>\n\n"
        "<i>Для отмены нажмите кнопку «❌ Отмена» ниже.</i>",
        reply_markup=get_cancel_reply_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(AdminUserManagementStates.waiting_for_add_admin_id)
async def process_add_admin_input(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    if not is_super_admin(user_id):
        return

    raw = message.text.strip() if message.text else ""
    lang = await get_user_language(user_id)
    if raw in ("❌ Отмена", "❌ Bekor qilish") or raw.startswith("/"):
        await state.clear()
        user_filters = await get_user_filters(user_id)
        is_mon = bool(user_filters.get("is_monitoring_active", 1))
        cancel_text = "Bekor qilindi." if lang == "uz" else "Назначение отменено."
        await message.answer(cancel_text, reply_markup=get_main_keyboard(is_admin=True, is_monitoring=is_mon, lang=lang))
        return

    # Extract digits or clean input
    clean_id = re.sub(r"[^\d]", "", raw)
    if not clean_id:
        await message.answer(
            "⚠️ Пожалуйста, введите числовой Telegram ID пользователя (например: <code>1234567890</code>):",
            reply_markup=get_cancel_reply_keyboard(),
            parse_mode="HTML"
        )
        return

    target_id = int(clean_id)
    if target_id == SUPER_ADMIN_ID:
        await message.answer("Вы уже являетесь Главным Администратором!", reply_markup=get_cancel_reply_keyboard())
        return

    # Try to fetch chat info via bot to get username/first_name
    target_username = None
    target_first_name = None
    try:
        chat_info = await bot.get_chat(target_id)
        target_username = chat_info.username
        target_first_name = chat_info.first_name
    except Exception:
        pass

    await add_admin(target_id, target_username, target_first_name, added_by=user_id)
    await state.clear()

    user_filters = await get_user_filters(user_id)
    is_mon = bool(user_filters.get("is_monitoring_active", 1))
    lang = await get_user_language(user_id)

    display_target = target_first_name or (f"@{target_username}" if target_username else f"ID {target_id}")

    await message.answer(
        f"✅ <b>Пользователь {display_target} (ID: <code>{target_id}</code>) успешно назначен администратором!</b>\n\n"
        f"Теперь ему доступны:\n"
        f"• Вход в бот <b>без ввода пароля</b> всегда\n"
        f"• Настройка частоты обновлений\n"
        f"• Смена пароля бота\n"
        f"• Просмотр статистики\n\n"
        f"<i>Лишить его прав администратора можете только вы.</i>",
        reply_markup=get_main_keyboard(is_admin=True, is_monitoring=is_mon, lang=lang),
        parse_mode="HTML"
    )

    # Attempt to notify new admin
    try:
        target_lang = await get_user_language(target_id)
        if target_lang == "uz":
            notify_text = (
                "🎉 <b>Tabriklaymiz!</b>\n\n"
                "Bosh administrator sizni monitoring botining <b>Administratori</b> etib tayinladi!\n\n"
                "Sizga botdan parolsiz foydalanish, yangilanish tezligini sozlash, "
                "parolni o'zgartirish va «📊 Admin paneli» imkoniyatlari ochildi."
            )
        else:
            notify_text = (
                "🎉 <b>Поздравляем!</b>\n\n"
                "Главный администратор назначил вас <b>Администратором</b> бота мониторинга OLX.uz!\n\n"
                "Вам открыт постоянный доступ к боту без пароля, настройка скорости обновлений, "
                "смена пароля и статистика в меню «📊 Админ-панель»."
            )
        await bot.send_message(
            chat_id=target_id,
            text=notify_text,
            reply_markup=get_main_keyboard(is_admin=True, is_monitoring=True, lang=target_lang),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.debug(f"Could not notify new admin {target_id}: {e}")

@router.callback_query(F.data == "admin_remove_admin_list")
async def remove_admin_list_menu(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not is_super_admin(user_id):
        await callback.answer("⛔️ Доступно только Главному Администратору.", show_alert=True)
        return

    admins = await get_all_admins()
    removable = [a for a in admins if not a.get("is_super")]
    if not removable:
        await callback.answer("Нет назначенных обычных администраторов.", show_alert=True)
        return

    text = (
        "➖ <b>Отзыв прав администратора:</b>\n\n"
        "Нажмите на администратора, которого вы хотите снять с должности:"
    )
    try:
        await callback.message.edit_text(text, reply_markup=get_remove_admin_keyboard(admins), parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()

@router.callback_query(F.data.startswith("confirm_remove_admin_"))
async def execute_remove_admin(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    if not is_super_admin(user_id):
        await callback.answer("⛔️ Доступно только Главному Администратору.", show_alert=True)
        return

    target_id = int(callback.data.replace("confirm_remove_admin_", ""))
    if target_id == SUPER_ADMIN_ID:
        await callback.answer("Нельзя снять Главного Администратора!", show_alert=True)
        return

    await remove_admin(target_id)
    await callback.answer("Права администратора отозваны!")

    # Attempt to notify removed admin
    try:
        target_lang = await get_user_language(target_id)
        if target_lang == "uz":
            revoked_text = (
                "ℹ️ <b>Bosh administrator tomonidan sizning administratorlik huquqlaringiz bekor qilindi.</b>\n"
                "Botdan foydalanishni davom ettirish uchun parolni kiritishingiz kerak bo'ladi."
            )
        else:
            revoked_text = (
                "ℹ️ <b>Ваши права администратора были отозваны Главным Администратором.</b>\n"
                "Для дальнейшего использования бота вам потребуется ввести пароль доступа."
            )
        await bot.send_message(
            chat_id=target_id,
            text=revoked_text,
            reply_markup=get_main_keyboard(is_admin=False, is_monitoring=True, lang=target_lang),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.debug(f"Could not notify revoked admin {target_id}: {e}")

    # Return to manage admins menu
    admins = await get_all_admins()
    lines = ["👥 <b>Список администраторов бота:</b>\n"]
    for i, a in enumerate(admins, 1):
        crown = "👑 <b>Главный:</b>" if a.get("is_super") else "👤 <b>Админ:</b>"
        uname = f"@{a['username']}" if a.get("username") else "без @username"
        lines.append(f"{i}. {crown} {a['display_name']} (ID: <code>{a['user_id']}</code>, {uname})")

    lines.append(f"\n✅ <i>Права у пользователя {target_id} успешно отозваны.</i>")
    text = "\n".join(lines)
    try:
        await callback.message.edit_text(text, reply_markup=get_admins_management_keyboard(admins), parse_mode="HTML")
    except Exception:
        pass

# ==================== PASSWORD CHANGE ====================

@router.message(F.text.in_(["🔑 Сменить пароль", "🔑 Parolni o'zgartirish"]))
@router.message(Command("change_password"))
@router.callback_query(F.data == "admin_change_pw")
async def start_change_password(event: Message | CallbackQuery, state: FSMContext):
    user_id = event.from_user.id
    if not await is_admin(user_id):
        if isinstance(event, CallbackQuery):
            await event.answer("⛔️ У вас нет прав администратора.", show_alert=True)
        else:
            await event.answer("⛔️ Эта команда доступна только администраторам.")
        return

    if isinstance(event, CallbackQuery):
        await event.answer()
        msg = event.message
    else:
        msg = event

    await state.set_state(AdminChangePasswordStates.waiting_for_old_password)
    await msg.answer(
        "🔐 <b>Смена мастер-пароля бота</b>\n\n"
        "Для безопасности подтвердите текущий пароль.\n"
        "Пожалуйста, <b>введите старый (текущий) пароль:</b>\n\n"
        "<i>Для отмены нажмите кнопку «❌ Отмена» ниже.</i>",
        reply_markup=get_cancel_reply_keyboard(),
        parse_mode="HTML"
    )

@router.message(AdminChangePasswordStates.waiting_for_old_password)
async def process_old_password(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if not await is_admin(user_id):
        return

    entered_password = message.text.strip() if message.text else ""
    current_password, _ = await get_auth_info()

    if entered_password != current_password:
        await message.answer(
            "❌ <b>Неверный старый пароль!</b>\n\n"
            "Пожалуйста, введите правильный текущий пароль или нажмите «❌ Отмена»:",
            reply_markup=get_cancel_reply_keyboard(),
            parse_mode="HTML"
        )
        return

    await state.set_state(AdminChangePasswordStates.waiting_for_new_password)
    await message.answer(
        "✅ <b>Старый пароль подтверждён!</b>\n\n"
        "Теперь <b>введите новый пароль</b> для доступа к боту:\n"
        "<i>(Минимум 3 символа)</i>",
        reply_markup=get_cancel_reply_keyboard(),
        parse_mode="HTML"
    )

@router.message(AdminChangePasswordStates.waiting_for_new_password)
async def process_new_password(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if not await is_admin(user_id):
        return

    new_password = message.text.strip() if message.text else ""
    if len(new_password) < 3:
        await message.answer(
            "⚠️ Пароль слишком короткий. Введите пароль не менее 3 символов:",
            reply_markup=get_cancel_reply_keyboard()
        )
        return

    new_version = await update_password(new_password)
    await state.clear()

    user_filters = await get_user_filters(user_id)
    is_mon = bool(user_filters.get("is_monitoring_active", 1))
    lang = await get_user_language(user_id)

    await message.answer(
        f"🎉 <b>Пароль успешно изменён!</b>\n\n"
        f"🔑 <b>Новый пароль:</b> <code>{new_password}</code>\n"
        f"🔢 <b>Версия пароля:</b> v{new_version}\n\n"
        f"🔒 <b>Внимание:</b> Все обычные пользователи разлогинены!\n"
        f"Им потребуется ввести новый пароль для продолжения работы.\n"
        f"<i>Все администраторы сохраняют постоянный доступ без ввода пароля.</i>",
        reply_markup=get_main_keyboard(is_admin=True, is_monitoring=is_mon, lang=lang),
        parse_mode="HTML"
    )
    logger.info(f"Admin {user_id} changed password to '{new_password}' (v{new_version})")
