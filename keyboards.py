from typing import List, Dict, Any, Optional
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from config import ALL_FUEL_TYPES, UZBEKISTAN_REGIONS, SUPER_ADMIN_ID
from locales import t

def get_language_keyboard(prefix: str = "set_lang_") -> InlineKeyboardMarkup:
    """Inline keyboard for selecting language."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇷🇺 Русский", callback_data=f"{prefix}ru"),
            InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data=f"{prefix}uz")
        ]
    ])

def get_main_keyboard(is_admin: bool = False, is_monitoring: bool = True, lang: str = "ru") -> ReplyKeyboardMarkup:
    """Creates persistent bottom keyboard for navigation in user's language."""
    mon_text = t("btn_pause", lang) if is_monitoring else t("btn_resume", lang)
    keyboard = [
        [
            KeyboardButton(text=t("btn_filters", lang)), 
            KeyboardButton(text=t("btn_status", lang))
        ],
        [
            KeyboardButton(text=mon_text),
            KeyboardButton(text=t("btn_lang", lang))
        ]
    ]
    if is_admin:
        keyboard.append([
            KeyboardButton(text=t("btn_change_pw", lang)),
            KeyboardButton(text=t("btn_admin", lang))
        ])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_cancel_reply_keyboard(lang: str = "ru") -> ReplyKeyboardMarkup:
    """Simple cancel button for text inputs."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t("btn_cancel", lang))]],
        resize_keyboard=True
    )

def format_filter_summary(filters: Dict[str, Any], lang: str = "ru") -> str:
    """Creates a readable summary text of the user's active filters."""
    curr = filters.get("price_currency", "USD")
    curr_symbol = "$" if curr == "USD" else ("so'm" if lang == "uz" else "сум")

    # Price
    min_p = filters.get("min_price")
    max_p = filters.get("max_price")
    if lang == "uz":
        if min_p is not None and max_p is not None:
            price_str = f"{min_p:,.0f} dan {max_p:,.0f} {curr_symbol} gacha".replace(",", " ")
        elif min_p is not None:
            price_str = f"{min_p:,.0f} {curr_symbol} dan".replace(",", " ")
        elif max_p is not None:
            price_str = f"{max_p:,.0f} {curr_symbol} gacha".replace(",", " ")
        else:
            price_str = "Istalgan"
    else:
        if min_p is not None and max_p is not None:
            price_str = f"от {min_p:,.0f} до {max_p:,.0f} {curr_symbol}".replace(",", " ")
        elif min_p is not None:
            price_str = f"от {min_p:,.0f} {curr_symbol}".replace(",", " ")
        elif max_p is not None:
            price_str = f"до {max_p:,.0f} {curr_symbol}".replace(",", " ")
        else:
            price_str = "Любая"

    # Mileage
    min_m = filters.get("min_mileage")
    max_m = filters.get("max_mileage")
    if lang == "uz":
        if min_m is not None and max_m is not None:
            mileage_str = f"{min_m:,.0f} dan {max_m:,.0f} km gacha".replace(",", " ")
        elif min_m is not None:
            mileage_str = f"{min_m:,.0f} km dan".replace(",", " ")
        elif max_m is not None:
            mileage_str = f"{max_m:,.0f} km gacha".replace(",", " ")
        else:
            mileage_str = "Istalgan"
    else:
        if min_m is not None and max_m is not None:
            mileage_str = f"от {min_m:,.0f} до {max_m:,.0f} км".replace(",", " ")
        elif min_m is not None:
            mileage_str = f"от {min_m:,.0f} км".replace(",", " ")
        elif max_m is not None:
            mileage_str = f"до {max_m:,.0f} км".replace(",", " ")
        else:
            mileage_str = "Любой"

    # Fuel
    fuels = filters.get("fuel_types", [])
    if not fuels or len(fuels) == len(ALL_FUEL_TYPES):
        fuel_str = "Barcha yoqilg'i turlari" if lang == "uz" else "Все виды топлива"
    else:
        fuel_str = ", ".join(fuels)

    # Location
    region = filters.get("region")
    city = filters.get("city")
    if region and city:
        loc_str = f"{region} ({city})"
    elif region:
        loc_str = region
    elif city:
        loc_str = f"Shahar: {city}" if lang == "uz" else f"Город: {city}"
    else:
        loc_str = "Butun O'zbekiston" if lang == "uz" else "Вся страна (Все регионы)"

    if lang == "uz":
        monitoring_status = "🟢 Faol" if filters.get("is_monitoring_active", 1) else "🔴 To'xtatilgan"
        return (
            f"📋 <b>Filtrlarning joriy sozlamalari:</b>\n\n"
            f"📡 <b>Monitoring:</b> {monitoring_status}\n"
            f"📍 <b>Hudud:</b> {loc_str}\n"
            f"💰 <b>Narx oralig'i:</b> {price_str} (Valyuta: {curr})\n"
            f"🛣 <b>Yurgan masofa:</b> {mileage_str}\n"
            f"⛽️ <b>Yoqilg'i turi:</b> {fuel_str}\n\n"
            f"<i>Kerakli parametrni o'zgartirish uchun quyidagi tugmani bosing:</i>"
        )
    else:
        monitoring_status = "🟢 Активен" if filters.get("is_monitoring_active", 1) else "🔴 Приостановлен"
        return (
            f"📋 <b>Текущие настройки фильтров:</b>\n\n"
            f"📡 <b>Мониторинг:</b> {monitoring_status}\n"
            f"📍 <b>Локация:</b> {loc_str}\n"
            f"💰 <b>Диапазон цены:</b> {price_str} (Валюта: {curr})\n"
            f"🛣 <b>Диапазон пробега:</b> {mileage_str}\n"
            f"⛽️ <b>Вид топлива:</b> {fuel_str}\n\n"
            f"<i>Нажмите кнопку ниже, чтобы изменить нужный параметр:</i>"
        )

