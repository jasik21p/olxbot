import re
import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from config import ALL_FUEL_TYPES, UZBEKISTAN_REGIONS
from database import (
    is_user_authorized,
    is_admin,
    get_user_filters,
    update_user_filters,
    reset_user_filters,
    get_user_language
)
from keyboards import (
    format_filter_summary,
    get_filter_menu_keyboard,
    get_region_keyboard,
    get_price_keyboard,
    get_mileage_keyboard,
    get_fuel_keyboard,
    get_cancel_reply_keyboard,
    get_main_keyboard
)
from locales import t

logger = logging.getLogger(__name__)
router = Router()

class FilterCustomStates(StatesGroup):
    waiting_for_custom_price = State()
    waiting_for_custom_mileage = State()
    waiting_for_custom_city = State()

def normalize_range_input(raw: str):
    """Normalizes range string: handles any dashes, spaces, and numbers."""
    if not raw:
        return None, None
    s = raw.strip().replace("–", "-").replace("—", "-").replace("−", "-").replace("_", "-")
    s = s.replace("$", "").replace("сум", "").replace("so'm", "").replace("км", "").replace("km", "").replace(" ", "")

    ot_do = re.search(r'от(\d+(?:\.\d+)?)до(\d+(?:\.\d+)?)', s, re.IGNORECASE)
    if ot_do:
        return float(ot_do.group(1)), float(ot_do.group(2))

    dan_gacha = re.search(r'(\d+(?:\.\d+)?)dan(\d+(?:\.\d+)?)gacha', s, re.IGNORECASE)
    if dan_gacha:
        return float(dan_gacha.group(1)), float(dan_gacha.group(2))

    if "-" in s:
        parts = s.split("-")
        try:
            p1 = float(parts[0]) if parts[0] else None
            p2 = float(parts[1]) if len(parts) > 1 and parts[1] else None
            return p1, p2
        except ValueError:
            pass

    if s.lower().startswith("от") or s.lower().endswith("dan"):
        nums = re.findall(r'\d+(?:\.\d+)?', s)
        if nums:
            return float(nums[0]), None

    if s.lower().startswith("до") or s.lower().endswith("gacha"):
        nums = re.findall(r'\d+(?:\.\d+)?', s)
        if nums:
            return None, float(nums[0])

    nums = re.findall(r'\d+(?:\.\d+)?', s)
    if len(nums) >= 2:
        return float(nums[0]), float(nums[1])
    elif len(nums) == 1:
        return None, float(nums[0])

    return None, None

@router.message(F.text.in_(["🔍 Настройки фильтров", "🔍 Filtr sozlamalari"]))
@router.message(Command("filters"))
async def show_filters(message: Message, state: FSMContext):
    user_id = message.from_user.id
    lang = await get_user_language(user_id)
    if not await is_user_authorized(user_id):
        await message.answer(t("unauthorized_reminder", lang), parse_mode="HTML")
        return

    await state.clear()
    filters = await get_user_filters(user_id)
    text = format_filter_summary(filters, lang=lang)
    await message.answer(text, reply_markup=get_filter_menu_keyboard(filters, lang=lang), parse_mode="HTML")

@router.callback_query(F.data == "back_to_filters")
async def back_to_filters_menu(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)
    if not await is_user_authorized(user_id):
        await callback.answer(t("unauthorized_reminder", lang), show_alert=True)
        return

    await state.clear()
    filters = await get_user_filters(user_id)
    text = format_filter_summary(filters, lang=lang)
    try:
        await callback.message.edit_text(text, reply_markup=get_filter_menu_keyboard(filters, lang=lang), parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()

@router.callback_query(F.data == "close_menu")
async def close_filter_menu(callback: CallbackQuery):
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer()

@router.callback_query(F.data == "reset_filters")
async def reset_filters_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)
    if not await is_user_authorized(user_id):
        return

    await reset_user_filters(user_id)
    filters = await get_user_filters(user_id)
    text = format_filter_summary(filters, lang=lang)
    try:
        await callback.message.edit_text(text, reply_markup=get_filter_menu_keyboard(filters, lang=lang), parse_mode="HTML")
    except Exception:
        pass
    alert_text = "Filtrlar tozalandi!" if lang == "uz" else "Все фильтры сброшены!"
    await callback.answer(alert_text, show_alert=False)

