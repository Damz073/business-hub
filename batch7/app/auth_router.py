from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr

from app.api_auth import get_current_web_user
from app.auth_service import autenticar_web_user

router = APIRouter(prefix='/auth', tags=['auth'])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post('/login')
def login(payload: LoginRequest):
    try:
        return autenticar_web_user(payload.email, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.get('/me')
def me(current_user: dict = Depends(get_current_web_user)):
    return current_user
