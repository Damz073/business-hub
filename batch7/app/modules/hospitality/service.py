from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional
import random
import string
import json

from app.core_services import (
    ensure_chat_session,
    get_bot_settings,
    log_chat_message,
    update_chat_session_status,
    upsert_bot_settings,
)
from app.database import conectar
from app.storage import salvar_transacao
from app.whatsapp_api import enviar_mensagem_texto



PROFESSIONAL_STATUS_MAP = {
    'lead': 'lead',
    'quoted': 'aguardando_pagamento',
    'confirmada': 'confirmada',
    'checkin': 'checkin',
    'checkout': 'checkout',
    'cancelada': 'cancelada',
    'bloqueada': 'bloqueada',
}


def _generate_reservation_code() -> str:
    return 'RES-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))


def _normalize_reservation_source(source: str | None) -> str:
    raw = (source or 'whatsapp').strip().lower()
    mapping = {
        'panel': 'balcao',
        'admin_manual': 'balcao',
        'manual': 'balcao',
        'desk': 'balcao',
        'frontdesk': 'balcao',
        'pms_voa': 'site',
    }
    return mapping.get(raw, raw or 'whatsapp')


def _normalize_reservation_status(status: str | None, payment_status: str | None = None) -> str:
    raw = (status or '').strip().lower()
    if raw in {'lead', 'aguardando_pagamento', 'confirmada', 'checkin', 'checkout', 'cancelada', 'bloqueada'}:
        return raw
    if raw == 'quoted':
        return 'aguardando_pagamento'
    if raw == 'canceled':
        return 'cancelada'
    if raw == 'confirmed':
        return 'confirmada'
    if raw == 'blocked':
        return 'bloqueada'
    if raw == 'pending_payment':
        return 'aguardando_pagamento'
    if (payment_status or '').lower() == 'confirmado':
        return 'confirmada'
    return 'lead'


def _serialize_guests(guests: list[dict] | None) -> str:
    return json.dumps(guests or [], ensure_ascii=False)


def _deserialize_guests(raw) -> list[dict]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _build_guest_records(main_name: str | None, main_phone: str | None, main_email: str | None = None, guests: list[dict] | None = None, cpf: str | None = None, city: str | None = None, car_plate: str | None = None):
    records: list[dict] = []
    if main_name or main_phone or main_email or cpf or city or car_plate:
        records.append({
            'name': main_name,
            'phone': main_phone,
            'email': main_email,
            'cpf': cpf,
            'city': city,
            'car_plate': car_plate,
            'is_main': True,
        })
    for guest in guests or []:
        if not isinstance(guest, dict):
            continue
        item = {
            'name': guest.get('name') or guest.get('nome'),
            'phone': guest.get('phone') or guest.get('telefone'),
            'email': guest.get('email'),
            'cpf': guest.get('cpf'),
            'city': guest.get('city') or guest.get('cidade'),
            'car_plate': guest.get('car_plate') or guest.get('placa_do_carro') or guest.get('placa'),
            'is_main': bool(guest.get('is_main')),
        }
        if any(item.values()):
            records.append(item)
    return records