@router.callback_query(F.data == "toggle_currency")
async def toggle_currency_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)
    if not await is_user_authorized(user_id):
        return

    filters = await get_user_filters(user_id)
    new_curr = "UZS" if filters.get("price_currency") == "USD" else "USD"
    await update_user_filters(user_id, price_currency=new_curr, min_price=None, max_price=None)
    
    filters = await get_user_filters(user_id)
    text = format_filter_summary(filters, lang=lang)
    try:
        await callback.message.edit_text(text, reply_markup=get_filter_menu_keyboard(filters, lang=lang), parse_mode="HTML")
    except Exception:
        pass
    alert_text = f"Valyuta o'zgartirildi: {new_curr}!" if lang == "uz" else f"Валюта переключена на {new_curr}!"
    await callback.answer(alert_text)

# ==================== LOCATION FILTERS ====================

@router.callback_query(F.data == "filter_location")
async def open_location_filter(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)
    if not await is_user_authorized(user_id):
        return

    filters = await get_user_filters(user_id)
    current_reg = filters.get("region")
    if lang == "uz":
        text = (
            "📍 <b>Hudud va shaharni sozlash:</b>\n\n"
            "Quyidagi ro'yxatdan kerakli viloyatni tanlang yoki <b>«✏️ Aniq shahar/tumanni kiritish»</b> tugmasini bosing:"
        )
    else:
        text = (
            "📍 <b>Настройка региона и города:</b>\n\n"
            "Выберите интересующий регион из списка ниже или нажмите кнопку <b>«✏️ Ввести конкретный город/район»</b>:"
        )
    try:
        await callback.message.edit_text(text, reply_markup=get_region_keyboard(current_reg, lang=lang), parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()

@router.callback_query(F.data == "region_all")
async def set_region_all_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)
    if not await is_user_authorized(user_id):
        return

    await update_user_filters(user_id, region=None, city=None)
    filters = await get_user_filters(user_id)
    text = format_filter_summary(filters, lang=lang)
    try:
        await callback.message.edit_text(text, reply_markup=get_filter_menu_keyboard(filters, lang=lang), parse_mode="HTML")
    except Exception:
        pass
    alert = "Butun O'zbekiston tanlandi!" if lang == "uz" else "Выбран поиск по всей стране!"
    await callback.answer(alert)

@router.callback_query(F.data.startswith("set_region_"))
async def set_specific_region(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)
    if not await is_user_authorized(user_id):
        return

    region_name = callback.data.replace("set_region_", "")
    await update_user_filters(user_id, region=region_name)
    filters = await get_user_filters(user_id)
    text = format_filter_summary(filters, lang=lang)
    try:
        await callback.message.edit_text(text, reply_markup=get_filter_menu_keyboard(filters, lang=lang), parse_mode="HTML")
    except Exception:
        pass
    alert = f"Hudud tanlandi: {region_name}" if lang == "uz" else f"Регион установлен: {region_name}"
    await callback.answer(alert)

