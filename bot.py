import asyncio
import logging
import sys
import os

# Ensure UTF-8 output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Cross-platform file locking (fcntl for Linux, msvcrt for Windows)
try:
    import fcntl
    def acquire_single_instance_lock():
        try:
            lock_file = open(LOCK_FILE_PATH, "a+")
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return lock_file
        except (IOError, OSError):
            logger.error("=" * 65)
            logger.error("❌ ОШИБКА: Другой экземпляр бота УЖЕ ЗАПУЩЕН!")
            logger.error("Одновременный запуск двух ботов приводит к ошибкам TelegramConflictError.")
            logger.error("Этот второй процесс будет немедленно остановлен.")
            logger.error("=" * 65)
            sys.exit(1)
except ImportError:
    import msvcrt
    def acquire_single_instance_lock():
        try:
            lock_file = open(LOCK_FILE_PATH, "a+")
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
            return lock_file
        except (IOError, OSError):
            logger.error("=" * 65)
            logger.error("❌ ОШИБКА: Другой экземпляр бота УЖЕ ЗАПУЩЕН!")
            logger.error("Одновременный запуск двух ботов приводит к ошибкам TelegramConflictError.")
            logger.error("Этот второй процесс будет немедленно остановлен.")
            logger.error("=" * 65)
            sys.exit(1)

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiohttp import web

from config import BOT_TOKEN, ADMIN_ID, LOCK_FILE_PATH
from database import init_db
from handlers import register_all_handlers
from monitor import OlxMonitor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("OLXBot")

async def start_healthcheck_server():
    """Lightweight HTTP server for cloud platforms (Koyeb / Render) health checks."""
    try:
        port = int(os.environ.get("PORT", 8000))
        app = web.Application()
        async def handle_ping(request):
            return web.Response(text="OLX Bot is running 24/7 OK")
        app.router.add_get("/", handle_ping)
        app.router.add_get("/health", handle_ping)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        logger.info(f"Healthcheck HTTP server listening on port {port}")
    except Exception as e:
        logger.warning(f"Could not start healthcheck HTTP server: {e}")

async def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not configured! Please specify it in .env or config.py.")
        return

    # Acquire exclusive file lock
    lock_file = acquire_single_instance_lock()

    logger.info("Initializing database...")
    await init_db()

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    # Register handlers
    register_all_handlers(dp)

    # Initialize and start background monitor
    monitor = OlxMonitor(bot)
    monitor_task = asyncio.create_task(monitor.start())

    # Start healthcheck server for Koyeb / cloud hosting
    await start_healthcheck_server()

    me = await bot.get_me()
    logger.info(f"🚀 Bot started successfully! @{me.username} [ID: {me.id}]")
    logger.info(f"👑 Admin ID: {ADMIN_ID}")
    logger.info("Ready to receive Telegram updates and monitor OLX.uz cars...")

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        logger.info("Shutting down bot...")
        monitor.stop()
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass
        await bot.session.close()
        try:
            lock_file.close()
        except Exception:
            pass
        logger.info("Bot stopped cleanly.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot execution terminated by user.")
