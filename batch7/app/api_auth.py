from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth_service import obter_usuario_atual_do_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_web_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Token bearer não informado.")

    try:
        return obter_usuario_atual_do_token(credentials.credentials)
    except Exception as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
