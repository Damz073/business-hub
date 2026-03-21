from app.auth_service import criar_login_web
from app.database import conectar
from app.phone_utils import normalizar_telefone_br, gerar_variantes_telefone_br


def cadastrar_restaurante(nome: str):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO restaurants (nome, status, plano)
        VALUES (?, 'ativo', 'basico')
        """,
        (nome,),
    )
    restaurant_id = cursor.lastrowid
    cursor.execute(
        """
        INSERT INTO businesses (legacy_restaurant_id, nome, slug, business_type, status, plano, created_at, updated_at)
        VALUES (?, ?, lower(replace(?, ' ', '-')), 'restaurant', 'ativo', 'basico', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (restaurant_id, nome, nome),
    )

    conn.commit()
    conn.close()
    return restaurant_id



def adicionar_usuario_restaurante(restaurant_id: int, telefone: str, nome: str = 'Usuario', role: str = 'operador'):
    conn = conectar()
    cursor = conn.cursor()

    telefone_normalizado = normalizar_telefone_br(telefone)
    variantes = gerar_variantes_telefone_br(telefone_normalizado)
    placeholders = ','.join(['?'] * len(variantes))
    cursor.execute(
        f"""
        SELECT id, restaurant_id, telefone
        FROM restaurant_users
        WHERE telefone IN ({placeholders})
        """,
        variantes,
    )

    existente = cursor.fetchone()
    if existente:
        conn.close()
        raise ValueError(
            '⚠️ Este telefone já está cadastrado no sistema.\n'
            f'Telefone informado: {telefone_normalizado}\n'
            f"Telefone já salvo: {existente['telefone']}"
        )

    cursor.execute(
        """
        INSERT INTO restaurant_users (restaurant_id, nome, telefone, role, ativo)
        VALUES (?, ?, ?, ?, 1)
        """,
        (restaurant_id, nome, telefone_normalizado, role),
    )
    restaurant_user_id = cursor.lastrowid

    cursor.execute('SELECT id FROM businesses WHERE legacy_restaurant_id = ? LIMIT 1', (restaurant_id,))
    business = cursor.fetchone()
    if business:
        cursor.execute(
            """
            INSERT OR IGNORE INTO business_contacts (
                business_id, legacy_restaurant_user_id, telefone, nome, role, channel, ativo, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'whatsapp', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (business['id'], restaurant_user_id, telefone_normalizado, nome, role),
        )

    conn.commit()
    conn.close()



def ativar_restaurante(restaurant_id: int):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("UPDATE restaurants SET status = 'ativo' WHERE id = ?", (restaurant_id,))
    cursor.execute("UPDATE businesses SET status = 'ativo', updated_at = CURRENT_TIMESTAMP WHERE legacy_restaurant_id = ?", (restaurant_id,))
    conn.commit()
    conn.close()



def desativar_restaurante(restaurant_id: int):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("UPDATE restaurants SET status = 'suspenso' WHERE id = ?", (restaurant_id,))
    cursor.execute("UPDATE businesses SET status = 'suspenso', updated_at = CURRENT_TIMESTAMP WHERE legacy_restaurant_id = ?", (restaurant_id,))
    conn.commit()
    conn.close()



def resetar_transacoes_restaurante(restaurant_id: int):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM transacoes WHERE restaurant_id = ?', (restaurant_id,))
    conn.commit()
    conn.close()



def listar_restaurantes():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT r.id, r.nome, r.status, r.plano, r.vencimento,
               b.id AS business_id, b.business_type
        FROM restaurants r
        LEFT JOIN businesses b ON b.legacy_restaurant_id = r.id
        ORDER BY r.id
        """
    )
    dados = cursor.fetchall()
    conn.close()
    return [dict(item) for item in dados]



def criar_login_web_restaurante(restaurant_id: int, email: str, nome: str, role: str = 'admin'):
    return criar_login_web(restaurant_id=restaurant_id, email=email, nome=nome, role=role)



def obter_restaurante(restaurant_id: int):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT r.id, r.nome, r.status, r.plano, r.vencimento,
               b.id AS business_id, b.business_type, b.slug, b.status AS business_status
        FROM restaurants r
        LEFT JOIN businesses b ON b.legacy_restaurant_id = r.id
        WHERE r.id = ?
        LIMIT 1
        """,
        (restaurant_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def listar_usuarios_restaurante(restaurant_id: int):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, restaurant_id, nome, telefone, role, ativo
        FROM restaurant_users
        WHERE restaurant_id = ?
        ORDER BY ativo DESC, nome COLLATE NOCASE ASC, id ASC
        """,
        (restaurant_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def remover_usuario_restaurante(restaurant_id: int, telefone: str):
    conn = conectar()
    cursor = conn.cursor()
    telefone_normalizado = normalizar_telefone_br(telefone)
    variantes = gerar_variantes_telefone_br(telefone_normalizado)
    placeholders = ','.join(['?'] * len(variantes))
    cursor.execute(
        f"""
        SELECT id, telefone, nome
        FROM restaurant_users
        WHERE restaurant_id = ? AND telefone IN ({placeholders})
        LIMIT 1
        """,
        [restaurant_id, *variantes],
    )
    found = cursor.fetchone()
    if not found:
        conn.close()
        return None

    cursor.execute('DELETE FROM restaurant_users WHERE id = ?', (found['id'],))
    cursor.execute(
        'DELETE FROM business_contacts WHERE business_id = (SELECT id FROM businesses WHERE legacy_restaurant_id = ?) AND telefone = ?',
        (restaurant_id, found['telefone']),
    )
    conn.commit()
    conn.close()
    return dict(found)


def listar_admins_plataforma():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute('SELECT id, nome, telefone, ativo FROM platform_admins ORDER BY ativo DESC, id ASC')
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]