def _replace_reservation_guests(cur, reservation_id: int, main_name: str | None, main_phone: str | None, main_email: str | None = None, guests: list[dict] | None = None, cpf: str | None = None, city: str | None = None, car_plate: str | None = None):
    cur.execute('DELETE FROM reservation_guests WHERE reservation_request_id = ?', (reservation_id,))
    for guest in _build_guest_records(main_name, main_phone, main_email, guests=guests, cpf=cpf, city=city, car_plate=car_plate):
        cur.execute(
            """
            INSERT INTO reservation_guests (
                reservation_request_id, name, cpf, phone, email, city, car_plate, is_main, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (reservation_id, guest.get('name'), guest.get('cpf'), guest.get('phone'), guest.get('email'), guest.get('city'), guest.get('car_plate'), 1 if guest.get('is_main') else 0),
        )


def _fetch_reservation_guests(cur, reservation_id: int):
    cur.execute(
        """
        SELECT id, name, cpf, phone, email, city, car_plate, is_main, created_at, updated_at
        FROM reservation_guests
        WHERE reservation_request_id = ?
        ORDER BY is_main DESC, id ASC
        """,
        (reservation_id,),
    )
    return [dict(r) for r in cur.fetchall()]


def _enrich_reservation(row: dict, cur):
    item = dict(row)
    item['source'] = _normalize_reservation_source(item.get('source'))
    item['status'] = _normalize_reservation_status(item.get('professional_status') or item.get('status'), item.get('payment_status'))
    item['legacy_status'] = item.get('status')
    item['professional_status'] = item['status']
    item['reservation_code'] = item.get('reservation_code') or f"RES-{item['id']:06d}"
    item['total_value'] = float(item.get('total_value') or item.get('quoted_amount') or 0)
    item['quoted_amount'] = float(item.get('quoted_amount') or item.get('total_value') or 0)
    item['main_guest_name'] = item.get('main_guest_name') or item.get('guest_name')
    item['main_guest_phone'] = item.get('main_guest_phone') or item.get('guest_phone')
    item['guest_document'] = item.get('guest_document')
    item['guest_email'] = item.get('guest_email')
    item['guest_city'] = item.get('guest_city')
    item['car_plate'] = item.get('car_plate')
    item['estimated_arrival'] = item.get('estimated_arrival')
    item['notes_internal'] = item.get('notes_internal')
    item['guest_list_json'] = item.get('guest_list_json') or '[]'
    guests = _fetch_reservation_guests(cur, item['id'])
    if not guests:
        guests = _build_guest_records(item.get('main_guest_name') or item.get('guest_name'), item.get('main_guest_phone') or item.get('guest_phone'), item.get('guest_email'), guests=_deserialize_guests(item.get('guest_list_json')), cpf=item.get('guest_document'), city=item.get('guest_city'), car_plate=item.get('car_plate'))
    item['guests'] = guests
    item['guest_summary'] = ', '.join([g.get('name') for g in guests if g.get('name')][:3]) or (item.get('main_guest_name') or item.get('guest_name') or item.get('guest_phone'))
    return item


def get_reservation_detail(business_id: int, reservation_id: int):
    conn = conectar(); cur = conn.cursor()
    cur.execute(
        """
        SELECT id, business_id, session_id, guest_name, guest_phone, checkin_date, checkout_date, guest_count,
               unit_category, quoted_amount, status, payment_status, payment_reference, human_confirmation_required,
               notes, finance_transaction_id, source, external_reservation_id, sync_status, created_at, updated_at,
               reservation_code, professional_status, total_value, notes_internal, main_guest_name, main_guest_phone,
               guest_document, guest_email, guest_city, car_plate, estimated_arrival, guest_list_json
        FROM reservation_requests
        WHERE id = ? AND business_id = ? LIMIT 1
        """,
        (reservation_id, business_id),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        return None
    item = _enrich_reservation(dict(row), cur)
    conn.close()
    return item


DEFAULT_ROOM_TYPES = [
    {'code': 'STD-CASAL', 'name': 'Standard Casal', 'category': 'standard', 'capacity': 2, 'base_rate': 260.0, 'quantity_total': 8, 'bed_setup': '1 cama casal', 'notes': 'Tipologia padrão sugerida para o MVP.'},
    {'code': 'STD-TWIN', 'name': 'Standard Twin', 'category': 'standard', 'capacity': 2, 'base_rate': 260.0, 'quantity_total': 6, 'bed_setup': '2 camas solteiro', 'notes': 'Tipologia padrão sugerida para o MVP.'},
    {'code': 'TRIPLO', 'name': 'Triplo', 'category': 'triplo', 'capacity': 3, 'base_rate': 340.0, 'quantity_total': 4, 'bed_setup': '1 cama casal + 1 solteiro', 'notes': 'Tipologia padrão sugerida para o MVP.'},
    {'code': 'FAMILIA', 'name': 'Família', 'category': 'familia', 'capacity': 4, 'base_rate': 420.0, 'quantity_total': 4, 'bed_setup': '1 cama casal + 2 solteiros', 'notes': 'Tipologia padrão sugerida para o MVP.'},
]


# ---------- room types ----------
def ensure_sample_units_for_hospitality(business_id: int):
    conn = conectar(); cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS total FROM accommodation_units WHERE business_id = ?", (business_id,))
    total = cur.fetchone()[0]
    if total:
        conn.close(); return
    for idx, item in enumerate(DEFAULT_ROOM_TYPES, start=1):
        cur.execute(
            """
            INSERT INTO accommodation_units (
                business_id, code, name, category, capacity, base_rate, active, notes,
                quantity_total, bed_setup, max_adults, max_children, sort_order
            ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?)
            """,
            (business_id, item['code'], item['name'], item['category'], item['capacity'], item['base_rate'], item['notes'], item['quantity_total'], item['bed_setup'], item['capacity'], 0, idx),
        )
    conn.commit(); conn.close()


def list_room_types(business_id: int):
    ensure_sample_units_for_hospitality(business_id)
    conn = conectar(); cur = conn.cursor()
    cur.execute(
        """
        SELECT id, code, name, category, capacity, base_rate, active, notes,
               quantity_total, bed_setup, max_adults, max_children, sort_order,
               created_at, updated_at
        FROM accommodation_units WHERE business_id = ?
        ORDER BY sort_order ASC, name ASC, id ASC
        """,
        (business_id,),
    )
    items = [dict(r) for r in cur.fetchall()]
    conn.close()
    return items


def upsert_room_type(business_id: int, code: str, name: str | None = None, category: str | None = None,
                     capacity: int | None = None, base_rate: float | None = None, quantity_total: int | None = None,
                     bed_setup: str | None = None, max_adults: int | None = None, max_children: int | None = None,
                     notes: str | None = None, active: int | None = None):
    ensure_sample_units_for_hospitality(business_id)
    conn = conectar(); cur = conn.cursor()
    cur.execute("SELECT * FROM accommodation_units WHERE business_id = ? AND code = ? LIMIT 1", (business_id, code))
    row = cur.fetchone()
    if row:
        current = dict(row)
        cur.execute(
            """
            UPDATE accommodation_units
            SET name = ?, category = ?, capacity = ?, base_rate = ?, active = ?, notes = ?,
                quantity_total = ?, bed_setup = ?, max_adults = ?, max_children = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                name if name is not None else current['name'],
                category if category is not None else current['category'],
                capacity if capacity is not None else current['capacity'],
                base_rate if base_rate is not None else current['base_rate'],
                active if active is not None else current['active'],
                notes if notes is not None else current['notes'],
                quantity_total if quantity_total is not None else current.get('quantity_total'),
                bed_setup if bed_setup is not None else current.get('bed_setup'),
                max_adults if max_adults is not None else current.get('max_adults'),
                max_children if max_children is not None else current.get('max_children'),
                current['id'],
            ),
        )
        unit_id = current['id']
    else:
        cur.execute(
            """
            INSERT INTO accommodation_units (
                business_id, code, name, category, capacity, base_rate, active, notes,
                quantity_total, bed_setup, max_adults, max_children, sort_order
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT MAX(sort_order) + 1 FROM accommodation_units WHERE business_id = ?), 1))
            """,
            (business_id, code, name or code, category, capacity or 2, base_rate or 0, 1 if active is None else active,
             notes, quantity_total if quantity_total is not None else 1, bed_setup, max_adults if max_adults is not None else (capacity or 2), max_children if max_children is not None else 0, business_id),
        )
        unit_id = cur.lastrowid
    conn.commit(); cur.execute("SELECT * FROM accommodation_units WHERE id = ?", (unit_id,)); item = dict(cur.fetchone()); conn.close(); return item


