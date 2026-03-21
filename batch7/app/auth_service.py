from app.database import conectar
from app.security import verify_password, create_access_token, hash_password, gerar_senha_temporaria, decode_access_token


def criar_tabela_web_users():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
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
        """
    )
    conn.commit()
    conn.close()



def criar_login_web(restaurant_id: int, email: str, nome: str, role: str = 'admin') -> dict:
    criar_tabela_web_users()
    email = (email or '').strip().lower()
    nome = (nome or '').strip()
    if not email or '@' not in email:
        raise ValueError('Email inválido.')
    if not nome:
        raise ValueError('Nome inválido.')

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT r.id, r.nome, b.id AS business_id, b.nome AS business_name, b.business_type
        FROM restaurants r
        LEFT JOIN businesses b ON b.legacy_restaurant_id = r.id
        WHERE r.id = ?
        """,
        (restaurant_id,),
    )
    restaurante = cursor.fetchone()
    if not restaurante:
        conn.close()
        raise ValueError('Restaurante não encontrado.')

    cursor.execute('SELECT id FROM web_users WHERE email = ?', (email,))
    existente = cursor.fetchone()
    if existente:
        conn.close()
        raise ValueError('Já existe um login web com esse email.')

    senha_temporaria = gerar_senha_temporaria()
    senha_hash = hash_password(senha_temporaria)

    cursor.execute(
        """
        INSERT INTO web_users (restaurant_id, business_id, name, email, password_hash, role, active)
        VALUES (?, ?, ?, ?, ?, ?, 1)
        """,
        (restaurant_id, restaurante['business_id'], nome, email, senha_hash, role),
    )
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {
        'id': user_id,
        'restaurant_id': restaurant_id,
        'restaurant_name': restaurante['nome'],
        'business_id': restaurante['business_id'],
        'business_name': restaurante['business_name'] or restaurante['nome'],
        'business_type': restaurante['business_type'] or 'restaurant',
        'name': nome,
        'email': email,
        'role': role,
        'temporary_password': senha_temporaria,
    }



def autenticar_web_user(email: str, password: str) -> dict:
    criar_tabela_web_users()
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT wu.id, wu.restaurant_id, wu.business_id, wu.name, wu.email, wu.password_hash, wu.role, wu.active,
               r.nome AS restaurant_name, r.status AS restaurant_status,
               b.nome AS business_name, b.business_type, b.status AS business_status
        FROM web_users wu
        JOIN restaurants r ON r.id = wu.restaurant_id
        LEFT JOIN businesses b ON b.id = wu.business_id
        WHERE lower(wu.email) = lower(?)
        LIMIT 1
        """,
        ((email or '').strip(),),
    )
    user = cursor.fetchone()
    conn.close()

    if not user:
        raise ValueError('Email ou senha inválidos.')

    user = dict(user)
    if not user['active']:
        raise ValueError('Usuário web inativo.')
    if user['restaurant_status'] != 'ativo':
        raise ValueError('O restaurante vinculado está suspenso.')
    if user.get('business_status') and user['business_status'] != 'ativo':
        raise ValueError('O negócio vinculado está suspenso.')
    if not verify_password(password or '', user['password_hash']):
        raise ValueError('Email ou senha inválidos.')

    token = create_access_token(user)
    user_payload = {
        'id': user['id'],
        'restaurant_id': user['restaurant_id'],
        'restaurant_name': user['restaurant_name'],
        'business_id': user['business_id'],
        'business_name': user.get('business_name') or user['restaurant_name'],
        'business_type': user.get('business_type') or 'restaurant',
        'name': user['name'],
        'email': user['email'],
        'role': user['role'],
    }
    return {
        'access_token': token,
        'token_type': 'bearer',
        'user': user_payload,
    }



def obter_usuario_web_por_id(user_id: int):
    criar_tabela_web_users()
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT wu.id, wu.restaurant_id, wu.business_id, wu.name, wu.email, wu.role, wu.active,
               r.nome AS restaurant_name, r.status AS restaurant_status,
               b.nome AS business_name, b.business_type, b.status AS business_status
        FROM web_users wu
        JOIN restaurants r ON r.id = wu.restaurant_id
        LEFT JOIN businesses b ON b.id = wu.business_id
        WHERE wu.id = ?
        LIMIT 1
        """,
        (user_id,),
    )
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None



def obter_usuario_atual_do_token(token: str):
    payload = decode_access_token(token)
    user_id = int(payload['sub'])
    user = obter_usuario_web_por_id(user_id)
    if not user:
        raise ValueError('Usuário não encontrado.')
    if not user['active']:
        raise ValueError('Usuário inativo.')
    return {
        'id': user['id'],
        'restaurant_id': user['restaurant_id'],
        'restaurant_name': user['restaurant_name'],
        'business_id': user.get('business_id'),
        'business_name': user.get('business_name') or user['restaurant_name'],
        'business_type': user.get('business_type') or 'restaurant',
        'name': user['name'],
        'email': user['email'],
        'role': user['role'],
        'active': user['active'],
    }
