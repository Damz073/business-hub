import re
import unicodedata


def normalizar_texto(texto: str) -> str:
    if not texto:
        return ""
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto.lower().strip()


def extrair_valor_total(texto: str):
    texto = texto.lower()
    texto = texto.replace("\r", "\n")
    linhas = [l.strip() for l in texto.split("\n") if l.strip()]

    # prioridade máxima
    for linha in linhas:
        if "valor a pagar" in linha or "valor pago" in linha or "total a pagar" in linha:
            valores = re.findall(r"(\d{1,3}(?:\.\d{3})*,\d{2})", linha)
            if valores:
                valor = valores[-1].replace(".", "").replace(",", ".")
                try:
                    return float(valor)
                except Exception:
                    pass

    # prioridade média
    for linha in linhas:
        if "valor total" in linha or re.search(r"\btotal\b", linha):
            valores = re.findall(r"(\d{1,3}(?:\.\d{3})*,\d{2})", linha)
            if valores:
                valor = valores[-1].replace(".", "").replace(",", ".")
                try:
                    return float(valor)
                except Exception:
                    pass

    # fallback: últimos valores monetários
    valores = re.findall(r"(\d{1,3}(?:\.\d{3})*,\d{2})", "\n".join(linhas))

    if valores:
        ultimos = valores[-6:]

        # prefere o maior entre os últimos valores, porque total costuma estar no final
        candidatos = []
        for v in ultimos:
            try:
                candidatos.append(float(v.replace(".", "").replace(",", ".")))
            except Exception:
                pass

        if candidatos:
            return max(candidatos)

    return None


def limpar_linha_estabelecimento(linha: str) -> str:
    linha = linha.strip()
    linha = re.sub(r"[|_/\\]+", " ", linha)
    linha = re.sub(r"[^A-Za-zÀ-ÿ0-9\s&\-\.\']", " ", linha)
    linha = re.sub(r"\s+", " ", linha)
    return linha.strip()


def contem_data_ou_hora(linha: str) -> bool:
    padroes = [
        r"\b\d{2}/\d{2}/\d{2,4}\b",
        r"\b\d{2}:\d{2}(:\d{2})?\b",
        r"\b\d{2}-\d{2}-\d{2,4}\b",
    ]
    return any(re.search(p, linha) for p in padroes)


def contem_cnpj_ou_documento(linha: str) -> bool:
    padroes = [
        r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b",
        r"\b\d{11,14}\b",
    ]
    return any(re.search(p, linha) for p in padroes)


def linha_parece_ruim(linha: str) -> bool:
    linha_limpa = limpar_linha_estabelecimento(linha)
    linha_lower = normalizar_texto(linha_limpa)

    if not linha_lower:
        return True

    if len(linha_lower) < 4:
        return True

    palavras_ruins = [
        "cnpj",
        "desc",
        "descr",
        "descricao",
        "codigo",
        "cod",
        "qtd",
        "qtde",
        "item",
        "vl unit",
        "unit",
        "un rs",
        "cpf",
        "documento auxiliar",
        "nota fiscal",
        "danfe",
        "consumidor",
        "chave de acesso",
        "protocolo",
        "serie",
        "caixa",
        "operador",
        "cliente",
        "terminal",
        "endereco",
        "logradouro",
        "bairro",
        "avenida",
        "rua",
        "travessa",
        "consulta",
        "sefaz",
        "www",
        "http",
        "qtd",
        "codigo",
        "cod",
        "descricao",
        "descr",
        "vl unit",
        "unit",
        "item",
        "kg",
        "un rs",
        "valor pago",
        "valor a pagar",
    ]

    if any(p in linha_lower for p in palavras_ruins):
        return True

    if contem_data_ou_hora(linha_limpa):
        return True

    if contem_cnpj_ou_documento(linha_limpa):
        return True

    qtd_numeros = sum(c.isdigit() for c in linha_limpa)
    qtd_letras = sum(c.isalpha() for c in linha_limpa)

    if qtd_numeros >= qtd_letras and qtd_numeros >= 3:
        return True

    if re.fullmatch(r"[\d\W]+", linha_limpa):
        return True

    return False


