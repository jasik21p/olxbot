from aiogram import Dispatcher
from .auth import router as auth_router
from .admin import router as admin_router
from .filters import router as filters_router
from .common import router as common_router

def register_all_handlers(dp: Dispatcher) -> None:
    """Registers all routers in specific order."""
    dp.include_router(admin_router)
    dp.include_router(auth_router)
    dp.include_router(filters_router)
    dp.include_router(common_router)
