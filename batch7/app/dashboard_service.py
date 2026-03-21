from app.database import conectar
from app.core_services import get_business_profile, list_enabled_modules_for_business, get_subscription_for_business


def _get_month_bounds() -> tuple[str, str]:
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT strftime('%Y-%m-01', 'now', 'localtime') AS start_month")
    start_month = cursor.fetchone()[0]
    cursor.execute("SELECT datetime(?, '+1 month')", (start_month,))
    next_month = cursor.fetchone()[0]
    conn.close()
    return start_month, next_month


def obter_dashboard_summary(restaurant_id: int) -> dict:
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            COALESCE(SUM(CASE WHEN tipo = 'entrada' THEN valor ELSE 0 END), 0) AS total_entradas,
            COALESCE(SUM(CASE WHEN tipo = 'despesa' THEN valor ELSE 0 END), 0) AS total_despesas,
            COUNT(*) AS quantidade_transacoes
        FROM transacoes
        WHERE restaurant_id = ?
        """,
        (restaurant_id,),
    )
    totals = dict(cursor.fetchone())

    month_start, next_month = _get_month_bounds()
    cursor.execute(
        """
        SELECT
            COALESCE(SUM(CASE WHEN tipo = 'entrada' THEN valor ELSE 0 END), 0) AS entradas_mes,
            COALESCE(SUM(CASE WHEN tipo = 'despesa' THEN valor ELSE 0 END), 0) AS despesas_mes,
            COUNT(*) AS transacoes_mes
        FROM transacoes
        WHERE restaurant_id = ?
          AND criado_em >= ?
          AND criado_em < ?
        """,
        (restaurant_id, month_start, next_month),
    )
    month_totals = dict(cursor.fetchone())

    cursor.execute(
        """
        SELECT id, tipo, categoria, valor, descricao, criado_em
        FROM transacoes
        WHERE restaurant_id = ?
        ORDER BY datetime(criado_em) DESC, id DESC
        LIMIT 5
        """,
        (restaurant_id,),
    )
    ultimas = [dict(row) for row in cursor.fetchall()]

    conn.close()

    total_entradas = float(totals["total_entradas"] or 0)
    total_despesas = float(totals["total_despesas"] or 0)
    entradas_mes = float(month_totals["entradas_mes"] or 0)
    despesas_mes = float(month_totals["despesas_mes"] or 0)

    profile = get_business_profile(get_business_id_by_legacy_restaurant_id(restaurant_id))
    enabled_modules = list_enabled_modules_for_business(profile['id']) if profile else []
    subscription = get_subscription_for_business(profile['id']) if profile else None

    return {
        "saldo_atual": total_entradas - total_despesas,
        "total_entradas": total_entradas,
        "total_despesas": total_despesas,
        "quantidade_transacoes": int(totals["quantidade_transacoes"] or 0),
        "mes_atual": {
            "inicio": month_start,
            "entradas": entradas_mes,
            "despesas": despesas_mes,
            "saldo": entradas_mes - despesas_mes,
            "quantidade_transacoes": int(month_totals["transacoes_mes"] or 0),
        },
        "ultimas_transacoes": ultimas,
        "business_profile": profile,
        "enabled_modules": enabled_modules,
        "subscription": subscription,
    }


def listar_transacoes(
    restaurant_id: int,
    limit: int = 100,
    tipo: str | None = None,
    categoria: str | None = None,
    data_inicio: str | None = None,
    data_fim: str | None = None,
):
    conn = conectar()
    cursor = conn.cursor()

    query = """
        SELECT id, restaurant_id, tipo, categoria, valor, descricao, criado_em, receipt_id, merchant_id
        FROM transacoes
        WHERE restaurant_id = ?
    """
    params = [restaurant_id]

    if tipo:
        query += " AND tipo = ?"
        params.append(tipo)
    if categoria:
        query += " AND categoria = ?"
        params.append(categoria)
    if data_inicio:
        query += " AND criado_em >= ?"
        params.append(data_inicio)
    if data_fim:
        query += " AND criado_em <= ?"
        params.append(data_fim)

    limit = max(1, min(int(limit), 500))
    query += " ORDER BY datetime(criado_em) DESC, id DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, tuple(params))
    items = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return items


def listar_categorias(restaurant_id: int):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT categoria, COUNT(*) AS quantidade
        FROM transacoes
        WHERE restaurant_id = ?
        GROUP BY categoria
        ORDER BY quantidade DESC, categoria ASC
        """,
        (restaurant_id,),
    )
    transacao_categorias = {row["categoria"]: int(row["quantidade"] or 0) for row in cursor.fetchall()}

    cursor.execute(
        """
        SELECT categoria_default, COUNT(*) AS quantidade
        FROM merchants
        WHERE restaurant_id = ?
          AND ativo = 1
          AND categoria_default IS NOT NULL
          AND trim(categoria_default) <> ''
        GROUP BY categoria_default
        ORDER BY quantidade DESC, categoria_default ASC
        """,
        (restaurant_id,),
    )
    merchant_categorias = {row["categoria_default"]: int(row["quantidade"] or 0) for row in cursor.fetchall()}

    conn.close()

    todas = set(transacao_categorias) | set(merchant_categorias)
    resultado = []
    for nome in sorted(todas):
        resultado.append(
            {
                "name": nome,
                "transactions_count": transacao_categorias.get(nome, 0),
                "merchants_count": merchant_categorias.get(nome, 0),
            }
        )
    return resultado



