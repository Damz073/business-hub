import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "banco.db"


def conectar():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _garantir_coluna(cursor, tabela: str, coluna: str, definicao: str):
    cursor.execute(f"PRAGMA table_info({tabela})")
    colunas = [row[1] for row in cursor.fetchall()]
    if coluna not in colunas:
        cursor.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {definicao}")


def _criar_tabelas_legadas(cursor):
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS platform_admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT,
        telefone TEXT NOT NULL UNIQUE,
        ativo INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS restaurants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        status TEXT DEFAULT 'ativo',
        plano TEXT DEFAULT 'basico',
        vencimento TEXT
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS restaurant_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        restaurant_id INTEGER NOT NULL,
        telefone TEXT NOT NULL UNIQUE,
        nome TEXT,
        role TEXT DEFAULT 'operador',
        ativo INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transacoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        restaurant_id INTEGER NOT NULL,
        tipo TEXT NOT NULL,
        categoria TEXT NOT NULL,
        valor REAL NOT NULL,
        descricao TEXT,
        criado_em TEXT DEFAULT CURRENT_TIMESTAMP,
        receipt_id INTEGER,
        merchant_id INTEGER
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS merchants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        restaurant_id INTEGER NOT NULL,
        nome TEXT NOT NULL,
        nome_normalizado TEXT,
        categoria_default TEXT,
        ocorrencias INTEGER DEFAULT 0,
        ativo INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS web_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        restaurant_id INTEGER NOT NULL,
        business_id INTEGER,
        name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        role TEXT DEFAULT 'admin',
        active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS receipts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        restaurant_id INTEGER NOT NULL,
        telefone TEXT,
        image_path TEXT,
        media_id TEXT,
        merchant_id INTEGER,
        merchant_name TEXT,
        ocr_text TEXT,
        ocr_text_top TEXT,
        ocr_text_total TEXT,
        valor_total REAL,
        data_comprovante TEXT,
        categoria_sugerida TEXT,
        categoria_confirmada TEXT,
        status TEXT,
        transaction_id INTEGER,
        confirmed_at TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)
    for t, c, d in [
        ('platform_admins', 'ativo', 'INTEGER DEFAULT 1'),
        ('restaurant_users', 'ativo', 'INTEGER DEFAULT 1'),
        ('restaurant_users', 'created_at', 'TEXT DEFAULT CURRENT_TIMESTAMP'),
        ('transacoes', 'receipt_id', 'INTEGER'),
        ('transacoes', 'merchant_id', 'INTEGER'),
        ('merchants', 'nome_normalizado', 'TEXT'),
        ('merchants', 'categoria_default', 'TEXT'),
        ('merchants', 'ocorrencias', 'INTEGER DEFAULT 0'),
        ('merchants', 'ativo', 'INTEGER DEFAULT 1'),
        ('merchants', 'created_at', 'TEXT DEFAULT CURRENT_TIMESTAMP'),
        ('merchants', 'updated_at', 'TEXT DEFAULT CURRENT_TIMESTAMP'),
        ('receipts', 'telefone', 'TEXT'),
        ('receipts', 'media_id', 'TEXT'),
        ('receipts', 'merchant_id', 'INTEGER'),
        ('receipts', 'merchant_name', 'TEXT'),
        ('receipts', 'ocr_text', 'TEXT'),
        ('receipts', 'ocr_text_top', 'TEXT'),
        ('receipts', 'ocr_text_total', 'TEXT'),
        ('receipts', 'valor_total', 'REAL'),
        ('receipts', 'data_comprovante', 'TEXT'),
        ('receipts', 'categoria_sugerida', 'TEXT'),
        ('receipts', 'categoria_confirmada', 'TEXT'),
        ('receipts', 'status', 'TEXT'),
        ('receipts', 'transaction_id', 'INTEGER'),
        ('receipts', 'confirmed_at', 'TEXT'),
        ('receipts', 'created_at', 'TEXT DEFAULT CURRENT_TIMESTAMP'),
        ('web_users', 'role', "TEXT DEFAULT 'admin'"),
        ('web_users', 'active', 'INTEGER DEFAULT 1'),
        ('web_users', 'created_at', 'TEXT DEFAULT CURRENT_TIMESTAMP'),
        ('web_users', 'business_id', 'INTEGER'),
    ]:
        _garantir_coluna(cursor, t, c, d)


