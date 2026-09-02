from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.modules.auth.router import router as auth_router
from app.modules.branches.router import branches_router, cities_router
from app.modules.categories.router import router as categories_router
from app.modules.catalog.router import admin_router as catalog_admin_router, public_router as catalog_router
from app.modules.inventory.router import public_router as inventory_public_router, router as inventory_router
from app.modules.suppliers.router import router as suppliers_router
from app.modules.users.router import roles_router, users_router


api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(roles_router)
api_router.include_router(cities_router)
api_router.include_router(branches_router)
api_router.include_router(categories_router)
api_router.include_router(suppliers_router)
api_router.include_router(catalog_router)
api_router.include_router(catalog_admin_router)
api_router.include_router(inventory_public_router)
api_router.include_router(inventory_router)
