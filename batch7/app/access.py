from app.database import conectar
from app.phone_utils import normalizar_telefone_br, gerar_variantes_telefone_br
from app.settings import get_admin_principal
from app.logger import logger


def seed_admin_principal():
    admin_principal = get_admin_principal()

    if not admin_principal:
        logger.warning('ADMIN_PRINCIPAL não configurado. Seed do admin principal ignorado.')
        return

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute('SELECT id FROM platform_admins WHERE telefone = ?', (admin_principal,))
    admin = cursor.fetchone()

    if not admin:
        cursor.execute(
            """
            INSERT INTO platform_admins (nome, telefone, ativo)
            VALUES (?, ?, 1)
            """,
            ('Administrador', admin_principal),
        )
        logger.info('ADMIN PRINCIPAL CRIADO: %s', admin_principal)

    conn.commit()
    conn.close()


def eh_admin_plataforma(telefone: str) -> bool:
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id
        FROM platform_admins
        WHERE telefone = ? AND ativo = 1
        """,
        (telefone,),
    )
    admin = cursor.fetchone()
    conn.close()
    return admin is not None



def buscar_restaurante_por_usuario(telefone: str):
    conn = conectar()
    cursor = conn.cursor()

    telefone_normalizado = normalizar_telefone_br(telefone)
    variantes = gerar_variantes_telefone_br(telefone_normalizado)
    placeholders = ','.join(['?'] * len(variantes))

    cursor.execute(
        f"""
        SELECT
            r.id AS restaurant_id,
            r.nome AS restaurant_nome,
            r.status AS restaurant_status,
            r.plano AS restaurant_plano,
            r.vencimento AS restaurant_vencimento,
            ru.nome AS user_nome,
            ru.role AS user_role,
            b.id AS business_id,
            b.nome AS business_name,
            b.business_type AS business_type,
            b.status AS business_status,
            bc.id AS business_contact_id
        FROM restaurant_users ru
        JOIN restaurants r ON r.id = ru.restaurant_id
        LEFT JOIN businesses b ON b.legacy_restaurant_id = r.id
        LEFT JOIN business_contacts bc ON bc.business_id = b.id AND bc.telefone = ru.telefone
        WHERE ru.telefone IN ({placeholders})
          AND ru.ativo = 1
        LIMIT 1
        """,
        variantes,
    )

    resultado = cursor.fetchone()
    conn.close()
    return dict(resultado) if resultado else None



def restaurante_ativo(restaurante: dict) -> bool:
    if not restaurante:
        return False
    return restaurante.get('restaurant_status') == 'ativo'