def delete_room_type(business_id: int, room_id: int):
    conn = conectar(); cur = conn.cursor()
    cur.execute("SELECT * FROM accommodation_units WHERE id = ? AND business_id = ? LIMIT 1", (room_id, business_id))
    row = cur.fetchone()
    if not row:
        conn.close(); return None
    item = dict(row)
    cur.execute("DELETE FROM accommodation_units WHERE id = ? AND business_id = ?", (room_id, business_id))
    conn.commit(); conn.close()
    return item


# ---------- chat/inbox ----------
def find_session_by_phone(customer_phone: str, business_id: int | None = None):
    conn = conectar(); cur = conn.cursor()
    query = "SELECT * FROM chat_sessions WHERE customer_phone = ?"; params: list[object] = [customer_phone]
    if business_id is not None:
        query += " AND business_id = ?"; params.append(business_id)
    query += " ORDER BY id DESC LIMIT 1"
    cur.execute(query, tuple(params)); row = cur.fetchone(); conn.close(); return dict(row) if row else None


def list_chat_messages(session_id: int):
    conn = conectar(); cur = conn.cursor()
    cur.execute("""
        SELECT id, direction, sender_type, sender_phone, message_type, text_content, payload_json, created_at
        FROM chat_messages WHERE session_id = ? ORDER BY id ASC
    """, (session_id,))
    items = [dict(r) for r in cur.fetchall()]; conn.close(); return items


def get_chat_messages_for_business(session_id: int, business_id: int):
    _get_session_or_raise(session_id, business_id)
    return list_chat_messages(session_id)


def _get_session_or_raise(session_id: int, business_id: int):
    conn = conectar(); cur = conn.cursor(); cur.execute("SELECT * FROM chat_sessions WHERE id = ? AND business_id = ? LIMIT 1", (session_id, business_id)); row = cur.fetchone(); conn.close()
    if not row: raise ValueError('Conversa não encontrada.')
    return dict(row)


def assume_session(session_id: int, business_id: int, assigned_to_phone: str | None, assigned_to_name: str | None):
    _get_session_or_raise(session_id, business_id)
    update_chat_session_status(session_id, 'human_active', assigned_to_phone=assigned_to_phone, assigned_to_name=assigned_to_name, handoff_reason='Assumido manualmente pelo painel')
    return _get_session_or_raise(session_id, business_id)


def release_session(session_id: int, business_id: int):
    _get_session_or_raise(session_id, business_id)
    update_chat_session_status(session_id, 'bot_active', assigned_to_phone=None, assigned_to_name=None, handoff_reason='Devolvido ao bot pelo painel')
    return _get_session_or_raise(session_id, business_id)


def send_manual_message(session_id: int, business_id: int, text: str, sender_name: str | None):
    session = _get_session_or_raise(session_id, business_id)
    response = enviar_mensagem_texto(text, session['customer_phone'])
    log_chat_message(session_id=session_id, direction='outbound', sender_type='human', sender_phone=session.get('assigned_to_phone'), message_type='text', text_content=text, payload=response)
    update_chat_session_status(session_id, 'human_active', assigned_to_phone=session.get('assigned_to_phone'), assigned_to_name=sender_name or session.get('assigned_to_name') or 'Equipe', handoff_reason='Mensagem enviada manualmente pelo painel')
    return {'session': _get_session_or_raise(session_id, business_id), 'delivery': response}


