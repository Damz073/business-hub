import json
from typing import Optional

from app.database import conectar
from app.module_registry import get_module_manifest, list_module_manifests, normalize_business_type


def get_business_by_legacy_restaurant_id(restaurant_id: int):
    conn = conectar()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, legacy_restaurant_id, nome, slug, business_type, status, plano, vencimento,
               metadata_json, created_at, updated_at
        FROM businesses
        WHERE legacy_restaurant_id = ?
        LIMIT 1
        """,
        (restaurant_id,),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_business_by_contact_phone(phone: str):
    conn = conectar()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT b.*, bc.nome AS contact_name, bc.role AS contact_role, bc.telefone AS contact_phone
        FROM business_contacts bc
        JOIN businesses b ON b.id = bc.business_id
        WHERE bc.telefone = ? AND bc.ativo = 1
        LIMIT 1
        """,
        (phone,),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def ensure_chat_session(business_id: int, customer_phone: str, customer_name: Optional[str] = None, channel: str = 'whatsapp'):
    conn = conectar()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT * FROM chat_sessions
        WHERE business_id = ? AND customer_phone = ? AND channel = ?
        LIMIT 1
        """,
        (business_id, customer_phone, channel),
    )
    row = cur.fetchone()
    if row:
        if customer_name:
            cur.execute(
                """
                UPDATE chat_sessions
                SET customer_name = COALESCE(?, customer_name), updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (customer_name, row['id']),
            )
            conn.commit()
            cur.execute("SELECT * FROM chat_sessions WHERE id = ?", (row['id'],))
            row = cur.fetchone()
        conn.close()
        upsert_customer_profile(business_id, customer_phone, customer_name, channel=channel)
        return dict(row)

    cur.execute(
        """
        INSERT INTO chat_sessions (business_id, customer_phone, customer_name, channel)
        VALUES (?, ?, ?, ?)
        """,
        (business_id, customer_phone, customer_name, channel),
    )
    session_id = cur.lastrowid
    conn.commit()
    cur.execute("SELECT * FROM chat_sessions WHERE id = ?", (session_id,))
    created = cur.fetchone()
    conn.close()
    upsert_customer_profile(business_id, customer_phone, customer_name, channel=channel)
    return dict(created)


def session_business_id(session_id: int) -> int | None:
    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT business_id FROM chat_sessions WHERE id = ? LIMIT 1", (session_id,))
    row = cur.fetchone()
    conn.close()
    return int(row['business_id']) if row else None