def _criar_tabelas_core(cursor):
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS businesses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        legacy_restaurant_id INTEGER UNIQUE,
        nome TEXT NOT NULL,
        slug TEXT,
        business_type TEXT DEFAULT 'restaurant',
        status TEXT DEFAULT 'ativo',
        plano TEXT DEFAULT 'basico',
        vencimento TEXT,
        metadata_json TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS business_contacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        business_id INTEGER NOT NULL,
        legacy_restaurant_user_id INTEGER,
        telefone TEXT NOT NULL,
        nome TEXT,
        role TEXT DEFAULT 'operador',
        channel TEXT DEFAULT 'whatsapp',
        ativo INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(business_id, telefone)
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        business_id INTEGER NOT NULL,
        customer_phone TEXT NOT NULL,
        customer_name TEXT,
        channel TEXT DEFAULT 'whatsapp',
        last_message_at TEXT DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'bot_active',
        assigned_to_phone TEXT,
        assigned_to_name TEXT,
        handoff_reason TEXT,
        last_customer_message TEXT,
        last_bot_message TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(business_id, customer_phone, channel)
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL,
        direction TEXT NOT NULL,
        sender_type TEXT NOT NULL,
        sender_phone TEXT,
        message_type TEXT DEFAULT 'text',
        text_content TEXT,
        payload_json TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS accommodation_units (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        business_id INTEGER NOT NULL,
        code TEXT,
        name TEXT NOT NULL,
        category TEXT,
        capacity INTEGER DEFAULT 2,
        base_rate REAL DEFAULT 0,
        active INTEGER DEFAULT 1,
        notes TEXT,
        quantity_total INTEGER DEFAULT 1,
        bed_setup TEXT,
        max_adults INTEGER DEFAULT 2,
        max_children INTEGER DEFAULT 0,
        sort_order INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)
    for c, d in [
        ('quantity_total', 'INTEGER DEFAULT 1'),
        ('bed_setup', 'TEXT'),
        ('max_adults', 'INTEGER DEFAULT 2'),
        ('max_children', 'INTEGER DEFAULT 0'),
        ('sort_order', 'INTEGER DEFAULT 1'),
    ]:
        _garantir_coluna(cursor, 'accommodation_units', c, d)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reservation_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        business_id INTEGER NOT NULL,
        session_id INTEGER,
        guest_name TEXT,
        guest_phone TEXT NOT NULL,
        checkin_date TEXT,
        checkout_date TEXT,
        guest_count INTEGER,
        unit_category TEXT,
        quoted_amount REAL,
        status TEXT DEFAULT 'lead',
        payment_status TEXT DEFAULT 'nao_enviado',
        payment_reference TEXT,
        human_confirmation_required INTEGER DEFAULT 1,
        finance_transaction_id INTEGER,
        source TEXT DEFAULT 'panel',
        external_reservation_id TEXT,
        sync_status TEXT DEFAULT 'not_synced',
        notes TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)
    for c, d in [
        ('finance_transaction_id', 'INTEGER'),
        ('source', "TEXT DEFAULT 'panel'"),
        ('external_reservation_id', 'TEXT'),
        ('sync_status', "TEXT DEFAULT 'not_synced'"),
        ('reservation_code', 'TEXT'),
        ('professional_status', "TEXT DEFAULT 'lead'"),
        ('total_value', 'REAL'),
        ('notes_internal', 'TEXT'),
        ('main_guest_name', 'TEXT'),
        ('main_guest_phone', 'TEXT'),
        ('guest_document', 'TEXT'),
        ('guest_email', 'TEXT'),
        ('guest_city', 'TEXT'),
        ('car_plate', 'TEXT'),
        ('estimated_arrival', 'TEXT'),
        ('guest_list_json', 'TEXT'),
    ]:
        _garantir_coluna(cursor, 'reservation_requests', c, d)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reservation_guests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reservation_request_id INTEGER NOT NULL,
        name TEXT,
        cpf TEXT,
        phone TEXT,
        email TEXT,
        city TEXT,
        car_plate TEXT,
        is_main INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS payment_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        business_id INTEGER NOT NULL,
        reservation_request_id INTEGER,
        amount REAL NOT NULL,
        payment_method TEXT DEFAULT 'pix',
        payment_key TEXT,
        payment_link TEXT,
        status TEXT DEFAULT 'pending_confirmation',
        proof_receipt_id INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bot_settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        business_id INTEGER NOT NULL UNIQUE,
        assistant_name TEXT DEFAULT 'Assistente Virtual',
        welcome_message TEXT,
        fallback_message TEXT,
        pix_key TEXT,
        payment_link_base TEXT,
        human_handoff_enabled INTEGER DEFAULT 1,
        auto_reply_enabled INTEGER DEFAULT 1,
        reservations_module_enabled INTEGER DEFAULT 0,
        finance_module_enabled INTEGER DEFAULT 1,
        whatsapp_phone_number_id TEXT,
        whatsapp_business_account_id TEXT,
        whatsapp_verify_token TEXT,
        checkin_time TEXT DEFAULT '14:00',
        checkout_time TEXT DEFAULT '12:00',
        reservation_payment_instructions TEXT,
        hospitality_mode TEXT DEFAULT 'manual_rates',
        rate_collection_frequency TEXT DEFAULT 'daily',
        rate_collection_time TEXT DEFAULT '08:00',
        last_rate_prompt_at TEXT,
        external_system_type TEXT,
        omnibees_hotel_id TEXT,
        omnibees_sync_enabled INTEGER DEFAULT 0,
        location_text TEXT,
        maps_link TEXT,
        pool_info TEXT,
        garage_info TEXT,
        breakfast_info TEXT,
        pet_policy TEXT,
        amenities_text TEXT,
        fiscal_company_name TEXT,
        fiscal_document TEXT,
        fiscal_municipal_registration TEXT,
        fiscal_service_city TEXT,
        fiscal_email TEXT,
        public_business_name TEXT,
        public_contact_phone TEXT,
        street_address TEXT,
        neighborhood TEXT,
        city_name TEXT,
        state_code TEXT,
        payment_alert_phones TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)
    for c, d in [
        ('whatsapp_phone_number_id', 'TEXT'),
        ('whatsapp_business_account_id', 'TEXT'),
        ('whatsapp_verify_token', 'TEXT'),
        ('checkin_time', "TEXT DEFAULT '14:00'"),
        ('checkout_time', "TEXT DEFAULT '12:00'"),
        ('reservation_payment_instructions', 'TEXT'),
        ('hospitality_mode', "TEXT DEFAULT 'manual_rates'"),
        ('rate_collection_frequency', "TEXT DEFAULT 'daily'"),
        ('rate_collection_time', "TEXT DEFAULT '08:00'"),
        ('last_rate_prompt_at', 'TEXT'),
        ('external_system_type', 'TEXT'),
        ('omnibees_hotel_id', 'TEXT'),
        ('omnibees_sync_enabled', 'INTEGER DEFAULT 0'),
        ('location_text', 'TEXT'),
        ('maps_link', 'TEXT'),
        ('pool_info', 'TEXT'),
        ('garage_info', 'TEXT'),
        ('breakfast_info', 'TEXT'),
        ('pet_policy', 'TEXT'),
        ('amenities_text', 'TEXT'),
        ('fiscal_company_name', 'TEXT'),
        ('fiscal_document', 'TEXT'),
        ('fiscal_municipal_registration', 'TEXT'),
        ('fiscal_service_city', 'TEXT'),
        ('fiscal_email', 'TEXT'),
        ('public_business_name', 'TEXT'),
        ('public_contact_phone', 'TEXT'),
        ('street_address', 'TEXT'),
        ('neighborhood', 'TEXT'),
        ('city_name', 'TEXT'),
        ('state_code', 'TEXT'),
        ('payment_alert_phones', 'TEXT'),
    ]:
        _garantir_coluna(cursor, 'bot_settings', c, d)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS room_rate_overrides (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        business_id INTEGER NOT NULL,
        room_code TEXT NOT NULL,
        rate_value REAL NOT NULL,
        valid_from TEXT NOT NULL,
        valid_until TEXT NOT NULL,
        source TEXT DEFAULT 'manual_admin',
        note TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        business_id INTEGER NOT NULL,
        phone TEXT NOT NULL,
        name TEXT,
        channel TEXT DEFAULT 'whatsapp',
        customer_type TEXT DEFAULT 'lead',
        lifecycle_stage TEXT DEFAULT 'new',
        last_message_at TEXT,
        last_reservation_at TEXT,
        total_revenue REAL DEFAULT 0,
        tags_json TEXT,
        notes TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(business_id, phone)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        business_id INTEGER NOT NULL UNIQUE,
        plan_code TEXT DEFAULT 'starter',
        status TEXT DEFAULT 'trialing',
        trial_ends_at TEXT,
        current_period_end TEXT,
        price_monthly REAL DEFAULT 0,
        seats_limit INTEGER DEFAULT 3,
        metadata_json TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS business_modules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        business_id INTEGER NOT NULL,
        module_key TEXT NOT NULL,
        enabled INTEGER DEFAULT 1,
        config_json TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(business_id, module_key)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS crm_notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        business_id INTEGER NOT NULL,
        customer_id INTEGER NOT NULL,
        author_name TEXT,
        content TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)