# ---------- manual rates ----------
def _now_iso():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def set_manual_rate(business_id: int, room_code: str, rate_value: float, period: str = 'daily', note: str | None = None):
    now = datetime.now()
    valid_from = now.replace(second=0, microsecond=0)
    if period == 'weekly':
        valid_until = valid_from + timedelta(days=7)
    else:
        valid_until = valid_from.replace(hour=23, minute=59)
    conn = conectar(); cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO room_rate_overrides (business_id, room_code, rate_value, valid_from, valid_until, source, note)
        VALUES (?, ?, ?, ?, ?, 'manual_admin', ?)
        """,
        (business_id, room_code.upper(), rate_value, valid_from.strftime('%Y-%m-%d %H:%M:%S'), valid_until.strftime('%Y-%m-%d %H:%M:%S'), note),
    )
    conn.commit(); conn.close()
    return {'room_code': room_code.upper(), 'rate_value': rate_value, 'valid_from': valid_from.isoformat(sep=' '), 'valid_until': valid_until.isoformat(sep=' ')}


def list_manual_rates(business_id: int):
    conn = conectar(); cur = conn.cursor()
    cur.execute(
        """
        SELECT r1.* FROM room_rate_overrides r1
        JOIN (
            SELECT room_code, MAX(id) AS max_id FROM room_rate_overrides
            WHERE business_id = ? GROUP BY room_code
        ) last ON last.max_id = r1.id
        WHERE r1.business_id = ?
        ORDER BY r1.room_code ASC
        """,
        (business_id, business_id),
    )
    items = [dict(r) for r in cur.fetchall()]
    conn.close(); return items


def get_effective_rate(business_id: int, room_code: str, base_rate: float = 0.0):
    conn = conectar(); cur = conn.cursor(); now = _now_iso()
    cur.execute(
        """
        SELECT rate_value FROM room_rate_overrides
        WHERE business_id = ? AND room_code = ? AND datetime(valid_from) <= datetime(?) AND datetime(valid_until) >= datetime(?)
        ORDER BY id DESC LIMIT 1
        """,
        (business_id, room_code.upper(), now, now),
    )
    row = cur.fetchone(); conn.close()
    return float(row['rate_value']) if row else float(base_rate or 0)


def manual_rates_status_text(business_id: int):
    settings = get_bot_settings(business_id) or {}
    mode = settings.get('hospitality_mode') or 'manual_rates'
    lines = [f"Modo operacional: {mode}"]
    for item in list_room_types(business_id):
        effective = get_effective_rate(business_id, item['code'], item.get('base_rate') or 0)
        lines.append(f"{item['code']}: R$ {effective:.2f} (base: R$ {float(item.get('base_rate') or 0):.2f})")
    latest = list_manual_rates(business_id)
    if latest:
        lines.append('Últimas validades:')
        for item in latest:
            lines.append(f"{item['room_code']} até {item['valid_until']}")
    return '\n'.join(lines)


# ---------- occupancy / reservations ----------
def listar_chat_sessions(business_id: int, status: str | None = None):
    conn = conectar(); cur = conn.cursor()
    query = """
        SELECT id, customer_phone, customer_name, channel, last_message_at, status,
               assigned_to_phone, assigned_to_name, handoff_reason, last_customer_message,
               last_bot_message, created_at, updated_at
        FROM chat_sessions WHERE business_id = ?
    """
    params = [business_id]
    if status:
        query += ' AND status = ?'; params.append(status)
    query += ' ORDER BY datetime(last_message_at) DESC, id DESC LIMIT 100'
    cur.execute(query, tuple(params)); items = [dict(r) for r in cur.fetchall()]; conn.close(); return items


def listar_reservas(business_id: int, status: str | None = None):
    conn = conectar(); cur = conn.cursor()
    query = """
        SELECT id, business_id, session_id, guest_name, guest_phone, checkin_date, checkout_date, guest_count,
               unit_category, quoted_amount, status, payment_status, payment_reference,
               human_confirmation_required, notes, finance_transaction_id, source,
               external_reservation_id, sync_status, created_at, updated_at,
               reservation_code, professional_status, total_value, notes_internal, main_guest_name, main_guest_phone,
               guest_document, guest_email, guest_city, car_plate, estimated_arrival, guest_list_json
        FROM reservation_requests WHERE business_id = ?
    """
    params = [business_id]
    if status:
        query += ' AND (professional_status = ? OR status = ?)'; params.extend([status, status])
    query += ' ORDER BY date(checkin_date) ASC, datetime(updated_at) DESC, id DESC LIMIT 200'
    cur.execute(query, tuple(params))
    items = [_enrich_reservation(dict(r), cur) for r in cur.fetchall()]
    conn.close()
    return items


def criar_reserva_manual(business_id: int, guest_name: str, guest_phone: str, checkin_date: str | None, checkout_date: str | None,
                        guest_count: int | None, unit_category: str | None, quoted_amount: float | None,
                        status: str = 'quoted', payment_status: str = 'aguardando_pagamento', notes: str | None = None,
                        session_id: int | None = None, source: str = 'panel', external_reservation_id: str | None = None,
                        sync_status: str = 'not_synced'):
    conn = conectar(); cur = conn.cursor()
    if not session_id:
        session = ensure_chat_session(business_id, guest_phone, guest_name)
        session_id = session['id']
    cur.execute(
        """
        INSERT INTO reservation_requests (
            business_id, session_id, guest_name, guest_phone, checkin_date, checkout_date,
            guest_count, unit_category, quoted_amount, status, payment_status, notes,
            source, external_reservation_id, sync_status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (business_id, session_id, guest_name, guest_phone, checkin_date, checkout_date, guest_count,
         unit_category, quoted_amount, status, payment_status, notes, source, external_reservation_id, sync_status),
    )
    reservation_id = cur.lastrowid
    if quoted_amount:
        settings = get_bot_settings(business_id) or {}
        cur.execute(
            """
            INSERT INTO payment_requests (
                business_id, reservation_request_id, amount, payment_method, payment_key, payment_link, status
            ) VALUES (?, ?, ?, 'pix', ?, ?, 'pending_confirmation')
            """,
            (business_id, reservation_id, quoted_amount, settings.get('pix_key'), settings.get('payment_link_base')),
        )
    conn.commit(); cur.execute("SELECT * FROM reservation_requests WHERE id = ?", (reservation_id,)); row = dict(cur.fetchone()); conn.close(); return row


def _build_customer_confirmation_message(reservation: dict):
    amount = float(reservation.get('quoted_amount') or 0)
    guest_name = reservation.get('guest_name') or 'sua reserva'
    lines = [
        'Pagamento confirmado ✅',
        '',
        f"{guest_name}, sua reserva está confirmada.",
    ]
    if reservation.get('checkin_date') or reservation.get('checkout_date'):
        lines.extend([
            f"Check-in: {reservation.get('checkin_date') or '-'}",
            f"Check-out: {reservation.get('checkout_date') or '-'}",
        ])
    if reservation.get('unit_category'):
        lines.append(f"Quarto: {reservation.get('unit_category')}")
    if reservation.get('guest_count'):
        lines.append(f"Hóspedes: {reservation.get('guest_count')}")
    if amount:
        lines.append(f"Valor: R$ {amount:.2f}")
    lines.extend(['', 'Te esperamos 😊'])
    return '\n'.join(lines)

def _notify_customer_payment_confirmed(reservation: dict):
    phone = reservation.get('guest_phone')
    if not phone:
        return None
    return enviar_mensagem_texto(_build_customer_confirmation_message(reservation), phone)



