import re


def extrair_valor(texto: str):
    padrao = r"(\d+[.,]?\d*)"
    resultado = re.search(padrao, texto)

    if resultado:
        valor_texto = resultado.group(1).replace(",", ".")
        return float(valor_texto)

    return None


def identificar_tipo(texto: str):
    texto = texto.lower()

    palavras_despesa = ["despesa", "paguei", "gastei", "comprei"]
    palavras_entrada = ["entrada", "recebi", "entrou", "vendi"]
    palavras_relatorio = ["relatorio", "relatório"]

    for p in palavras_relatorio:
        if p in texto:
            return "relatorio"

    for p in palavras_despesa:
        if p in texto:
            return "despesa"

    for p in palavras_entrada:
        if p in texto:
            return "entrada"

    return "desconhecido"


def identificar_categoria(texto: str):
    texto = texto.lower()

    categorias = [
        "mercado",
        "ifood",
        "aluguel",
        "energia",
        "agua",
        "gás",
        "gas",
        "internet",
        "funcionario",
        "funcionarios"
    ]

    for categoria in categorias:
        if categoria in texto:
            return categoria

    return "geral"


def limpar_descricao(texto: str):
    texto = re.sub(r"\d+[.,]?\d*", "", texto)
    return " ".join(texto.split())


def interpretar_texto(texto: str):
    texto = texto.lower().strip()

    tipo = identificar_tipo(texto)

    if tipo == "relatorio":
        return {
            "tipo": "relatorio",
            "categoria": None,
            "valor": None,
            "descricao": texto
        }

    valor = extrair_valor(texto)
    categoria = identificar_categoria(texto)
    descricao = limpar_descricao(texto)

    return {
        "tipo": tipo,
        "categoria": categoria,
        "valor": valor,
        "descricao": descricao
    }