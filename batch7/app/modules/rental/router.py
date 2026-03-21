from fastapi import APIRouter, Depends

from app.api_auth import get_current_web_user
from app.modules.rental.service import get_rental_summary

router = APIRouter(prefix='/rental', tags=['rental'])


@router.get('/summary')
def rental_summary(current_user: dict = Depends(get_current_web_user)):
    return get_rental_summary(current_user['business_id'])
