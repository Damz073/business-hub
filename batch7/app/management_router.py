from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api_auth import get_current_web_user
from app.dashboard_service import (
    listar_merchants,
    listar_restaurant_users,
    obter_restaurant_info,
)
from app.admin_service import adicionar_usuario_restaurante, listar_usuarios_restaurante, remover_usuario_restaurante
from app.database import conectar


class RestaurantUserPayload(BaseModel):
    nome: str
    telefone: str
    role: str = "staff"


class RestaurantUserRolePayload(BaseModel):
    role: str

router = APIRouter(tags=["dashboard-management"])


@router.get("/merchants")
def get_merchants(
    apenas_ativos: bool = Query(default=True),
    current_user: dict = Depends(get_current_web_user),
):
    items = listar_merchants(
        restaurant_id=current_user["restaurant_id"],
        apenas_ativos=apenas_ativos,
    )
    return {
        "count": len(items),
        "items": items,
    }


@router.get("/restaurant-users")
def get_restaurant_users(
    apenas_ativos: bool = Query(default=False),
    current_user: dict = Depends(get_current_web_user),
):
    items = listar_restaurant_users(
        restaurant_id=current_user["restaurant_id"],
        apenas_ativos=apenas_ativos,
    )
    return {
        "count": len(items),
        "items": items,
    }


@router.get("/restaurant-info")
def get_restaurant_info(current_user: dict = Depends(get_current_web_user)):
    info = obter_restaurant_info(current_user["restaurant_id"])
    return info or {
        "restaurant_id": current_user["restaurant_id"],
        "restaurant_name": current_user.get("restaurant_name"),
        "status": None,
        "plano": None,
        "vencimento": None,
    }


@router.post("/restaurant-users")
def create_restaurant_user(payload: RestaurantUserPayload, current_user: dict = Depends(get_current_web_user)):
    try:
        adicionar_usuario_restaurante(current_user["restaurant_id"], payload.telefone, nome=payload.nome, role=payload.role)
        items = listar_restaurant_users(current_user["restaurant_id"], apenas_ativos=False)
        return {"ok": True, "count": len(items), "items": items}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/restaurant-users/{user_id}")
def update_restaurant_user_role(user_id: int, payload: RestaurantUserRolePayload, current_user: dict = Depends(get_current_web_user)):
    conn = conectar(); cursor = conn.cursor()
    cursor.execute("SELECT id, telefone FROM restaurant_users WHERE id = ? AND restaurant_id = ? LIMIT 1", (user_id, current_user["restaurant_id"]))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    cursor.execute("UPDATE restaurant_users SET role = ? WHERE id = ?", (payload.role, user_id))
    cursor.execute("UPDATE business_contacts SET role = ? WHERE legacy_restaurant_user_id = ?", (payload.role, user_id))
    conn.commit(); conn.close()
    items = listar_restaurant_users(current_user["restaurant_id"], apenas_ativos=False)
    return {"ok": True, "count": len(items), "items": items}


@router.delete("/restaurant-users/{user_id}")
def delete_restaurant_user(user_id: int, current_user: dict = Depends(get_current_web_user)):
    conn = conectar(); cursor = conn.cursor()
    cursor.execute("SELECT id, telefone, nome FROM restaurant_users WHERE id = ? AND restaurant_id = ? LIMIT 1", (user_id, current_user["restaurant_id"]))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    removed = dict(row)
    cursor.execute("DELETE FROM restaurant_users WHERE id = ? AND restaurant_id = ?", (user_id, current_user["restaurant_id"]))
    cursor.execute("DELETE FROM business_contacts WHERE legacy_restaurant_user_id = ?", (user_id,))
    conn.commit(); conn.close()
    items = listar_restaurant_users(current_user["restaurant_id"], apenas_ativos=False)
    return {"ok": True, "removed": removed, "count": len(items), "items": items}
