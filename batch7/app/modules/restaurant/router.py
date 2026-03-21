from fastapi import APIRouter, Depends

from app.api_auth import get_current_web_user
from app.modules.restaurant.service import get_restaurant_summary

router = APIRouter(prefix='/restaurant', tags=['restaurant'])


@router.get('/summary')
def restaurant_summary(current_user: dict = Depends(get_current_web_user)):
    return get_restaurant_summary(current_user['business_id'])
