import re
import unicodedata
from difflib import SequenceMatcher
from typing import Optional

from app.database import conectar

STOPWORDS_ESTABELECIMENTO = {
    "de", "da", "do", "das", "dos", "e", "me", "ltda", "eireli", "sa", "cia"
}


def normalizar_nome_estabelecimento(nome: str) -> str:
    nome = (nome or "").strip()
    if not nome:
        return ""
    nome = unicodedata.normalize("NFKD", nome)
    nome = "".join(c for c in nome if not unicodedata.combining(c))
    nome = nome.lower()
    nome = re.sub(r"[^a-z0-9\s]", " ", nome)
    nome = re.sub(r"\s+", " ", nome)
    return nome.strip()


def tokenizar_nome_estabelecimento(nome: str):
    base = normalizar_nome_estabelecimento(nome)
    if not base:
        return []
    return [t for t in base.split() if len(t) > 2 and t not in STOPWORDS_ESTABELECIMENTO]


def similaridade_nomes_estabelecimento(nome_a: str, nome_b: str) -> float:
    a = normalizar_nome_estabelecimento(nome_a)
    b = normalizar_nome_estabelecimento(nome_b)
    if not a or not b:
        return 0.0

    ratio = SequenceMatcher(None, a, b).ratio()
    tokens_a = set(tokenizar_nome_estabelecimento(a))
    tokens_b = set(tokenizar_nome_estabelecimento(b))

    if not tokens_a or not tokens_b:
        return ratio

    intersecao = len(tokens_a & tokens_b)
    cobertura = intersecao / max(1, min(len(tokens_a), len(tokens_b)))
    return max(ratio, cobertura)


