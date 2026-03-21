from fastapi import APIRouter, Depends

from app.api_auth import get_current_web_user
from app.modules.beauty.service import get_beauty_summary

router = APIRouter(prefix='/beauty', tags=['beauty'])


@router.get('/summary')
def beauty_summary(current_user: dict = Depends(get_current_web_user)):
    return get_beauty_summary(current_user['business_id'])
