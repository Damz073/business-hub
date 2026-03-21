from fastapi import APIRouter, Depends

from app.api_auth import get_current_web_user
from app.dashboard_service import obter_dashboard_summary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def dashboard_summary(current_user: dict = Depends(get_current_web_user)):
    return obter_dashboard_summary(current_user["restaurant_id"])