def listar_merchants(restaurant_id: int, apenas_ativos: bool = True):
    conn = conectar()
    cursor = conn.cursor()

    query = """
        SELECT id, restaurant_id, nome, nome_normalizado, categoria_default,
               ocorrencias, ativo, created_at, updated_at
        FROM merchants
        WHERE restaurant_id = ?
    """
    params = [restaurant_id]
    if apenas_ativos:
        query += " AND ativo = 1"

    query += " ORDER BY ocorrencias DESC, nome ASC"
    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    conn.close()

    items = []
    for row in rows:
        item = dict(row)
        item["display_name"] = item.pop("nome")
        item["normalized_name"] = item.pop("nome_normalizado")
        item["default_category"] = item.pop("categoria_default")
        item["occurrence_count"] = int(item.pop("ocorrencias") or 0)
        item["active"] = bool(item.pop("ativo"))
        item["last_seen_at"] = item.get("updated_at")
        items.append(item)
    return items



def listar_restaurant_users(restaurant_id: int, apenas_ativos: bool = False):
    conn = conectar()
    cursor = conn.cursor()

    query = """
        SELECT id, restaurant_id, telefone, nome, role, ativo, created_at
        FROM restaurant_users
        WHERE restaurant_id = ?
    """
    params = [restaurant_id]
    if apenas_ativos:
        query += " AND ativo = 1"

    query += " ORDER BY nome ASC, id ASC"
    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    conn.close()

    items = []
    for row in rows:
        item = dict(row)
        item["active"] = bool(item.pop("ativo"))
        items.append(item)
    return items



def obter_restaurant_info(restaurant_id: int):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT r.id, r.nome, r.status, r.plano, r.vencimento,
               b.id AS business_id, b.nome AS business_name, b.business_type
        FROM restaurants r
        LEFT JOIN businesses b ON b.legacy_restaurant_id = r.id
        WHERE r.id = ?
        LIMIT 1
        """,
        (restaurant_id,),
    )
    restaurante = cursor.fetchone()
    conn.close()

    if not restaurante:
        return None

    restaurante = dict(restaurante)
    restaurante["restaurant_id"] = restaurante.pop("id")
    restaurante["restaurant_name"] = restaurante.pop("nome")
    restaurante["business_name"] = restaurante.get("business_name") or restaurante["restaurant_name"]
    restaurante["business_type"] = restaurante.get("business_type") or "restaurant"
    return restaurante


def get_business_id_by_legacy_restaurant_id(restaurant_id: int):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM businesses WHERE legacy_restaurant_id = ? LIMIT 1', (restaurant_id,))
    row = cursor.fetchone()
    conn.close()
    return int(row['id']) if row else None