@router.callback_query(F.data == "city_custom")
async def ask_custom_city(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)
    if not await is_user_authorized(user_id):
        return

    await state.set_state(FilterCustomStates.waiting_for_custom_city)
    if lang == "uz":
        text = (
            "✏️ <b>Shahar yoki tuman nomini kiriting:</b>\n\n"
            "Masalan: <code>Toshkent</code>, <code>Samarqand</code>, <code>Chilonzor</code>, <code>Urganch</code>\n"
            "<i>Tozalash uchun 0 yoki «barchasi» so'zini yuboring.</i>\n\n"
            "<i>Bekor qilish uchun «❌ Bekor qilish» tugmasini bosing.</i>"
        )
    else:
        text = (
            "✏️ <b>Введите название города или района:</b>\n\n"
            "Например: <code>Ташкент</code>, <code>Самарканд</code>, <code>Чиланзар</code>, <code>Ургенч</code>\n"
            "<i>Для сброса города отправьте 0 или слово «все».</i>\n\n"
            "<i>Для отмены нажмите «❌ Отмена» ниже.</i>"
        )

    await callback.message.answer(text, reply_markup=get_cancel_reply_keyboard(lang=lang), parse_mode="HTML")
    await callback.answer()

@router.message(FilterCustomStates.waiting_for_custom_city)
async def process_custom_city(message: Message, state: FSMContext):
    user_id = message.from_user.id
    lang = await get_user_language(user_id)
    raw = message.text.strip() if message.text else ""

    if raw in ("❌ Отмена", "❌ Bekor qilish") or raw.startswith("/"):
        await state.clear()
        filters = await get_user_filters(user_id)
        is_mon = bool(filters.get("is_monitoring_active", 1))
        user_is_adm = await is_admin(user_id)
        await message.answer(t("cancelled", lang), reply_markup=get_main_keyboard(is_admin=user_is_adm, is_monitoring=is_mon, lang=lang))
        return

    if raw.lower() in ("0", "все", "barchasi", "любой", "сброс", "нет", "yo'q"):
        city_val = None
    else:
        city_val = raw

    await update_user_filters(user_id, city=city_val)
    await state.clear()

    filters = await get_user_filters(user_id)
    is_mon = bool(filters.get("is_monitoring_active", 1))
    user_is_adm = await is_admin(user_id)
    saved_text = "✅ <b>Manzil saqlandi!</b>\n\n" if lang == "uz" else "✅ <b>Локация сохранена!</b>\n\n"
    await message.answer(
        saved_text + format_filter_summary(filters, lang=lang),
        reply_markup=get_main_keyboard(is_admin=user_is_adm, is_monitoring=is_mon, lang=lang),
        parse_mode="HTML"
    )

# ==================== PRICE FILTERS ====================