def _seed_business_modules(cursor):
    defaults = {
        'hospitality': ['core', 'finance', 'crm', 'inbox', 'hospitality'],
        'restaurant': ['core', 'finance', 'crm', 'inbox', 'restaurant'],
        'beauty': ['core', 'finance', 'crm', 'inbox', 'beauty'],
        'rental': ['core', 'finance', 'crm', 'inbox', 'rental'],
    }
    cursor.execute("SELECT id, business_type FROM businesses")
    businesses = cursor.fetchall()
    for business in businesses:
        modules = defaults.get(business['business_type'] or 'restaurant', defaults['restaurant'])
        for module_key in modules:
            cursor.execute(
                """
                INSERT INTO business_modules (business_id, module_key, enabled, created_at, updated_at)
                SELECT ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                WHERE NOT EXISTS (SELECT 1 FROM business_modules WHERE business_id = ? AND module_key = ?)
                """,
                (business['id'], module_key, business['id'], module_key),
            )


def _sincronizar_businesses(cursor):
    cursor.execute("""
        INSERT INTO businesses (
            legacy_restaurant_id, nome, slug, business_type, status, plano, vencimento, created_at, updated_at
        )
        SELECT r.id, r.nome, lower(replace(replace(r.nome, ' ', '-'), '/', '-')), 'restaurant', r.status, r.plano, r.vencimento,
               CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        FROM restaurants r
        WHERE NOT EXISTS (SELECT 1 FROM businesses b WHERE b.legacy_restaurant_id = r.id)
    """)
    cursor.execute("""
        UPDATE web_users
        SET business_id = (SELECT b.id FROM businesses b WHERE b.legacy_restaurant_id = web_users.restaurant_id)
        WHERE business_id IS NULL AND restaurant_id IS NOT NULL
    """)
    cursor.execute("""
        INSERT INTO business_contacts (
            business_id, legacy_restaurant_user_id, telefone, nome, role, channel, ativo, created_at, updated_at
        )
        SELECT b.id, ru.id, ru.telefone, ru.nome, ru.role, 'whatsapp', ru.ativo, ru.created_at, CURRENT_TIMESTAMP
        FROM restaurant_users ru
        JOIN businesses b ON b.legacy_restaurant_id = ru.restaurant_id
        WHERE NOT EXISTS (SELECT 1 FROM business_contacts bc WHERE bc.business_id = b.id AND bc.telefone = ru.telefone)
    """)
    cursor.execute("""
        INSERT INTO bot_settings (
            business_id, assistant_name, welcome_message, fallback_message,
            human_handoff_enabled, auto_reply_enabled, reservations_module_enabled, finance_module_enabled,
            checkin_time, checkout_time, reservation_payment_instructions,
            hospitality_mode, rate_collection_frequency, rate_collection_time,
            created_at, updated_at
        )
        SELECT b.id,
               CASE WHEN b.business_type = 'hospitality' THEN 'Central de Reservas' ELSE 'Assistente Comercial' END,
               'Olá! Sou a assistente virtual. Posso ajudar com seu atendimento.',
               'Não entendi sua mensagem. Tente reformular ou aguarde um atendente.',
               1, 1,
               CASE WHEN b.business_type = 'hospitality' THEN 1 ELSE 0 END,
               1,
               '14:00', '12:00',
               'Para confirmar a reserva, envie o comprovante Pix e aguarde a validação da equipe.',
               CASE WHEN b.business_type = 'hospitality' THEN 'manual_rates' ELSE 'pms_integrated' END,
               'daily', '08:00',
               CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        FROM businesses b
        WHERE NOT EXISTS (SELECT 1 FROM bot_settings bs WHERE bs.business_id = b.id)
    """)

    cursor.execute("""
        INSERT INTO subscriptions (business_id, plan_code, status, trial_ends_at, current_period_end, price_monthly, seats_limit, created_at, updated_at)
        SELECT b.id,
               CASE WHEN b.business_type = 'hospitality' THEN 'hospitality_starter' ELSE 'starter' END,
               'trialing',
               datetime('now', '+14 day'),
               datetime('now', '+30 day'),
               0,
               3,
               CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        FROM businesses b
        WHERE NOT EXISTS (SELECT 1 FROM subscriptions s WHERE s.business_id = b.id)
    """)

    cursor.execute("""
        INSERT INTO customers (business_id, phone, name, channel, customer_type, lifecycle_stage, last_message_at, created_at, updated_at)
        SELECT cs.business_id, cs.customer_phone, cs.customer_name, cs.channel, 'lead',
               CASE WHEN cs.status = 'human_active' THEN 'engaged' ELSE 'new' END,
               cs.last_message_at, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        FROM chat_sessions cs
        WHERE NOT EXISTS (SELECT 1 FROM customers c WHERE c.business_id = cs.business_id AND c.phone = cs.customer_phone)
    """)


def criar_tabelas():
    conn = conectar()
    cursor = conn.cursor()
    _criar_tabelas_legadas(cursor)
    _criar_tabelas_core(cursor)
    _sincronizar_businesses(cursor)
    _seed_business_modules(cursor)
    conn.commit()
    conn.close()
