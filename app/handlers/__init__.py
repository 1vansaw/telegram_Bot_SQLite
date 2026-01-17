from .manuals import manuals_router
from .editors import editor_router
from .admins import admin_router
from .add_records import add_router
from .history import history_router
from .edit_records import edit_router
from .search import search_router
from .commands import commands_router
from aiogram import Router

router = Router()

router.include_router(commands_router)
router.include_router(search_router)     # ✅ Точное состояние + текст
router.include_router(edit_router)       # ✅ Точное состояние + текст
router.include_router(add_router)        # ✅ Точное состояние + текст
router.include_router(history_router)    # ✅ Точное состояние + текст

router.include_router(editor_router)     # ✅ ДО admin_router!
router.include_router(manuals_router)    # ✅ ДО admin_router!
router.include_router(admin_router)
