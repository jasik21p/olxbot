import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional
import aiohttp
from aiogram import Bot
from aiogram.types import InputMediaPhoto
from aiogram.exceptions import TelegramAPIError

from config import (
    OLX_API_URL, 
    MAX_PHOTOS
)
from database import (
    is_ad_seen, 
    mark_ad_seen, 
    mark_multiple_ads_seen, 
    get_active_authorized_users,
    get_poll_interval
)
from olx_parser import (
    CarOffer, 
    parse_offer_dict, 
    fetch_offer_phones
)
from keyboards import get_ad_inline_keyboard
from locales import t

logger = logging.getLogger(__name__)

def build_caption(offer: CarOffer, lang: str = "ru") -> str:
    """Formats ad details into an attractive HTML caption in user's preferred language."""
    phones_str = ", ".join(offer.phones) if offer.phones else t("ad_no_contacts", lang)
    year_str = offer.year if offer.year else t("ad_not_specified", lang)

    header = f"🚗 <b>{offer.title}</b>\n\n"
    details = (
        f"{t('ad_price', lang)} {offer.price_display}\n"
        f"{t('ad_mileage', lang)} {offer.mileage_display}\n"
        f"{t('ad_fuel', lang)} {offer.fuel_type}\n"
        f"{t('ad_year', lang)} {year_str}\n"
        f"{t('ad_loc', lang)} {offer.location}\n\n"
        f"{t('ad_seller', lang)} {offer.seller_name}\n"
        f"{t('ad_contacts', lang)} <code>{phones_str}</code>\n\n"
    )
    footer = f"\n<a href='{offer.url}'>{t('ad_open_olx', lang)}</a>"

    desc_header = f"{t('ad_desc', lang)}\n"
    remaining_space = 1000 - len(header) - len(details) - len(footer) - len(desc_header) - 5
    if remaining_space > 50 and offer.description:
        desc = offer.description[:remaining_space].strip()
        if len(offer.description) > remaining_space:
            desc += "..."
        desc_block = f"{desc_header}{desc}\n"
    else:
        desc_block = ""

    caption = header + details + desc_block + footer
    return caption

async def send_ad_notification(bot: Bot, user_id: int, offer: CarOffer, lang: str = "ru") -> None:
    """Sends notification with photos and action buttons to a single user in their language."""
    caption = build_caption(offer, lang=lang)
    reply_markup = get_ad_inline_keyboard(offer.url, lang=lang)
    caption_hint = t("ad_new_notification", lang)

    try:
        if offer.photos and len(offer.photos) > 1:
            media = []
            for i, photo_url in enumerate(offer.photos[:MAX_PHOTOS]):
                if i == 0:
                    media.append(InputMediaPhoto(media=photo_url, caption=caption, parse_mode="HTML"))
                else:
                    media.append(InputMediaPhoto(media=photo_url))

            try:
                await bot.send_media_group(chat_id=user_id, media=media)
                await bot.send_message(
                    chat_id=user_id, 
                    text=caption_hint, 
                    reply_markup=reply_markup,
                    parse_mode="HTML"
                )
                return
            except TelegramAPIError as e:
                logger.warning(f"send_media_group failed for user {user_id}: {e}. Falling back to single photo.")

        if offer.photos:
            try:
                await bot.send_photo(
                    chat_id=user_id,
                    photo=offer.photos[0],
                    caption=caption,
                    reply_markup=reply_markup,
                    parse_mode="HTML"
                )
                return
            except TelegramAPIError as e:
                logger.warning(f"send_photo failed for user {user_id}: {e}. Falling back to text message.")

        await bot.send_message(
            chat_id=user_id,
            text=caption,
            reply_markup=reply_markup,
            parse_mode="HTML",
            disable_web_page_preview=False
        )

    except Exception as e:
        logger.error(f"Failed to send ad {offer.id} to user {user_id}: {e}")