def buscar_merchant_por_nome(restaurante_id: int, nome: str):
    nome_normalizado = normalizar_nome_estabelecimento(nome)
    if not nome_normalizado:
        return None

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, restaurant_id, nome, nome_normalizado, categoria_default, ocorrencias, ativo
        FROM merchants
        WHERE restaurant_id = ? AND nome_normalizado = ?
        """,
        (restaurante_id, nome_normalizado),
    )
    merchant = cursor.fetchone()
    if merchant:
        conn.close()
        return dict(merchant)

    cursor.execute(
        """
        SELECT id, restaurant_id, nome, nome_normalizado, categoria_default, ocorrencias, ativo
        FROM merchants
        WHERE restaurant_id = ? AND ativo = 1
        ORDER BY ocorrencias DESC, id ASC
        """,
        (restaurante_id,),
    )
    candidatos = cursor.fetchall()
    conn.close()

    melhor = None
    melhor_score = 0.0
    for item in candidatos:
        atual = dict(item)
        score = similaridade_nomes_estabelecimento(nome, atual["nome"])
        if score > melhor_score:
            melhor_score = score
            melhor = atual

    if melhor and melhor_score >= 0.84:
        return melhor
    return None


def buscar_ou_criar_merchant(restaurante_id: int, nome: str, categoria_default: Optional[str] = None):
    nome = (nome or "").strip()
    nome_normalizado = normalizar_nome_estabelecimento(nome)
    if not nome_normalizado:
        return None

    existente = buscar_merchant_por_nome(restaurante_id, nome)
    if existente:
        return existente

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO merchants (
            restaurant_id,
            nome,
            nome_normalizado,
            categoria_default,
            ocorrencias,
            ativo,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, 0, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (restaurante_id, nome, nome_normalizado, categoria_default),
    )
    merchant_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {
        "id": merchant_id,
        "restaurant_id": restaurante_id,
        "nome": nome,
        "nome_normalizado": nome_normalizado,
        "categoria_default": categoria_default,
        "ocorrencias": 0,
        "ativo": 1,
    }


def obter_ou_criar_merchant_normalizado(
    restaurant_id: int,
    nome_detectado: str,
    category_default: Optional[str] = None
):
    merchant = buscar_ou_criar_merchant(
        restaurant_id,
        nome_detectado,
        category_default
    )

    if not merchant:
        return None

    return {
        "id": merchant["id"],
        "nome": merchant["nome"],
        "categoria_default": merchant.get("categoria_default")
    }


def registrar_ocorrencia_merchant(merchant_id: int, categoria_default: Optional[str] = None):
    conn = conectar()
    cursor = conn.cursor()

    if categoria_default:
        cursor.execute(
            """
            UPDATE merchants
            SET ocorrencias = COALESCE(ocorrencias, 0) + 1,
                categoria_default = COALESCE(?, categoria_default),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (categoria_default, merchant_id),
        )
    else:
        cursor.execute(
            """
            UPDATE merchants
            SET ocorrencias = COALESCE(ocorrencias, 0) + 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (merchant_id,),
        )

    conn.commit()
    conn.close()


def salvar_receipt_processado(
    restaurante_id: int,
    telefone: str,
    caminho_imagem: str,
    resultado_ocr: dict,
    media_id: Optional[str] = None,
    status: str = "processado",
):
    estabelecimento = resultado_ocr.get("estabelecimento")
    categoria_sugerida = resultado_ocr.get("categoria_sugerida")
    merchant = None
    merchant_id = None

    if estabelecimento and estabelecimento != "Não identificado":
        merchant = buscar_ou_criar_merchant(restaurante_id, estabelecimento, categoria_sugerida)
        if merchant:
            merchant_id = merchant["id"]
            estabelecimento = merchant["nome"]
            if merchant.get("categoria_default"):
                categoria_sugerida = merchant["categoria_default"] or categoria_sugerida

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO receipts (
            restaurant_id,
            telefone,
            image_path,
            media_id,
            merchant_id,
            merchant_name,
            ocr_text,
            ocr_text_top,
            ocr_text_total,
            valor_total,
            categoria_sugerida,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            restaurante_id,
            telefone,
            caminho_imagem,
            media_id,
            merchant_id,
            estabelecimento,
            resultado_ocr.get("texto_extraido"),
            resultado_ocr.get("texto_topo"),
            resultado_ocr.get("texto_total"),
            resultado_ocr.get("valor_total"),
            categoria_sugerida,
            status,
        ),
    )
    receipt_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {
        "id": receipt_id,
        "merchant_id": merchant_id,
        "categoria_sugerida": categoria_sugerida,
        "merchant_name": estabelecimento,
    }


def atualizar_receipt_status(
    receipt_id: int,
    status: str,
    categoria_confirmada: Optional[str] = None,
    transaction_id: Optional[int] = None,
):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE receipts
        SET status = ?,
            categoria_confirmada = COALESCE(?, categoria_confirmada),
            transaction_id = COALESCE(?, transaction_id),
            confirmed_at = CASE
                WHEN ? IN ('confirmado', 'registrado') THEN CURRENT_TIMESTAMP
                ELSE confirmed_at
            END
        WHERE id = ?
        """,
        (status, categoria_confirmada, transaction_id, status, receipt_id),
    )
    conn.commit()
    conn.close()


def salvar_transacao(restaurante_id, resultado, receipt_id: Optional[int] = None, merchant_id: Optional[int] = None):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO transacoes (restaurant_id, tipo, categoria, valor, descricao, receipt_id, merchant_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            restaurante_id,
            resultado["tipo"],
            resultado["categoria"],
            resultado["valor"],
            resultado.get("descricao"),
            receipt_id,
            merchant_id,
        ),
    )
    transacao_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return transacao_id


def gerar_relatorio(restaurante_id):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT tipo, categoria, valor, descricao
        FROM transacoes
        WHERE restaurant_id = ?
        """,
        (restaurante_id,),
    )
    dados = cursor.fetchall()

    total_entradas = 0.0
    total_despesas = 0.0
    transacoes = []

    for item in dados:
        tipo = item["tipo"]
        categoria = item["categoria"]
        valor = item["valor"] or 0
        descricao = item["descricao"]
        transacoes.append({
            "tipo": tipo,
            "categoria": categoria,
            "valor": valor,
            "descricao": descricao,
        })
        if tipo == "entrada":
            total_entradas += valor
        elif tipo == "despesa":
            total_despesas += valor

    saldo = total_entradas - total_despesas
    conn.close()

    return {
        "quantidade_transacoes": len(transacoes),
        "total_entradas": total_entradas,
        "total_despesas": total_despesas,
        "saldo": saldo,
        "transacoes": transacoes,
    }