from fastapi import APIRouter, Depends, Query, HTTPException

from app.api_auth import get_current_web_user
from app.dashboard_service import listar_transacoes, listar_categorias
from app.modules.hospitality.service import update_transaction, delete_transaction

router = APIRouter(tags=["dashboard-data"])

from pydantic import BaseModel

class TransactionUpdatePayload(BaseModel):
    tipo: str | None = None
    categoria: str | None = None
    valor: float | None = None
    descricao: str | None = None

def _can_manage_finance(current_user: dict):
    return str(current_user.get('role') or "").lower() in {'admin', 'financeiro', 'gerente', 'owner'}


@router.get("/transactions")
def get_transactions(
    limit: int = Query(default=100, ge=1, le=500),
    tipo: str | None = Query(default=None),
    categoria: str | None = Query(default=None),
    data_inicio: str | None = Query(default=None),
    data_fim: str | None = Query(default=None),
    current_user: dict = Depends(get_current_web_user),
):
    items = listar_transacoes(
        restaurant_id=current_user["restaurant_id"],
        limit=limit,
        tipo=tipo,
        categoria=categoria,
        data_inicio=data_inicio,
        data_fim=data_fim,
    )
    return {
        "count": len(items),
        "items": items,
    }


@router.get("/categories")
def get_categories(current_user: dict = Depends(get_current_web_user)):
    items = listar_categorias(current_user["restaurant_id"])
    return {
        "count": len(items),
        "items": items,
    }

@router.put('/transactions/{transaction_id}')
def update_transaction_route(transaction_id: int, payload: TransactionUpdatePayload, current_user: dict = Depends(get_current_web_user)):
    if not _can_manage_finance(current_user):
        raise HTTPException(status_code=403, detail='Sem permissão para editar transações.')
    item = update_transaction(current_user['restaurant_id'], transaction_id, **payload.model_dump(exclude_none=True))
    if not item:
        raise HTTPException(status_code=404, detail='Transação não encontrada.')
    return {'ok': True, 'item': item, 'items': listar_transacoes(current_user['restaurant_id'])}

@router.delete('/transactions/{transaction_id}')
def delete_transaction_route(transaction_id: int, current_user: dict = Depends(get_current_web_user)):
    if not _can_manage_finance(current_user):
        raise HTTPException(status_code=403, detail='Sem permissão para excluir transações.')
    item = delete_transaction(current_user['restaurant_id'], transaction_id)
    if not item:
        raise HTTPException(status_code=404, detail='Transação não encontrada.')
    return {'ok': True, 'item': item, 'items': listar_transacoes(current_user['restaurant_id'])}