class OlxMonitor:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.is_running = False
        self.start_time = datetime.now(timezone.utc)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,uz;q=0.7"
        }

    async def initialize_baseline(self, session: aiohttp.ClientSession) -> None:
        """Loads latest ads on launch and marks them seen so no past ads are sent."""
        logger.info("Initializing baseline ads from OLX...")
        try:
            async with session.get(OLX_API_URL, headers=self.headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    raw_items = data.get("data", [])
                    baseline = []
                    for item in raw_items:
                        ad_id = int(item.get("id"))
                        title = item.get("title", "")
                        created_time = str(item.get("created_time") or "")
                        baseline.append((ad_id, title, created_time))
                    if baseline:
                        await mark_multiple_ads_seen(baseline)
                        logger.info(f"Baseline established with {len(baseline)} existing ads. Start time: {self.start_time.isoformat()}")
                else:
                    logger.warning(f"Failed to get baseline ads, status: {resp.status}")
        except Exception as e:
            logger.error(f"Error fetching baseline ads: {e}")

    async def start(self) -> None:
        """Main monitoring loop running dynamically based on poll_interval from DB."""
        self.is_running = True
        self.start_time = datetime.now(timezone.utc)
        init_interval = await get_poll_interval()
        logger.info(f"Starting OLX car monitor (Initial polling interval: {init_interval}s)...")

        timeout = aiohttp.ClientTimeout(total=6)
        connector = aiohttp.TCPConnector(limit=10, ssl=False)

        async with aiohttp.ClientSession(headers=self.headers, timeout=timeout, connector=connector) as session:
            await self.initialize_baseline(session)

            consecutive_errors = 0

            while self.is_running:
                try:
                    async with session.get(OLX_API_URL) as resp:
                        if resp.status == 200:
                            consecutive_errors = 0
                            data = await resp.json()
                            raw_offers = data.get("data", [])

                            unseen_offers = []
                            for raw in raw_offers:
                                ad_id = int(raw.get("id"))
                                if not await is_ad_seen(ad_id):
                                    unseen_offers.append(raw)

                            if unseen_offers:
                                for raw in reversed(unseen_offers):
                                    offer = parse_offer_dict(raw)
                                    if not offer:
                                        continue

                                    await mark_ad_seen(offer.id, offer.title, offer.created_time)

                                    # Filter out ads created before bot started
                                    if offer.created_dt:
                                        if offer.created_dt < (self.start_time - timedelta(minutes=1)):
                                            logger.info(
                                                f"Discarding old/TOP ad {offer.id} ('{offer.title[:30]}') "
                                                f"created at {offer.created_time}"
                                            )
                                            continue
                                    else:
                                        continue

                                    logger.info(f"⚡️ New genuine car published on OLX.uz: {offer.title} (ID: {offer.id})")

                                    offer.phones = await fetch_offer_phones(session, offer.id, offer.description)

                                    active_users = await get_active_authorized_users()
                                    for user in active_users:
                                        if offer.matches_filters(user):
                                            u_lang = user.get("language", "ru")
                                            asyncio.create_task(send_ad_notification(self.bot, user["user_id"], offer, lang=u_lang))
                                            await asyncio.sleep(0.04)

                        elif resp.status == 429:
                            consecutive_errors += 1
                            backoff = min(15, consecutive_errors * 3)
                            logger.warning(f"OLX rate limit (429). Backing off for {backoff}s...")
                            await asyncio.sleep(backoff)
                        else:
                            logger.warning(f"OLX API returned status {resp.status}")

                except asyncio.CancelledError:
                    logger.info("Monitor task cancelled.")
                    break
                except Exception as e:
                    consecutive_errors += 1
                    backoff = min(10, consecutive_errors * 2)
                    logger.error(f"Error in monitor loop: {e}. Retrying in {backoff}s...")
                    await asyncio.sleep(backoff)

                poll_interval = await get_poll_interval()
                await asyncio.sleep(poll_interval)

    def stop(self) -> None:
        self.is_running = False