def confirm_reservation_payment(reservation_id: int, business_id: int, restaurant_id: int, actor_name: str | None = None):
    conn = conectar(); cur = conn.cursor(); cur.execute("SELECT * FROM reservation_requests WHERE id = ? AND business_id = ? LIMIT 1", (reservation_id, business_id)); row = cur.fetchone()
    if not row:
        conn.close(); raise ValueError('Reserva não encontrada.')
    reservation = dict(row)
    finance_transaction_id = reservation.get('finance_transaction_id')
    if not finance_transaction_id:
        finance_transaction_id = salvar_transacao(restaurant_id, {'tipo': 'entrada', 'categoria': 'hospedagem', 'valor': float(reservation.get('quoted_amount') or 0), 'descricao': f"Reserva {reservation.get('guest_name') or reservation.get('guest_phone')}"})
    cur.execute("UPDATE reservation_requests SET status = 'confirmada', professional_status = 'confirmada', payment_status = 'confirmado', finance_transaction_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (finance_transaction_id, reservation_id))
    cur.execute("UPDATE payment_requests SET status = 'confirmed', updated_at = CURRENT_TIMESTAMP WHERE reservation_request_id = ?", (reservation_id,))
    cur.execute("SELECT session_id FROM reservation_requests WHERE id = ?", (reservation_id,))
    session_row = cur.fetchone()
    conn.commit(); cur.execute("SELECT * FROM reservation_requests WHERE id = ?", (reservation_id,)); result = _enrich_reservation(dict(cur.fetchone()), cur); conn.close()
    if session_row and session_row['session_id']:
        update_chat_session_status(session_row['session_id'], 'closed', handoff_reason='Pagamento confirmado')
        try:
            log_chat_message(session_row['session_id'], 'outbound', _build_customer_confirmation_message(result), business_id=business_id)
        except Exception:
            pass
    notify_result = _notify_customer_payment_confirmed(result)
    return {'item': result, 'finance_transaction_id': finance_transaction_id, 'confirmed_by': actor_name, 'customer_notify': notify_result}


def update_reservation(business_id: int, reservation_id: int, **fields):
    allowed = {
        'guest_name', 'guest_phone', 'checkin_date', 'checkout_date', 'guest_count', 'unit_category', 'quoted_amount',
        'status', 'payment_status', 'notes', 'source', 'external_reservation_id', 'sync_status', 'reservation_code',
        'professional_status', 'total_value', 'notes_internal', 'main_guest_name', 'main_guest_phone', 'guest_document',
        'guest_email', 'guest_city', 'car_plate', 'estimated_arrival', 'guest_list_json'
    }
    payload = {k: v for k, v in fields.items() if k in allowed and v is not None}
    guests = fields.get('guests')
    if 'source' in payload:
        payload['source'] = _normalize_reservation_source(payload['source'])
    if 'professional_status' in payload or 'status' in payload or 'payment_status' in fields:
        payload['professional_status'] = _normalize_reservation_status(payload.get('professional_status') or payload.get('status'), fields.get('payment_status') or payload.get('payment_status'))
    conn = conectar(); cur = conn.cursor()
    cur.execute("SELECT * FROM reservation_requests WHERE id = ? AND business_id = ? LIMIT 1", (reservation_id, business_id))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise ValueError('Reserva não encontrada.')
    current = dict(row)
    if not payload.get('reservation_code'):
        payload['reservation_code'] = current.get('reservation_code') or _generate_reservation_code()
    if 'total_value' not in payload:
        payload['total_value'] = fields.get('quoted_amount', current.get('total_value') or current.get('quoted_amount') or 0)
    if guests is not None:
        payload['guest_list_json'] = _serialize_guests(guests)
    parts = [f"{k} = ?" for k in payload]
    values = list(payload.values())
    if parts:
        cur.execute(f"UPDATE reservation_requests SET {', '.join(parts)}, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND business_id = ?", tuple(values + [reservation_id, business_id]))
    _replace_reservation_guests(cur, reservation_id, payload.get('main_guest_name', current.get('main_guest_name') or current.get('guest_name')), payload.get('main_guest_phone', current.get('main_guest_phone') or current.get('guest_phone')), payload.get('guest_email', current.get('guest_email')), guests=guests if guests is not None else _deserialize_guests(payload.get('guest_list_json') or current.get('guest_list_json')), cpf=payload.get('guest_document', current.get('guest_document')), city=payload.get('guest_city', current.get('guest_city')), car_plate=payload.get('car_plate', current.get('car_plate')))
    conn.commit()
    cur.execute("SELECT * FROM reservation_requests WHERE id = ?", (reservation_id,))
    item = _enrich_reservation(dict(cur.fetchone()), cur)
    conn.close()
    return item


def cancel_reservation(business_id: int, reservation_id: int, reason: str | None = None):
    return update_reservation(business_id, reservation_id, status='cancelada', professional_status='cancelada', payment_status='cancelado' if reason else None, notes_internal=reason)


def get_reservations_calendar(business_id: int, start_date: str | None = None, end_date: str | None = None):
    conn = conectar()
    cur = conn.cursor()

    today = date.today()
    start = date.fromisoformat(start_date) if start_date else today.replace(day=1)
    end = date.fromisoformat(end_date) if end_date else (start + timedelta(days=30))

    ensure_sample_units_for_hospitality(business_id)

    cur.execute(
        """
        SELECT
            id,
            code,
            name,
            category,
            capacity,
            base_rate,
            quantity_total,
            active
        FROM accommodation_units
        WHERE business_id = ?
        ORDER BY sort_order ASC, name ASC, id ASC
        """,
        (business_id,),
    )
    rooms = [dict(r) for r in cur.fetchall()]

    cur.execute(
        """
        SELECT
            id, business_id, session_id, guest_name, guest_phone, checkin_date, checkout_date, guest_count,
            unit_category, quoted_amount, status, payment_status, payment_reference, human_confirmation_required,
            notes, finance_transaction_id, source, external_reservation_id, sync_status, created_at, updated_at,
            reservation_code, professional_status, total_value, notes_internal, main_guest_name, main_guest_phone,
            guest_document, guest_email, guest_city, car_plate, estimated_arrival, guest_list_json
        FROM reservation_requests
        WHERE business_id = ?
          AND date(checkin_date) <= date(?)
          AND date(checkout_date) >= date(?)
        ORDER BY date(checkin_date) ASC, id ASC
        """,
        (business_id, end.isoformat(), start.isoformat()),
    )
    reservation_rows = cur.fetchall()

    items = []
    for row in reservation_rows:
        item = _enrich_reservation(dict(row), cur)

        unit_category = (item.get("unit_category") or "").strip()
        matched_room = next(
            (
                room for room in rooms
                if unit_category in {
                    str(room.get("code") or "").strip(),
                    str(room.get("name") or "").strip(),
                    str(room.get("category") or "").strip(),
                }
            ),
            None,
        )

        items.append({
            "id": item["id"],
            "reservation_code": item.get("reservation_code"),
            "room_id": matched_room.get("id") if matched_room else None,
            "room_code": matched_room.get("code") if matched_room else None,
            "room_name": matched_room.get("name") if matched_room else (item.get("unit_category") or "Sem tipologia"),
            "room_label": matched_room.get("name") if matched_room else (item.get("unit_category") or "Sem tipologia"),
            "unit_category": item.get("unit_category"),
            "guest_name": item.get("guest_name"),
            "main_guest_name": item.get("main_guest_name"),
            "phone": item.get("main_guest_phone") or item.get("guest_phone"),
            "checkin": item.get("checkin_date"),
            "checkout": item.get("checkout_date"),
            "status": item.get("professional_status") or item.get("status"),
            "calendar_status": item.get("professional_status") or item.get("status"),
            "payment_status": item.get("payment_status"),
            "total_value": item.get("total_value") or item.get("quoted_amount") or 0,
            "notes_internal": item.get("notes_internal"),
            "source": item.get("source"),
            "guests": item.get("guests", []),
            "reservation": item,
        })

    conn.close()

    return {
        "range": {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "count": len(items),
        "rooms": rooms,
        "items": items,
    }


def _count_reservations_by_state(business_id: int, unit_category: str | None = None):
    conn = conectar(); cur = conn.cursor()
    query = """
        SELECT
            SUM(CASE WHEN status = 'confirmada' THEN 1 ELSE 0 END) AS confirmed_total,
            SUM(CASE WHEN payment_status IN ('aguardando_pagamento', 'pending_confirmation') OR status IN ('lead','quoted') THEN 1 ELSE 0 END) AS pending_total,
            SUM(CASE WHEN status = 'bloqueada' THEN 1 ELSE 0 END) AS blocked_total
        FROM reservation_requests
        WHERE business_id = ?
    """
    params: list[object] = [business_id]
    if unit_category:
        query += " AND upper(unit_category) = ?"
        params.append(unit_category.upper())
    cur.execute(query, tuple(params))
    row = dict(cur.fetchone() or {})
    conn.close()
    return {
        'confirmed_total': int(row.get('confirmed_total') or 0),
        'pending_total': int(row.get('pending_total') or 0),
        'blocked_total': int(row.get('blocked_total') or 0),
    }


def inventory_snapshot(business_id: int):
    items = []
    for room in list_room_types(business_id):
        total = int(room.get('quantity_total') or 0)
        counts = _count_reservations_by_state(business_id, room.get('code'))
        confirmed = min(total, counts['confirmed_total'])
        pending = max(0, min(total - confirmed, counts['pending_total']))
        blocked = max(0, min(total - confirmed - pending, counts['blocked_total']))
        unavailable = min(total, confirmed + pending + blocked)
        items.append({
            'code': room['code'], 'name': room['name'], 'total': total,
            'occupied_estimate': confirmed, 'pending_estimate': pending, 'blocked_estimate': blocked,
            'available_estimate': max(0, total - unavailable),
            'capacity': int(room.get('capacity') or 0), 'bed_setup': room.get('bed_setup') or '-',
            'effective_rate': get_effective_rate(business_id, room['code'], room.get('base_rate') or 0),
        })
    return items


def obter_hospitality_summary(business_id: int):
    ensure_sample_units_for_hospitality(business_id)
    conn = conectar(); cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*) AS total_conversas,
               SUM(CASE WHEN status = 'human_active' THEN 1 ELSE 0 END) AS em_humano,
               SUM(CASE WHEN status = 'bot_active' THEN 1 ELSE 0 END) AS em_bot
        FROM chat_sessions WHERE business_id = ?
    """, (business_id,))
    chats = dict(cur.fetchone())
    cur.execute("""
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN status IN ('lead','quoted') THEN 1 ELSE 0 END) AS leads_abertos,
               SUM(CASE WHEN payment_status IN ('aguardando_pagamento', 'pending_confirmation') THEN 1 ELSE 0 END) AS pagamentos_pendentes,
               SUM(CASE WHEN status = 'confirmada' THEN COALESCE(quoted_amount, 0) ELSE 0 END) AS receita_confirmada
        FROM reservation_requests WHERE business_id = ?
    """, (business_id,))
    reservas = dict(cur.fetchone())
    cur.execute("SELECT COUNT(*) AS tipos, COALESCE(SUM(quantity_total),0) AS unidades, SUM(CASE WHEN active = 1 THEN 1 ELSE 0 END) AS tipos_ativos FROM accommodation_units WHERE business_id = ?", (business_id,))
    inventario = dict(cur.fetchone())
    cur.execute("SELECT id, customer_phone, customer_name, status, assigned_to_name, last_customer_message, last_message_at FROM chat_sessions WHERE business_id = ? ORDER BY datetime(last_message_at) DESC, id DESC LIMIT 8", (business_id,)); inbox = [dict(r) for r in cur.fetchall()]
    cur.execute("SELECT id, guest_name, guest_phone, checkin_date, checkout_date, guest_count, unit_category, quoted_amount, status, payment_status, updated_at FROM reservation_requests WHERE business_id = ? ORDER BY datetime(updated_at) DESC, id DESC LIMIT 8", (business_id,)); recent = [dict(r) for r in cur.fetchall()]
    conn.close()
    return {'conversas': chats, 'reservas': reservas, 'inventario': inventario, 'inbox_recente': inbox, 'reservas_recentes': recent, 'settings': get_bot_settings(business_id), 'inventory_snapshot': inventory_snapshot(business_id), 'manual_rates': list_manual_rates(business_id)}


def summarize_hospitality_operations(business_id: int):
    return {'recent_sessions': listar_chat_sessions(business_id), 'recent_reservations': listar_reservas(business_id), 'inventory': inventory_snapshot(business_id)}


def list_admin_contacts(business_id: int):
    conn = conectar(); cur = conn.cursor()
    contacts = []
    seen = set()
    cur.execute("""
        SELECT telefone, nome, role FROM business_contacts
        WHERE business_id = ? AND ativo = 1
        ORDER BY CASE WHEN role IN ('admin','gerente','owner') THEN 0 ELSE 1 END, id ASC
    """, (business_id,))
    for row in cur.fetchall():
        item = dict(row)
        phone = item.get('telefone')
        if phone and phone not in seen:
            seen.add(phone)
            contacts.append(item)
    cur.execute("SELECT legacy_restaurant_id FROM businesses WHERE id = ? LIMIT 1", (business_id,))
    business = cur.fetchone()
    if business and business['legacy_restaurant_id']:
        cur.execute("""
            SELECT telefone, nome, role FROM restaurant_users
            WHERE restaurant_id = ? AND ativo = 1
            ORDER BY CASE WHEN role IN ('admin','gerente','owner') THEN 0 ELSE 1 END, id ASC
        """, (business['legacy_restaurant_id'],))
        for row in cur.fetchall():
            item = dict(row)
            phone = item.get('telefone')
            if phone and phone not in seen:
                seen.add(phone)
                contacts.append(item)
    settings = get_bot_settings(business_id) or {}
    extra = settings.get('payment_alert_phones')
    if extra:
        for raw in str(extra).replace(';', ',').split(','):
            phone = raw.strip()
            if phone and phone not in seen:
                seen.add(phone)
                contacts.append({'telefone': phone, 'nome': 'Alerta', 'role': 'admin'})
    conn.close(); return contacts


def get_primary_admin_contact(business_id: int):
    contacts = list_admin_contacts(business_id)
    return contacts[0] if contacts else None


def list_pending_payment_confirmations(business_id: int):
    conn = conectar(); cur = conn.cursor()
    cur.execute(
        """
        SELECT id, guest_name, guest_phone, checkin_date, checkout_date, guest_count,
               unit_category, quoted_amount, status, payment_status, payment_reference,
               notes, source, sync_status, updated_at
        FROM reservation_requests
        WHERE business_id = ? AND payment_status = 'pending_confirmation'
        ORDER BY datetime(updated_at) DESC, id DESC
        """,
        (business_id,),
    )
    items = [dict(r) for r in cur.fetchall()]
    conn.close()
    return items


def _find_latest_customer_reservation(business_id: int, phone: str, session_id: int | None = None):
    conn = conectar(); cur = conn.cursor()
    if session_id is not None:
        cur.execute(
            """
            SELECT * FROM reservation_requests
            WHERE business_id = ? AND session_id = ?
            ORDER BY id DESC LIMIT 1
            """,
            (business_id, session_id),
        )
    else:
        cur.execute(
            """
            SELECT * FROM reservation_requests
            WHERE business_id = ? AND guest_phone = ?
            ORDER BY id DESC LIMIT 1
            """,
            (business_id, phone),
        )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def notify_admin_payment_pending(business_id: int, reservation: dict, customer_name: str | None = None):
    contacts = [c for c in list_admin_contacts(business_id) if c.get('telefone') and c.get('telefone') != reservation.get('guest_phone')]
    if not contacts:
        return None
    amount = float(reservation.get('quoted_amount') or 0)
    guest_label = customer_name or reservation.get('guest_name') or reservation.get('guest_phone')
    lines = [
        '🚨 Comprovante recebido e aguardando confirmação.',
        f"Cliente: {guest_label}",
    ]
    if reservation.get('checkin_date') or reservation.get('checkout_date'):
        lines.append(f"Período: {reservation.get('checkin_date') or '-'} até {reservation.get('checkout_date') or '-'}")
    if reservation.get('unit_category'):
        lines.append(f"Quarto: {reservation.get('unit_category')}")
    if amount:
        lines.append(f"Valor: R$ {amount:.2f}")
    lines.append(f"Telefone: {reservation.get('guest_phone')}")
    lines.append('Ação: confirme pelo painel ou use /pendentes e /confirmar pagamento TELEFONE no WhatsApp admin.')
    message = "\n".join(lines)
    responses = []
    for contact in contacts:
        try:
            responses.append({'phone': contact['telefone'], 'response': enviar_mensagem_texto(message, contact['telefone'])})
        except Exception as exc:
            responses.append({'phone': contact['telefone'], 'error': str(exc)})
    return responses


def mark_reservation_payment_pending_confirmation(business_id: int, guest_phone: str, proof_note: str | None = None, session_id: int | None = None, customer_name: str | None = None):
    reservation = _find_latest_customer_reservation(business_id, guest_phone, session_id=session_id)
    if not reservation:
        return None
    conn = conectar(); cur = conn.cursor()
    note_suffix = proof_note or 'Comprovante recebido via WhatsApp e aguardando confirmação humana.'
    cur.execute(
        """
        UPDATE reservation_requests
        SET payment_status = 'pending_confirmation',
            status = CASE WHEN status = 'lead' THEN 'quoted' ELSE status END,
            notes = TRIM(COALESCE(notes, '') || '
' || ?),
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (note_suffix, reservation['id']),
    )
    cur.execute(
        """
        UPDATE payment_requests
        SET status = 'pending_confirmation', updated_at = CURRENT_TIMESTAMP
        WHERE reservation_request_id = ?
        """,
        (reservation['id'],),
    )
    if cur.rowcount == 0 and reservation.get('quoted_amount'):
        settings = get_bot_settings(business_id) or {}
        cur.execute(
            """
            INSERT INTO payment_requests (
                business_id, reservation_request_id, amount, payment_method, payment_key, payment_link, status
            ) VALUES (?, ?, ?, 'pix', ?, ?, 'pending_confirmation')
            """,
            (business_id, reservation['id'], reservation.get('quoted_amount'), settings.get('pix_key'), settings.get('payment_link_base')),
        )
    conn.commit()
    cur.execute("SELECT * FROM reservation_requests WHERE id = ?", (reservation['id'],))
    updated = dict(cur.fetchone())
    conn.close()
    notify_admin_payment_pending(business_id, updated, customer_name=customer_name)
    if session_id:
        update_chat_session_status(session_id, 'awaiting_payment_confirmation', handoff_reason='Comprovante recebido e aguardando conferência humana')
    return updated




