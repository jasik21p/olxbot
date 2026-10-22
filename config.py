import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# Load .env file
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "8626571387:AAHmbW5s0dGTs8WmA0rd2N3U1xAd7ax9CtY").strip()
SUPER_ADMIN_ID = int(os.getenv("ADMIN_ID", "5905608906"))
ADMIN_ID = SUPER_ADMIN_ID  # Backward compatibility
DEFAULT_PASSWORD = os.getenv("DEFAULT_PASSWORD", "olx2026").strip()

POLL_INTERVAL = float(os.getenv("POLL_INTERVAL", "1.0"))
DB_PATH = BASE_DIR / os.getenv("DB_PATH", "olx_bot.db")
LOCK_FILE_PATH = BASE_DIR / "bot.lock"

# OLX Configuration
OLX_CATEGORY_ID = 108  # Легковые автомобили
OLX_BASE_URL = "https://www.olx.uz"
OLX_API_URL = "https://www.olx.uz/api/v1/offers/?offset=0&limit=30&category_id=108&sort_by=created_at:desc"
OLX_PHONE_API_URL = "https://www.olx.uz/api/v1/offers/{offer_id}/phones/"

# Fuel types available on OLX Uzbekistan
ALL_FUEL_TYPES = [
    "Бензин",
    "Газ/Бензин",
    "Дизель",
    "Электро",
    "Гибрид"
]

# Regions of Uzbekistan
UZBEKISTAN_REGIONS = [
    "г. Ташкент",
    "Ташкентская область",
    "Самаркандская область",
    "Ферганская область",
    "Андижанская область",
    "Наманганская область",
    "Бухарская область",
    "Кашкадарьинская область",
    "Сурхандарьинская область",
    "Хорезмская область",
    "Навоийская область",
    "Джизакская область",
    "Сырдарьинская область",
    "Республика Каракалпакстан"
]

MAX_PHOTOS = 8  # Send up to 8 photos in album