def get_filter_menu_keyboard(filters: Dict[str, Any], lang: str = "ru") -> InlineKeyboardMarkup:
    """Main filter management inline keyboard."""
    curr = filters.get("price_currency", "USD")
    curr_label = "USD ($)" if curr == "USD" else ("UZS (so'm)" if lang == "uz" else "UZS (сум)")

    if lang == "uz":
        buttons = [
            [InlineKeyboardButton(text="📍 Hudud va shahar", callback_data="filter_location")],
            [InlineKeyboardButton(text="💰 Narxni sozlash", callback_data="filter_price")],
            [InlineKeyboardButton(text="🛣 Masofani sozlash", callback_data="filter_mileage")],
            [InlineKeyboardButton(text="⛽️ Yoqilg'i turi", callback_data="filter_fuel")],
            [InlineKeyboardButton(text=f"💱 Valyuta: {curr_label}", callback_data="toggle_currency")],
            [InlineKeyboardButton(text="🔄 Barcha filtrlarni tozalash", callback_data="reset_filters")],
            [InlineKeyboardButton(text="⬅️ Menyuni yopish", callback_data="close_menu")]
        ]
    else:
        buttons = [
            [InlineKeyboardButton(text="📍 Регион и город", callback_data="filter_location")],
            [InlineKeyboardButton(text="💰 Настроить цену", callback_data="filter_price")],
            [InlineKeyboardButton(text="🛣 Настроить пробег", callback_data="filter_mileage")],
            [InlineKeyboardButton(text="⛽️ Вид топлива", callback_data="filter_fuel")],
            [InlineKeyboardButton(text=f"💱 Валюта цены: {curr_label}", callback_data="toggle_currency")],
            [InlineKeyboardButton(text="🔄 Сбросить все фильтры", callback_data="reset_filters")],
            [InlineKeyboardButton(text="⬅️ Закрыть меню", callback_data="close_menu")]
        ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_region_keyboard(current_region: Optional[str], lang: str = "ru") -> InlineKeyboardMarkup:
    """Keyboard for selecting region or entering city."""
    rows = []
    all_label = "🇺🇿 Butun O'zbekiston" if lang == "uz" else "🇺🇿 Вся страна (Все регионы)"
    all_icon = "✅ " if not current_region or current_region in ("Все регионы", "Butun O'zbekiston") else ""
    rows.append([InlineKeyboardButton(text=f"{all_icon}{all_label}", callback_data="region_all")])

    temp_row = []
    for reg in UZBEKISTAN_REGIONS:
        is_cur = (current_region == reg)
        icon = "✅ " if is_cur else ""
        short_name = reg.replace(" область", " обл.").replace("Республика ", "Респ. ")
        btn = InlineKeyboardButton(text=f"{icon}{short_name}", callback_data=f"set_region_{reg}")
        temp_row.append(btn)
        if len(temp_row) == 2:
            rows.append(temp_row)
            temp_row = []
    if temp_row:
        rows.append(temp_row)

    city_btn_label = "✏️ Aniq shahar/tumanni kiritish" if lang == "uz" else "✏️ Ввести конкретный город/район"
    back_btn_label = "⬅️ Filtrlarga qaytish" if lang == "uz" else "⬅️ Назад к фильтрам"

    rows.append([InlineKeyboardButton(text=city_btn_label, callback_data="city_custom")])
    rows.append([InlineKeyboardButton(text=back_btn_label, callback_data="back_to_filters")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def get_price_keyboard(currency: str, lang: str = "ru") -> InlineKeyboardMarkup:
    """Preset price buttons + custom input option."""
    if currency == "USD":
        presets = [
            ("Istalgan narx" if lang == "uz" else "Любая цена", "price_preset_all"),
            ("$5,000 gacha" if lang == "uz" else "До $5,000", "price_preset_0_5000"),
            ("$5,000 - $10,000", "price_preset_5000_10000"),
            ("$10,000 - $15,000", "price_preset_10000_15000"),
            ("$15,000 - $25,000", "price_preset_15000_25000"),
            ("$25,000 dan" if lang == "uz" else "От $25,000", "price_preset_25000_0")
        ]
    else:
        presets = [
            ("Istalgan narx" if lang == "uz" else "Любая цена", "price_preset_all"),
            ("50 mln gacha" if lang == "uz" else "До 50 млн", "price_preset_0_50000000"),
            ("50 - 100 mln", "price_preset_50000000_100000000"),
            ("100 - 180 mln", "price_preset_100000000_180000000"),
            ("180 - 300 mln", "price_preset_180000000_300000000"),
            ("300 mln dan" if lang == "uz" else "От 300 млн", "price_preset_300000000_0")
        ]

    rows = []
    for i in range(0, len(presets), 2):
        row = [InlineKeyboardButton(text=presets[i][0], callback_data=presets[i][1])]
        if i + 1 < len(presets):
            row.append(InlineKeyboardButton(text=presets[i+1][0], callback_data=presets[i+1][1]))
        rows.append(row)

    custom_label = "✏️ Narxni qo'lda kiritish" if lang == "uz" else "✏️ Ввести цену вручную"
    back_label = "⬅️ Filtrlarga qaytish" if lang == "uz" else "⬅️ Назад к фильтрам"

    rows.append([InlineKeyboardButton(text=custom_label, callback_data="price_custom")])
    rows.append([InlineKeyboardButton(text=back_label, callback_data="back_to_filters")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def get_mileage_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Preset mileage buttons + custom input."""
    presets = [
        ("Istalgan masofa" if lang == "uz" else "Любой пробег", "mileage_preset_all"),
        ("Yangi (0 km)" if lang == "uz" else "Новые (0 км)", "mileage_preset_0_0"),
        ("30 000 km gacha" if lang == "uz" else "До 30 000 км", "mileage_preset_0_30000"),
        ("70 000 km gacha" if lang == "uz" else "До 70 000 км", "mileage_preset_0_70000"),
        ("120 000 km gacha" if lang == "uz" else "До 120 000 км", "mileage_preset_0_120000"),
        ("200 000 km gacha" if lang == "uz" else "До 200 000 км", "mileage_preset_0_200000")
    ]
    rows = []
    for i in range(0, len(presets), 2):
        row = [InlineKeyboardButton(text=presets[i][0], callback_data=presets[i][1])]
        if i + 1 < len(presets):
            row.append(InlineKeyboardButton(text=presets[i+1][0], callback_data=presets[i+1][1]))
        rows.append(row)

    custom_label = "✏️ Masofani qo'lda kiritish" if lang == "uz" else "✏️ Ввести пробег вручную"
    back_label = "⬅️ Filtrlarga qaytish" if lang == "uz" else "⬅️ Назад к фильтрам"

    rows.append([InlineKeyboardButton(text=custom_label, callback_data="mileage_custom")])
    rows.append([InlineKeyboardButton(text=back_label, callback_data="back_to_filters")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def get_fuel_keyboard(selected_fuels: List[str], lang: str = "ru") -> InlineKeyboardMarkup:
    """Interactive toggle buttons for each fuel type."""
    rows = []
    for fuel in ALL_FUEL_TYPES:
        is_selected = fuel in selected_fuels
        icon = "✅" if is_selected else "❌"
        rows.append([
            InlineKeyboardButton(
                text=f"{icon} {fuel}", 
                callback_data=f"toggle_fuel_{fuel}"
            )
        ])

    all_btn = "✅ Barchasini tanlash" if lang == "uz" else "✅ Выбрать все"
    clear_btn = "❌ Tozalash" if lang == "uz" else "❌ Снять все"
    back_btn = "⬅️ Filtrlarga qaytish" if lang == "uz" else "⬅️ Назад к фильтрам"

    rows.append([
        InlineKeyboardButton(text=all_btn, callback_data="fuel_select_all"),
        InlineKeyboardButton(text=clear_btn, callback_data="fuel_clear_all")
    ])
    rows.append([InlineKeyboardButton(text=back_btn, callback_data="back_to_filters")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def get_ad_inline_keyboard(url: str, lang: str = "ru") -> InlineKeyboardMarkup:
    """Action buttons attached to listings."""
    label = t("ad_open_btn", lang)
    buttons = [
        [InlineKeyboardButton(text=label, url=url)]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ==================== ADMIN KEYBOARDS ====================

def get_admin_panel_keyboard(is_super: bool = False, current_interval: float = 1.0, lang: str = "ru") -> InlineKeyboardMarkup:
    """Admin quick management actions."""
    interval_label = f"⏱ Частота обновлений: {current_interval:.1f}с" if lang != "uz" else f"⏱ Yangilanish tezligi: {current_interval:.1f}s"
    pw_label = "🔑 Сменить пароль бота" if lang != "uz" else "🔑 Bot parolini o'zgartirish"
    ping_label = "📡 Проверить пинг (OLX и Сервер)" if lang != "uz" else "📡 Tarmoq pingi (OLX va Server)"
    admins_label = "👥 Управление администраторами" if lang != "uz" else "👥 Administratorlarni boshqarish"
    refresh_label = "📊 Обновить статистику" if lang != "uz" else "📊 Statistikani yangilash"
    close_label = "❌ Закрыть" if lang != "uz" else "❌ Yopish"

    buttons = [
        [InlineKeyboardButton(text=interval_label, callback_data="admin_open_interval")],
        [InlineKeyboardButton(text=pw_label, callback_data="admin_change_pw")],
        [InlineKeyboardButton(text=ping_label, callback_data="admin_check_ping")]
    ]
    if is_super:
        buttons.append([InlineKeyboardButton(text=admins_label, callback_data="admin_manage_admins")])

    buttons.append([
        InlineKeyboardButton(text=refresh_label, callback_data="admin_refresh_stats"),
        InlineKeyboardButton(text=close_label, callback_data="close_admin")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_ping_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    refresh_btn = "🔄 Yangilash" if lang == "uz" else "🔄 Повторить замер"
    back_btn = "⬅️ Admin paneli" if lang == "uz" else "⬅️ В админ-панель"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=refresh_btn, callback_data="admin_check_ping")],
        [InlineKeyboardButton(text=back_btn, callback_data="admin_panel_main")]
    ])

def get_poll_interval_keyboard(current_interval: float) -> InlineKeyboardMarkup:
    """Presets for update frequency."""
    presets = [
        (0.5, "0.5 сек"),
        (1.0, "1.0 сек"),
        (2.0, "2.0 сек"),
        (3.0, "3.0 сек"),
        (5.0, "5.0 сек"),
        (10.0, "10.0 сек")
    ]
    rows = []
    for i in range(0, len(presets), 2):
        row = []
        for val, label in presets[i:i+2]:
            icon = "✅ " if abs(val - current_interval) < 0.05 else ""
            row.append(InlineKeyboardButton(text=f"{icon}{label}", callback_data=f"set_interval_{val}"))
        rows.append(row)

    rows.append([InlineKeyboardButton(text="✏️ Ввести вручную (число сек)", callback_data="admin_custom_interval")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад в админ-панель", callback_data="admin_panel_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def get_admins_management_keyboard(admins: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Keyboard for super admin to manage other admins."""
    buttons = [
        [InlineKeyboardButton(text="➕ Назначить администратора", callback_data="admin_add_admin_start")]
    ]
    removable = [a for a in admins if not a.get("is_super")]
    if removable:
        buttons.append([InlineKeyboardButton(text=f"➖ Снять администратора ({len(removable)})", callback_data="admin_remove_admin_list")])

    buttons.append([InlineKeyboardButton(text="⬅️ Назад в админ-панель", callback_data="admin_panel_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_remove_admin_keyboard(admins: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """List of removable regular admins."""
    rows = []
    for a in admins:
        if a.get("is_super"):
            continue
        name = a.get("display_name", f"ID {a['user_id']}")
        rows.append([InlineKeyboardButton(text=f"❌ Снять: {name} ({a['user_id']})", callback_data=f"confirm_remove_admin_{a['user_id']}")])

    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_manage_admins")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