def log_chat_message(
    session_id: int,
    direction: str,
    sender_type: str,
    sender_phone: Optional[str],
    message_type: str,
    text_content: Optional[str],
    payload: Optional[dict] = None,
):
    conn = conectar()
    cur = conn.cursor()
    payload_json = json.dumps(payload, ensure_ascii=False) if payload is not None else None
    cur.execute(
        """
        INSERT INTO chat_messages (
            session_id, direction, sender_type, sender_phone, message_type, text_content, payload_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (session_id, direction, sender_type, sender_phone, message_type, text_content, payload_json),
    )

    if direction == 'inbound':
        cur.execute(
            """
            UPDATE chat_sessions
            SET last_message_at = CURRENT_TIMESTAMP,
                last_customer_message = COALESCE(?, last_customer_message),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (text_content, session_id),
        )
    else:
        cur.execute(
            """
            UPDATE chat_sessions
            SET last_message_at = CURRENT_TIMESTAMP,
                last_bot_message = COALESCE(?, last_bot_message),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (text_content, session_id),
        )

    conn.commit()
    conn.close()
    # mantém o CRM universal alinhado ao inbox
    try:
        if sender_phone:
            upsert_customer_profile(session_business_id(session_id), sender_phone, None)
    except Exception:
        pass


def update_chat_session_status(session_id: int, status: str, assigned_to_phone: str | None = None,
                               assigned_to_name: str | None = None, handoff_reason: str | None = None):
    conn = conectar()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE chat_sessions
        SET status = ?,
            assigned_to_phone = ?,
            assigned_to_name = ?,
            handoff_reason = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (status, assigned_to_phone, assigned_to_name, handoff_reason, session_id),
    )
    conn.commit()
    conn.close()


def get_bot_settings(business_id: int):
    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT * FROM bot_settings WHERE business_id = ? LIMIT 1", (business_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def upsert_bot_settings(business_id: int, **fields):
    current = get_bot_settings(business_id)
    if not current:
        conn = conectar()
        cur = conn.cursor()
        cur.execute("INSERT INTO bot_settings (business_id) VALUES (?)", (business_id,))
        conn.commit()
        conn.close()
        current = get_bot_settings(business_id)

    allowed = {
        'assistant_name', 'welcome_message', 'fallback_message', 'pix_key', 'payment_link_base',
        'human_handoff_enabled', 'auto_reply_enabled', 'reservations_module_enabled', 'finance_module_enabled',
        'whatsapp_phone_number_id', 'whatsapp_business_account_id', 'whatsapp_verify_token',
        'checkin_time', 'checkout_time', 'reservation_payment_instructions',
        'hospitality_mode', 'rate_collection_frequency', 'rate_collection_time', 'last_rate_prompt_at',
        'external_system_type', 'omnibees_hotel_id', 'omnibees_sync_enabled',
        'location_text', 'maps_link', 'pool_info', 'garage_info', 'breakfast_info', 'pet_policy', 'amenities_text',
        'fiscal_company_name', 'fiscal_document', 'fiscal_municipal_registration', 'fiscal_service_city', 'fiscal_email',
        'public_business_name', 'public_contact_phone', 'street_address', 'neighborhood', 'city_name', 'state_code', 'payment_alert_phones'
    }
    payload = {k: v for k, v in fields.items() if k in allowed}
    if not payload:
        return get_bot_settings(business_id)

    parts = [f"{key} = ?" for key in payload]
    params = list(payload.values())
    params.append(business_id)

    conn = conectar()
    cur = conn.cursor()
    cur.execute(
        f"UPDATE bot_settings SET {', '.join(parts)}, updated_at = CURRENT_TIMESTAMP WHERE business_id = ?",
        tuple(params),
    )
    conn.commit()
    conn.close()
    return get_bot_settings(business_id)


def upsert_customer_profile(business_id: int, phone: str, name: str | None = None, channel: str = 'whatsapp', customer_type: str = 'lead'):
    conn = conectar()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO customers (business_id, phone, name, channel, customer_type, lifecycle_stage, last_message_at, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, 'new', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT(business_id, phone) DO UPDATE SET
            name = COALESCE(excluded.name, customers.name),
            channel = COALESCE(excluded.channel, customers.channel),
            customer_type = COALESCE(excluded.customer_type, customers.customer_type),
            last_message_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        """,
        (business_id, phone, name, channel, customer_type),
    )
    conn.commit()
    cur.execute("SELECT * FROM customers WHERE business_id = ? AND phone = ? LIMIT 1", (business_id, phone))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def list_business_customers(business_id: int, limit: int = 200):
    conn = conectar()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, business_id, phone, name, channel, customer_type, lifecycle_stage,
               last_message_at, last_reservation_at, total_revenue, tags_json, notes, created_at, updated_at
        FROM customers
        WHERE business_id = ?
        ORDER BY datetime(COALESCE(last_message_at, updated_at)) DESC, id DESC
        LIMIT ?
        """,
        (business_id, max(1, min(limit, 500))),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_subscription_for_business(business_id: int):
    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT * FROM subscriptions WHERE business_id = ? LIMIT 1", (business_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def list_enabled_modules_for_business(business_id: int):
    conn = conectar()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT module_key, enabled, config_json, created_at, updated_at
        FROM business_modules
        WHERE business_id = ?
        ORDER BY module_key ASC
        """,
        (business_id,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def toggle_business_module(business_id: int, module_key: str, enabled: bool):
    conn = conectar()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO business_modules (business_id, module_key, enabled, created_at, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT(business_id, module_key) DO UPDATE SET enabled = excluded.enabled, updated_at = CURRENT_TIMESTAMP
        """,
        (business_id, module_key, 1 if enabled else 0),
    )
    conn.commit()
    conn.close()
    return list_enabled_modules_for_business(business_id)


def get_business_profile(business_id: int):
    conn = conectar()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, legacy_restaurant_id, nome, slug, business_type, status, plano, vencimento, metadata_json, created_at, updated_at
        FROM businesses
        WHERE id = ? LIMIT 1
        """,
        (business_id,),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    item = dict(row)
    item['manifest'] = get_module_manifest(item.get('business_type'))
    item['available_modules'] = list_module_manifests()
    item['enabled_modules'] = list_enabled_modules_for_business(business_id)
    item['subscription'] = get_subscription_for_business(business_id)
    return item


def get_core_overview(business_id: int):
    profile = get_business_profile(business_id)
    conn = conectar()
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) AS total FROM chat_sessions WHERE business_id = ?', (business_id,))
    conversations = int(cur.fetchone()['total'])
    cur.execute('SELECT COUNT(*) AS total FROM customers WHERE business_id = ?', (business_id,))
    customers = int(cur.fetchone()['total'])
    cur.execute('SELECT COUNT(*) AS total FROM reservation_requests WHERE business_id = ?', (business_id,))
    reservations = int(cur.fetchone()['total'])
    cur.execute('SELECT COUNT(*) AS total FROM web_users WHERE business_id = ?', (business_id,))
    users = int(cur.fetchone()['total'])
    conn.close()
    return {
        'profile': profile,
        'metrics': {
            'conversations': conversations,
            'customers': customers,
            'reservations': reservations,
            'team_members': users,
        },
        'growth_stage': 'foundation',
        'saas_mode': 'vertical_plus_core',
    }