def update_transaction(restaurant_id: int, transaction_id: int, **fields):
    allowed = {'tipo', 'categoria', 'valor', 'descricao'}
    payload = {k: v for k, v in fields.items() if k in allowed}
    if not payload:
        return None
    conn = conectar(); cur = conn.cursor()
    cur.execute("SELECT * FROM transacoes WHERE id = ? AND restaurant_id = ? LIMIT 1", (transaction_id, restaurant_id))
    row = cur.fetchone()
    if not row:
        conn.close(); return None
    parts = [f"{k} = ?" for k in payload]
    params = list(payload.values()) + [transaction_id, restaurant_id]
    cur.execute(f"UPDATE transacoes SET {', '.join(parts)} WHERE id = ? AND restaurant_id = ?", tuple(params))
    conn.commit(); cur.execute("SELECT * FROM transacoes WHERE id = ?", (transaction_id,)); item = dict(cur.fetchone()); conn.close(); return item


def delete_transaction(restaurant_id: int, transaction_id: int):
    conn = conectar(); cur = conn.cursor()
    cur.execute("SELECT * FROM transacoes WHERE id = ? AND restaurant_id = ? LIMIT 1", (transaction_id, restaurant_id))
    row = cur.fetchone()
    if not row:
        conn.close(); return None
    item = dict(row)
    cur.execute("DELETE FROM transacoes WHERE id = ? AND restaurant_id = ?", (transaction_id, restaurant_id))
    conn.commit(); conn.close(); return item