@router.callback_query(F.data == "filter_price")
async def open_price_filter(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)
    if not await is_user_authorized(user_id):
        return

    filters = await get_user_filters(user_id)
    curr = filters.get("price_currency", "USD")
    if lang == "uz":
        text = (
            f"💰 <b>Narx oralig'ini sozlash</b> ({curr} valyutasida)\n\n"
            f"Tayyor oralig'ini tanlang yoki <b>«✏️ Narxni qo'lda kiritish»</b> tugmasini bosing:"
        )
    else:
        text = (
            f"💰 <b>Настройка диапазона цены</b> (в {curr})\n\n"
            f"Выберите готовый диапазон или нажмите <b>«✏️ Ввести цену вручную»</b>:"
        )
    try:
        await callback.message.edit_text(text, reply_markup=get_price_keyboard(curr, lang=lang), parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()

@router.callback_query(F.data.startswith("price_preset_"))
async def apply_price_preset(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)
    if not await is_user_authorized(user_id):
        return

    preset_name = callback.data.replace("price_preset_", "")
    if preset_name == "all":
        min_p, max_p = None, None
    else:
        parts = preset_name.split("_")
        min_p = float(parts[0]) if parts[0] != "0" or len(parts) > 1 and parts[1] != "0" else None
        if parts[0] == "0":
            min_p = 0.0
        max_p = float(parts[1]) if len(parts) > 1 and parts[1] != "0" else None

    await update_user_filters(user_id, min_price=min_p, max_price=max_p)
    filters = await get_user_filters(user_id)
    text = format_filter_summary(filters, lang=lang)
    try:
        await callback.message.edit_text(text, reply_markup=get_filter_menu_keyboard(filters, lang=lang), parse_mode="HTML")
    except Exception:
        pass
    alert = "Narx oralig'i yangilandi!" if lang == "uz" else "Диапазон цены обновлён!"
    await callback.answer(alert)

@router.callback_query(F.data == "price_custom")
async def ask_custom_price(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)
    if not await is_user_authorized(user_id):
        return

    filters = await get_user_filters(user_id)
    curr = filters.get("price_currency", "USD")
    await state.set_state(FilterCustomStates.waiting_for_custom_price)
    
    if lang == "uz":
        text = (
            f"✏️ <b>Istalgan narx oralig'ini {curr} valyutasida kiriting:</b>\n\n"
            f"Kiritish namunalari:\n"
            f"• <code>5000-50000</code> (5 000 dan 50 000 gacha)\n"
            f"• <code>10000</code> (10 000 gacha)\n"
            f"• <code>8000 dan</code> (8 000 dan boshlab)\n\n"
            f"<i>Bekor qilish uchun «❌ Bekor qilish» tugmasini bosing.</i>"
        )
    else:
        text = (
            f"✏️ <b>Введите желаемый диапазон цены в {curr}:</b>\n\n"
            f"Примеры ввода:\n"
            f"• <code>5000-50000</code> (от 5 000 до 50 000)\n"
            f"• <code>10000</code> (до 10 000)\n"
            f"• <code>от 8000</code> (от 8 000)\n\n"
            f"<i>Для отмены нажмите кнопку «❌ Отмена» ниже.</i>"
        )

    await callback.message.answer(text, reply_markup=get_cancel_reply_keyboard(lang=lang), parse_mode="HTML")
    await callback.answer()

@router.message(FilterCustomStates.waiting_for_custom_price)
async def process_custom_price(message: Message, state: FSMContext):
    user_id = message.from_user.id
    lang = await get_user_language(user_id)
    raw = message.text.strip() if message.text else ""

    if raw in ("❌ Отмена", "❌ Bekor qilish") or raw.startswith("/"):
        await state.clear()
        filters = await get_user_filters(user_id)
        is_mon = bool(filters.get("is_monitoring_active", 1))
        user_is_adm = await is_admin(user_id)
        await message.answer(t("cancelled", lang), reply_markup=get_main_keyboard(is_admin=user_is_adm, is_monitoring=is_mon, lang=lang))
        return

    min_p, max_p = normalize_range_input(raw)

    if min_p is None and max_p is None:
        err_msg = (
            "⚠️ Raqamlarni aniqlab bo'lmadi.\nIltimos, narx oralig'ini kiriting (masalan <code>5000-50000</code>):" 
            if lang == "uz" else
            "⚠️ Не удалось распознать числа.\nПожалуйста, введите диапазон (например <code>5000-50000</code> или <code>20000</code>):"
        )
        await message.answer(err_msg, reply_markup=get_cancel_reply_keyboard(lang=lang), parse_mode="HTML")
        return

    await update_user_filters(user_id, min_price=min_p, max_price=max_p)
    await state.clear()

    filters = await get_user_filters(user_id)
    is_mon = bool(filters.get("is_monitoring_active", 1))
    user_is_adm = await is_admin(user_id)
    saved_text = "✅ <b>Narx muvaffaqiyatli saqlandi!</b>\n\n" if lang == "uz" else "✅ <b>Цена успешно сохранена!</b>\n\n"
    await message.answer(
        saved_text + format_filter_summary(filters, lang=lang),
        reply_markup=get_main_keyboard(is_admin=user_is_adm, is_monitoring=is_mon, lang=lang),
        parse_mode="HTML"
    )

# ==================== MILEAGE FILTERS ====================

@router.callback_query(F.data == "filter_mileage")
async def open_mileage_filter(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)
    if not await is_user_authorized(user_id):
        return

    if lang == "uz":
        text = (
            "🛣 <b>Yurgan masofani sozlash (km)</b>\n\n"
            "Tayyor variantni tanlang yoki <b>«✏️ Masofani qo'lda kiritish»</b> tugmasini bosing:"
        )
    else:
        text = (
            "🛣 <b>Настройка диапазона пробега (в км)</b>\n\n"
            "Выберите готовый вариант или нажмите <b>«✏️ Ввести пробег вручную»</b>:"
        )
    try:
        await callback.message.edit_text(text, reply_markup=get_mileage_keyboard(lang=lang), parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()

@router.callback_query(F.data.startswith("mileage_preset_"))
async def apply_mileage_preset(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)
    if not await is_user_authorized(user_id):
        return

    preset_name = callback.data.replace("mileage_preset_", "")
    if preset_name == "all":
        min_m, max_m = None, None
    elif preset_name == "0_0":
        min_m, max_m = 0, 0
    else:
        parts = preset_name.split("_")
        min_m = int(parts[0]) if parts[0] != "0" else 0
        max_m = int(parts[1]) if len(parts) > 1 and parts[1] != "0" else None

    await update_user_filters(user_id, min_mileage=min_m, max_mileage=max_m)
    filters = await get_user_filters(user_id)
    text = format_filter_summary(filters, lang=lang)
    try:
        await callback.message.edit_text(text, reply_markup=get_filter_menu_keyboard(filters, lang=lang), parse_mode="HTML")
    except Exception:
        pass
    alert = "Masofa yangilandi!" if lang == "uz" else "Диапазон пробега обновлён!"
    await callback.answer(alert)

@router.callback_query(F.data == "mileage_custom")
async def ask_custom_mileage(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)
    if not await is_user_authorized(user_id):
        return

    await state.set_state(FilterCustomStates.waiting_for_custom_mileage)
    if lang == "uz":
        text = (
            "✏️ <b>Istalgan masofani kilometrda kiriting:</b>\n\n"
            "Kiritish namunalari:\n"
            "• <code>0-50000</code> (0 dan 50 000 km gacha)\n"
            "• <code>70000</code> (70 000 km gacha)\n"
            "• <code>20000 dan</code> (20 000 km dan boshlab)\n\n"
            "<i>Bekor qilish uchun «❌ Bekor qilish» tugmasini bosing.</i>"
        )
    else:
        text = (
            "✏️ <b>Введите желаемый пробег в километрах:</b>\n\n"
            "Примеры ввода:\n"
            "• <code>0-50000</code> (от 0 до 50 000 км)\n"
            "• <code>70000</code> (до 70 000 км)\n"
            "• <code>от 20000</code> (от 20 000 км)\n\n"
            "<i>Для отмены нажмите кнопку «❌ Отмена» ниже.</i>"
        )

    await callback.message.answer(text, reply_markup=get_cancel_reply_keyboard(lang=lang), parse_mode="HTML")
    await callback.answer()

@router.message(FilterCustomStates.waiting_for_custom_mileage)
async def process_custom_mileage(message: Message, state: FSMContext):
    user_id = message.from_user.id
    lang = await get_user_language(user_id)
    raw = message.text.strip() if message.text else ""

    if raw in ("❌ Отмена", "❌ Bekor qilish") or raw.startswith("/"):
        await state.clear()
        filters = await get_user_filters(user_id)
        is_mon = bool(filters.get("is_monitoring_active", 1))
        user_is_adm = await is_admin(user_id)
        await message.answer(t("cancelled", lang), reply_markup=get_main_keyboard(is_admin=user_is_adm, is_monitoring=is_mon, lang=lang))
        return

    min_m_f, max_m_f = normalize_range_input(raw)
    min_m = int(min_m_f) if min_m_f is not None else None
    max_m = int(max_m_f) if max_m_f is not None else None

    if min_m is None and max_m is None:
        err_msg = (
            "⚠️ Raqamni aniqlab bo'lmadi.\nIltimos, masofani kiriting (masalan <code>0-60000</code> yoki <code>50000</code>):" 
            if lang == "uz" else
            "⚠️ Не удалось распознать число.\nПожалуйста, введите пробег вида <code>0-60000</code> или <code>50000</code>:"
        )
        await message.answer(err_msg, reply_markup=get_cancel_reply_keyboard(lang=lang), parse_mode="HTML")
        return

    await update_user_filters(user_id, min_mileage=min_m, max_mileage=max_m)
    await state.clear()

    filters = await get_user_filters(user_id)
    is_mon = bool(filters.get("is_monitoring_active", 1))
    user_is_adm = await is_admin(user_id)
    saved_text = "✅ <b>Masofa muvaffaqiyatli saqlandi!</b>\n\n" if lang == "uz" else "✅ <b>Пробег успешно сохранён!</b>\n\n"
    await message.answer(
        saved_text + format_filter_summary(filters, lang=lang),
        reply_markup=get_main_keyboard(is_admin=user_is_adm, is_monitoring=is_mon, lang=lang),
        parse_mode="HTML"
    )

# ==================== FUEL FILTERS ====================

@router.callback_query(F.data == "filter_fuel")
async def open_fuel_filter(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)
    if not await is_user_authorized(user_id):
        return

    filters = await get_user_filters(user_id)
    selected = filters.get("fuel_types", [])
    if lang == "uz":
        text = (
            "⛽️ <b>Yoqilg'i turini tanlash:</b>\n\n"
            "Qidiruvda yoqish (✅) yoki o'chirish (❌) uchun kerakli yoqilg'i turini bosing."
        )
    else:
        text = (
            "⛽️ <b>Выбор вида топлива:</b>\n\n"
            "Нажмите на нужный вид топлива, чтобы включить (✅) или отключить (❌) его в поиске."
        )
    try:
        await callback.message.edit_text(text, reply_markup=get_fuel_keyboard(selected, lang=lang), parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()

@router.callback_query(F.data.startswith("toggle_fuel_"))
async def toggle_fuel_item(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)
    if not await is_user_authorized(user_id):
        return

    fuel_name = callback.data.replace("toggle_fuel_", "")
    filters = await get_user_filters(user_id)
    selected = set(filters.get("fuel_types", []))

    if fuel_name in selected:
        selected.remove(fuel_name)
    else:
        selected.add(fuel_name)

    await update_user_filters(user_id, fuel_types=list(selected))
    if lang == "uz":
        text = (
            "⛽️ <b>Yoqilg'i turini tanlash:</b>\n\n"
            "Qidiruvda yoqish (✅) yoki o'chirish (❌) uchun kerakli yoqilg'i turini bosing."
        )
    else:
        text = (
            "⛽️ <b>Выбор вида топлива:</b>\n\n"
            "Нажмите на нужный вид топлива, чтобы включить (✅) или отключить (❌) его в поиске."
        )
    try:
        await callback.message.edit_text(text, reply_markup=get_fuel_keyboard(list(selected), lang=lang), parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()

@router.callback_query(F.data == "fuel_select_all")
async def fuel_select_all(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)
    if not await is_user_authorized(user_id):
        return

    await update_user_filters(user_id, fuel_types=ALL_FUEL_TYPES)
    try:
        await callback.message.edit_reply_markup(reply_markup=get_fuel_keyboard(ALL_FUEL_TYPES, lang=lang))
    except Exception:
        pass
    alert = "Barcha yoqilg'i turlari tanlandi!" if lang == "uz" else "Выбраны все виды топлива!"
    await callback.answer(alert)

@router.callback_query(F.data == "fuel_clear_all")
async def fuel_clear_all(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)
    if not await is_user_authorized(user_id):
        return

    await update_user_filters(user_id, fuel_types=[])
    try:
        await callback.message.edit_reply_markup(reply_markup=get_fuel_keyboard([], lang=lang))
    except Exception:
        pass
    alert = "Tanlov tozalandi!" if lang == "uz" else "Выбор очищен!"
    await callback.answer(alert)
