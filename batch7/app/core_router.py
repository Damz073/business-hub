from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api_auth import get_current_web_user
from app.core_services import get_core_overview, get_business_profile, list_business_customers, list_enabled_modules_for_business, toggle_business_module
from app.module_registry import list_module_manifests

router = APIRouter(prefix='/core', tags=['core'])


class ModuleTogglePayload(BaseModel):
    enabled: bool


@router.get('/overview')
def core_overview(current_user: dict = Depends(get_current_web_user)):
    return get_core_overview(current_user['business_id'])


@router.get('/business-profile')
def business_profile(current_user: dict = Depends(get_current_web_user)):
    return get_business_profile(current_user['business_id'])


@router.get('/customers')
def core_customers(current_user: dict = Depends(get_current_web_user)):
    items = list_business_customers(current_user['business_id'])
    return {'count': len(items), 'items': items}


@router.get('/modules')
def core_modules(current_user: dict = Depends(get_current_web_user)):
    return {
        'available': list_module_manifests(),
        'enabled': list_enabled_modules_for_business(current_user['business_id']),
    }


@router.put('/modules/{module_key}')
def core_toggle_module(module_key: str, payload: ModuleTogglePayload, current_user: dict = Depends(get_current_web_user)):
    items = toggle_business_module(current_user['business_id'], module_key, payload.enabled)
    return {'ok': True, 'items': items}
