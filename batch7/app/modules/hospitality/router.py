from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api_auth import get_current_web_user
from app.core_services import get_bot_settings, upsert_bot_settings
from app.modules.hospitality.service import (
    assume_session,
    confirm_reservation_payment,
    criar_reserva_manual,
    inventory_snapshot,
    get_chat_messages_for_business,
    list_chat_messages,
    list_manual_rates,
    list_pending_payment_confirmations,
    list_room_types,
    listar_chat_sessions,
    listar_reservas,
    manual_rates_status_text,
    obter_hospitality_summary,
    release_session,
    send_manual_message,
    set_manual_rate,
    upsert_room_type,
    delete_room_type,
)

router = APIRouter(prefix='/hospitality', tags=['hospitality'])


class ReservationCreatePayload(BaseModel):
    guest_name: str
    guest_phone: str
    checkin_date: str | None = None
    checkout_date: str | None = None
    guest_count: int | None = None
    unit_category: str | None = None
    quoted_amount: float | None = None
    notes: str | None = None
    source: str | None = 'panel'
    external_reservation_id: str | None = None
    sync_status: str | None = 'not_synced'


class BotSettingsPayload(BaseModel):
    assistant_name: str | None = None
    welcome_message: str | None = None
    fallback_message: str | None = None
    pix_key: str | None = None
    payment_link_base: str | None = None
    human_handoff_enabled: bool | None = None
    auto_reply_enabled: bool | None = None
    reservations_module_enabled: bool | None = None
    finance_module_enabled: bool | None = None
    whatsapp_phone_number_id: str | None = None
    whatsapp_business_account_id: str | None = None
    whatsapp_verify_token: str | None = None
    checkin_time: str | None = None
    checkout_time: str | None = None
    reservation_payment_instructions: str | None = None
    hospitality_mode: str | None = None
    rate_collection_frequency: str | None = None
    rate_collection_time: str | None = None
    last_rate_prompt_at: str | None = None
    external_system_type: str | None = None
    omnibees_hotel_id: str | None = None
    omnibees_sync_enabled: bool | None = None
    location_text: str | None = None
    maps_link: str | None = None
    pool_info: str | None = None
    garage_info: str | None = None
    breakfast_info: str | None = None
    pet_policy: str | None = None
    amenities_text: str | None = None
    fiscal_company_name: str | None = None
    fiscal_document: str | None = None
    fiscal_municipal_registration: str | None = None
    fiscal_service_city: str | None = None
    fiscal_email: str | None = None
    public_business_name: str | None = None
    public_contact_phone: str | None = None
    street_address: str | None = None
    neighborhood: str | None = None
    city_name: str | None = None
    state_code: str | None = None
    payment_alert_phones: str | None = None


class SessionReplyPayload(BaseModel):
    text: str


class RoomTypePayload(BaseModel):
    code: str
    name: str | None = None
    category: str | None = None
    capacity: int | None = None
    base_rate: float | None = None
    quantity_total: int | None = None
    bed_setup: str | None = None
    max_adults: int | None = None
    max_children: int | None = None
    notes: str | None = None
    active: int | None = None


class ManualRatePayload(BaseModel):
    room_code: str
    rate_value: float
    period: str = 'daily'
    note: str | None = None


@router.get('/summary')
def hospitality_summary(current_user: dict = Depends(get_current_web_user)):
    return obter_hospitality_summary(current_user['business_id'])


@router.get('/inbox')
def hospitality_inbox(current_user: dict = Depends(get_current_web_user)):
    items = listar_chat_sessions(current_user['business_id'])
    return {'count': len(items), 'items': items}


@router.get('/inbox/{session_id}')
def hospitality_inbox_detail(session_id: int, current_user: dict = Depends(get_current_web_user)):
    return {'session_id': session_id, 'items': get_chat_messages_for_business(session_id, current_user['business_id'])}


@router.get('/inbox/{session_id}/messages')
def hospitality_inbox_messages(session_id: int, current_user: dict = Depends(get_current_web_user)):
    return {'session_id': session_id, 'items': get_chat_messages_for_business(session_id, current_user['business_id'])}


@router.post('/inbox/{session_id}/assume')
def hospitality_inbox_assume(session_id: int, current_user: dict = Depends(get_current_web_user)):
    try:
        item = assume_session(session_id, current_user['business_id'], assigned_to_phone=None, assigned_to_name=current_user.get('name'))
        return {'ok': True, 'item': item}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post('/inbox/{session_id}/release')
