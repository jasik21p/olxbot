import re
import html
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
import aiohttp
from config import OLX_PHONE_API_URL, MAX_PHOTOS

logger = logging.getLogger(__name__)

# Regex for finding Uzbek phone numbers in text (e.g. +998901234567, 90 123 45 67, etc.)
PHONE_REGEX = re.compile(
    r'(?:\+?998[\s.-]?)?(?:\(?\d{2}\)?[\s.-]?)?\d{3}[\s.-]?\d{2}[\s.-]?\d{2}'
)

def clean_html_text(raw_text: str) -> str:
    """Removes HTML tags, decodes HTML entities, and formats whitespace."""
    if not raw_text:
        return ""
    text = re.sub(r'<br\s*/?>', '\n', raw_text, flags=re.IGNORECASE)
    text = re.sub(r'</p>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = html.unescape(text)
    text = re.sub(r'\n\s*\n+', '\n\n', text)
    return text.strip()

def parse_iso_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    """Parses ISO timestamp string into timezone-aware datetime."""
    if not dt_str:
        return None
    try:
        # e.g. "2026-10-22T23:30:03+05:00"
        return datetime.fromisoformat(dt_str)
    except Exception:
        return None

@dataclass
class CarOffer:
    id: int
    title: str
    url: str
    created_time: str
    created_dt: Optional[datetime]
    last_refresh_time: str
    is_top: bool
    description: str
    photos: List[str]
    price_usd: float
    price_uzs: float
    price_display: str
    mileage: Optional[int]
    mileage_display: str
    fuel_type: str
    year: str
    model: str
    region: str
    city: str
    district: str
    location: str
    seller_name: str
    phones: List[str] = field(default_factory=list)

    def matches_filters(self, user: Dict[str, Any]) -> bool:
        """Checks whether this ad matches the user's configured filters."""
        # 1. Price check
        currency = user.get("price_currency", "USD")
        price_to_check = self.price_usd if currency == "USD" else self.price_uzs
        min_p = user.get("min_price")
        max_p = user.get("max_price")

        if min_p is not None and price_to_check < min_p:
            return False
        if max_p is not None and price_to_check > max_p:
            return False

        # 2. Mileage check
        min_m = user.get("min_mileage")
        max_m = user.get("max_mileage")
        if self.mileage is not None:
            if min_m is not None and self.mileage < min_m:
                return False
            if max_m is not None and self.mileage > max_m:
                return False
        elif min_m is not None and min_m > 0:
            return False

        # 3. Fuel type check
        allowed_fuels = user.get("fuel_types", [])
        if allowed_fuels and len(allowed_fuels) > 0:
            if self.fuel_type:
                matched = any(
                    f.lower() in self.fuel_type.lower() or self.fuel_type.lower() in f.lower() 
                    for f in allowed_fuels
                )
                if not matched:
                    return False

        # 4. Region check
        user_region = user.get("region")
        if user_region and user_region != "Все регионы":
            clean_user_reg = user_region.lower().replace(" область", "").replace(" обл.", "").replace("г. ", "").strip()
            loc_combined = f"{self.region} {self.city} {self.location}".lower()
            if clean_user_reg not in loc_combined:
                return False

        # 5. City check
        user_city = user.get("city")
        if user_city and user_city.strip():
            clean_user_city = user_city.lower().strip()
            city_combined = f"{self.city} {self.district} {self.location}".lower()
            if clean_user_city not in city_combined:
                return False

        return True

def parse_offer_dict(item: Dict[str, Any]) -> Optional[CarOffer]:
    """Parses raw offer dictionary from OLX API into a CarOffer dataclass."""
    try:
        ad_id = int(item.get("id"))
        title = item.get("title", "").strip()
        url = item.get("url", "")
        raw_created = item.get("created_time") or ""
        created_dt = parse_iso_datetime(raw_created)
        last_refresh_time = item.get("last_refresh_time") or ""

        # Check if TOP / Promoted ad
        promotion = item.get("promotion", {}) or {}
        is_top = bool(promotion.get("top_ad", False) or item.get("is_promoted", False))

        # Description
        raw_desc = item.get("description", "")
        description = clean_html_text(raw_desc)

        # Photos
        photos = []
        for p in item.get("photos", []):
            link = p.get("link", "")
            if link:
                photo_url = link.replace("{width}", "1000").replace("{height}", "1000")
                photos.append(photo_url)
            if len(photos) >= MAX_PHOTOS:
                break

        # Location details
        loc_data = item.get("location", {}) or {}
        region_name = loc_data.get("region", {}).get("name", "") if isinstance(loc_data.get("region"), dict) else ""
        city_name = loc_data.get("city", {}).get("name", "") if isinstance(loc_data.get("city"), dict) else ""
        district_name = loc_data.get("district", {}).get("name", "") if isinstance(loc_data.get("district"), dict) else ""

        location_parts = [p for p in [city_name, district_name, region_name] if p]
        location = ", ".join(location_parts) or "Узбекистан"

        # Seller
        seller_name = item.get("user", {}).get("name") or item.get("contact", {}).get("name") or "Продавец"

        # Parameters
        params = item.get("params", [])
        param_map = {p.get("key"): p for p in params if isinstance(p, dict)}

        # 1. Price
        price_param = param_map.get("price", {}).get("value", {})
        price_val = price_param.get("value") or 0
        price_curr = price_param.get("currency") or "USD"
        converted_val = price_param.get("converted_value")
        raw_price_label = price_param.get("label")

        exchange_rate = 12800.0
        if price_curr == "UYE" and converted_val and price_val:
            exchange_rate = float(converted_val) / float(price_val)
        elif price_curr == "UZS" and converted_val and price_val:
            exchange_rate = float(price_val) / float(converted_val)

        if price_curr in ("UYE", "USD"):
            price_usd = float(price_val)
            price_uzs = float(converted_val) if converted_val else price_usd * exchange_rate
            price_display = f"${price_usd:,.0f} (~{price_uzs:,.0f} сум)".replace(",", " ")
        else:
            price_uzs = float(price_val)
            price_usd = float(converted_val) if converted_val else price_uzs / exchange_rate
            price_display = f"{price_uzs:,.0f} сум (~${price_usd:,.0f})".replace(",", " ")

        if raw_price_label and raw_price_label not in price_display:
            price_display += f" [{raw_price_label}]"

        # 2. Mileage
        mileage_param = param_map.get("motor_mileage", {}).get("value", {})
        mileage_key = mileage_param.get("key")
        mileage = None
        mileage_display = "Не указан"
        if mileage_key is not None:
            try:
                mileage = int(str(mileage_key).replace(" ", "").replace("км", ""))
                mileage_display = f"{mileage:,.0f} км".replace(",", " ")
            except (ValueError, TypeError):
                mileage_display = str(mileage_param.get("label", "Не указан"))

        # 3. Fuel type
        fuel_param = param_map.get("fuel_type", {}).get("value", {})
        fuel_type = fuel_param.get("label") or "Не указано"

        # 4. Year & Model
        year_param = param_map.get("motor_year", {}).get("value", {})
        year = str(year_param.get("label", "")).strip()

        model_param = param_map.get("model", {}).get("value", {})
        model = str(model_param.get("label", "")).strip()

        return CarOffer(
            id=ad_id,
            title=title,
            url=url,
            created_time=str(raw_created),
            created_dt=created_dt,
            last_refresh_time=str(last_refresh_time),
            is_top=is_top,
            description=description,
            photos=photos,
            price_usd=price_usd,
            price_uzs=price_uzs,
            price_display=price_display,
            mileage=mileage,
            mileage_display=mileage_display,
            fuel_type=fuel_type,
            year=year,
            model=model,
            region=region_name,
            city=city_name,
            district=district_name,
            location=location,
            seller_name=seller_name,
            phones=[]
        )
    except Exception as e:
        logger.error(f"Error parsing offer {item.get('id')}: {e}", exc_info=True)
        return None

async def fetch_offer_phones(session: aiohttp.ClientSession, offer_id: int, description: str) -> List[str]:
    """Fetches phone numbers via OLX API endpoint with regex fallback on description."""
    phones = []
    url = OLX_PHONE_API_URL.format(offer_id=offer_id)
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=3)) as resp:
            if resp.status == 200:
                data = await resp.json()
                fetched = data.get("data", {}).get("phones", [])
                for p in fetched:
                    p_clean = str(p).strip()
                    if p_clean and p_clean not in phones:
                        phones.append(p_clean)
    except Exception as e:
        logger.debug(f"Could not fetch phone from API for ad {offer_id}: {e}")

    # Fallback to description regex
    if not phones and description:
        matches = PHONE_REGEX.findall(description)
        for m in matches:
            cleaned = re.sub(r'[\s.-]', '', m)
            if 7 <= len(cleaned) <= 12 and cleaned not in phones:
                phones.append(m.strip())

    return phones
