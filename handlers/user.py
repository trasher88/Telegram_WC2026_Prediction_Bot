"""Combined user router.

The old monolithic user.py has been split into focused handler modules.
main.py can keep importing this router, so the public entry point stays stable.
"""

from aiogram import Router

from handlers.admin import router as admin_router
from handlers.common import router as common_router
from handlers.matches import router as matches_router
from handlers.my_predictions import router as my_predictions_router
from handlers.predictions import router as predictions_router

router = Router()

router.include_router(common_router)
router.include_router(matches_router)
router.include_router(predictions_router)
router.include_router(my_predictions_router)
router.include_router(admin_router)