def pontuar_linha_estabelecimento(linha: str, indice: int = 0) -> int:
    linha_limpa = limpar_linha_estabelecimento(linha)
    linha_lower = normalizar_texto(linha_limpa)

    if not linha_limpa:
        return -999

    score = 0

    if indice == 0:
        score += 40
    elif indice == 1:
        score += 30
    elif indice == 2:
        score += 20
    elif indice <= 5:
        score += 8

    tamanho = len(linha_limpa)
    if 8 <= tamanho <= 45:
        score += 15
    elif 46 <= tamanho <= 60:
        score += 5
    else:
        score -= 10

    qtd_letras = sum(c.isalpha() for c in linha_limpa)
    qtd_numeros = sum(c.isdigit() for c in linha_limpa)

    score += qtd_letras
    score -= qtd_numeros * 4

    palavras_boas = [
        "mercado",
        "supermercado",
        "padaria",
        "restaurante",
        "bar",
        "lanchonete",
        "comercio",
        "comercial",
        "distribuidora",
        "transportes",
        "transporte",
        "posto",
        "farmacia",
        "drogaria",
        "atacadao",
        "assai",
        "mix",
    ]

    if any(p in linha_lower for p in palavras_boas):
        score += 35

    termos_societarios = ["ltda", "eireli", "me", "sa", "cia"]
    if any(re.search(rf"\b{re.escape(t)}\b", linha_lower) for t in termos_societarios):
        score += 20

    letras = [c for c in linha_limpa if c.isalpha()]
    if letras:
        maiusculas = sum(1 for c in letras if c.isupper())
        proporcao_maiusculas = maiusculas / len(letras)
        if proporcao_maiusculas >= 0.6:
            score += 12

    if contem_data_ou_hora(linha_limpa):
        score -= 40

    if contem_cnpj_ou_documento(linha_limpa):
        score -= 50

    penalidades = [
        "avenida",
        "rua",
        "bairro",
        "centro",
        "fone",
        "telefone",
        "documento auxiliar",
        "nota fiscal",
        "descricao",
        "descr",
        "qtd",
        "item",
        "vl unit",
        "unit",
        "codigo",
        "cod",
        "kg",
    ]

    if any(p in linha_lower for p in penalidades):
        score -= 45

    return score


def extrair_estabelecimento(texto: str):
    if not texto:
        return None

    linhas = [limpar_linha_estabelecimento(l) for l in texto.splitlines() if l.strip()]
    linhas = [l for l in linhas if l]

    if not linhas:
        return None

    candidatas = []

    for i, linha in enumerate(linhas[:12]):
        if linha_parece_ruim(linha):
            continue

        score = pontuar_linha_estabelecimento(linha, i)
        candidatas.append((score, linha))

    if candidatas:
        candidatas.sort(key=lambda x: x[0], reverse=True)
        melhor_score, melhor_linha = candidatas[0]

        if melhor_score >= 20:
            return melhor_linha

    return None


def sugerir_categoria_comprovante(texto: str, estabelecimento: str | None = None):
    base = normalizar_texto(f"{estabelecimento or ''}\n{texto}")
    mapa = {
        "mercado": [
            "mercado", "supermercado", "mercearia", "padaria", "atacadao",
            "assai", "extra", "mix", "hortifruti", "acougue", "frigorifico"
        ],
        "combustivel": [
            "posto", "gasolina", "etanol", "diesel", "combustivel", "gnv", "ipiranga", "shell", "petrobras"
        ],
        "farmacia": ["farmacia", "drogaria", "medicamento"],
        "fornecedor": ["distribuidora", "fornecedor", "bebidas", "atacado", "comercial", "deposito"],
        "energia": ["energia", "eletrica", "enel", "coelba", "cemig", "light"],
        "agua": ["agua", "embasa", "saneamento"],
        "internet": ["internet", "fibra", "oi", "vivo", "claro", "tim", "provedor"],
    }

    for categoria, palavras in mapa.items():
        if any(p in base for p in palavras):
            return categoria

    return "geral"