def should_prompt_for_rates(business_id: int):
    settings = get_bot_settings(business_id) or {}
    if settings.get('hospitality_mode') != 'manual_rates':
        return False
    now = datetime.now()
    collection_time = settings.get('rate_collection_time') or '08:00'
    try:
        hour, minute = [int(x) for x in collection_time.split(':')[:2]]
    except Exception:
        hour, minute = 8, 0
    if now.hour != hour or now.minute != minute:
        return False
    last_prompt = settings.get('last_rate_prompt_at')
    if last_prompt and str(last_prompt).startswith(now.strftime('%Y-%m-%d')):
        return False
    frequency = settings.get('rate_collection_frequency') or 'daily'
    active_rates = list_manual_rates(business_id)
    if frequency == 'weekly' and active_rates:
        valid_until_values = [datetime.fromisoformat(item['valid_until']) for item in active_rates if item.get('valid_until')]
        if valid_until_values and min(valid_until_values) > now:
            return False
    return True


def build_rate_prompt_message(business_id: int):
    room_lines = [f"- {item['code']}: informe o valor" for item in list_room_types(business_id)]
    return (
        'Bom dia! Vamos atualizar as tarifas da hospedagem.\n\n'
        + '\n'.join(room_lines)
        + '\n\nResponda por exemplo:\n/tarifas semana STD-CASAL 320, FAMILIA 420\nou\n/tarifas hoje STD-CASAL 280, FAMILIA 380'
    )


def prompt_daily_rates_if_needed():
    conn = conectar(); cur = conn.cursor(); cur.execute("SELECT business_id FROM bot_settings WHERE hospitality_mode = 'manual_rates'"); business_ids = [r['business_id'] for r in cur.fetchall()]; conn.close()
    sent = 0
    for business_id in business_ids:
        if not should_prompt_for_rates(business_id):
            continue
        contact = get_primary_admin_contact(business_id)
        if not contact:
            continue
        text = build_rate_prompt_message(business_id)
        enviar_mensagem_texto(text, contact['telefone'])
        upsert_bot_settings(business_id, last_rate_prompt_at=_now_iso())
        sent += 1
    return sent