def hospitality_inbox_release(session_id: int, current_user: dict = Depends(get_current_web_user)):
    try:
        item = release_session(session_id, current_user['business_id'])
        return {'ok': True, 'item': item}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post('/inbox/{session_id}/reply')
def hospitality_inbox_reply(session_id: int, payload: SessionReplyPayload, current_user: dict = Depends(get_current_web_user)):
    try:
        result = send_manual_message(session_id, current_user['business_id'], payload.text, current_user.get('name'))
        return {'ok': True, **result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get('/reservations')
def hospitality_reservations(current_user: dict = Depends(get_current_web_user)):
    items = listar_reservas(current_user['business_id'])
    return {'count': len(items), 'items': items}


@router.get('/pending-payments')
def hospitality_pending_payments(current_user: dict = Depends(get_current_web_user)):
    items = list_pending_payment_confirmations(current_user['business_id'])
    return {'count': len(items), 'items': items}


@router.post('/reservations')
def hospitality_reservation_create(payload: ReservationCreatePayload, current_user: dict = Depends(get_current_web_user)):
    item = criar_reserva_manual(current_user['business_id'], **payload.model_dump())
    return {'ok': True, 'item': item}


@router.post('/reservations/{reservation_id}/confirm-payment')
def hospitality_reservation_confirm_payment(reservation_id: int, current_user: dict = Depends(get_current_web_user)):
    try:
        result = confirm_reservation_payment(reservation_id=reservation_id, business_id=current_user['business_id'], restaurant_id=current_user['restaurant_id'], actor_name=current_user.get('name'))
        return {'ok': True, **result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get('/settings')
def hospitality_settings(current_user: dict = Depends(get_current_web_user)):
    return get_bot_settings(current_user['business_id'])


@router.put('/settings')
def hospitality_settings_update(payload: BotSettingsPayload, current_user: dict = Depends(get_current_web_user)):
    item = upsert_bot_settings(current_user['business_id'], **payload.model_dump(exclude_none=True))
    return {'ok': True, 'item': item}


@router.get('/room-types')
def hospitality_room_types(current_user: dict = Depends(get_current_web_user)):
    items = list_room_types(current_user['business_id'])
    return {'count': len(items), 'items': items}


@router.post('/room-types')
def hospitality_room_type_create(payload: RoomTypePayload, current_user: dict = Depends(get_current_web_user)):
    item = upsert_room_type(current_user['business_id'], **payload.model_dump(exclude_none=True))
    return {'ok': True, 'item': item}


@router.delete('/room-types/{room_id}')
def hospitality_room_type_delete(room_id: int, current_user: dict = Depends(get_current_web_user)):
    item = delete_room_type(current_user['business_id'], room_id)
    if not item:
        raise HTTPException(status_code=404, detail='Tipo de quarto não encontrado.')
    return {'ok': True, 'item': item}


@router.get('/inventory')
def hospitality_inventory(current_user: dict = Depends(get_current_web_user)):
    snapshot = inventory_snapshot(current_user['business_id'])
    return {'count': len(snapshot), 'items': snapshot}


@router.get('/occupancy-map')
def hospitality_occupancy_map(current_user: dict = Depends(get_current_web_user)):
    snapshot = inventory_snapshot(current_user['business_id'])
    items = []
    for item in snapshot:
        total = int(item.get('total') or 0)
        occupied = int(item.get('occupied_estimate') or 0)
        available = int(item.get('available_estimate') or 0)
        occupancy_pct = round((occupied / total) * 100, 1) if total else 0
        status = 'alta' if occupancy_pct >= 80 else ('media' if occupancy_pct >= 40 else 'baixa')
        items.append({**item, 'occupancy_pct': occupancy_pct, 'occupancy_status': status})
    return {'count': len(items), 'items': items}


@router.get('/rates')
def hospitality_rates(current_user: dict = Depends(get_current_web_user)):
    return {'count': len(list_manual_rates(current_user['business_id'])), 'items': list_manual_rates(current_user['business_id']), 'status_text': manual_rates_status_text(current_user['business_id'])}


@router.post('/rates')
def hospitality_rates_create(payload: ManualRatePayload, current_user: dict = Depends(get_current_web_user)):
    item = set_manual_rate(current_user['business_id'], payload.room_code, payload.rate_value, period=payload.period, note=payload.note)
    return {'ok': True, 'item': item}
