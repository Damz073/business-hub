import re
import pytesseract
from PIL import Image, ImageOps, ImageFilter

from app.ocr_parser import (
    extrair_valor_total,
    extrair_estabelecimento,
    sugerir_categoria_comprovante,
)
from app.settings import get_tesseract_cmd

tesseract_cmd = get_tesseract_cmd()
if tesseract_cmd:
    pytesseract.pytesseract.tesseract_cmd = tesseract_cmd


def preprocessar_base(imagem: Image.Image) -> Image.Image:
    imagem = imagem.convert("L")
    imagem = ImageOps.autocontrast(imagem)
    imagem = imagem.resize((imagem.width * 2, imagem.height * 2))
    imagem = imagem.filter(ImageFilter.SHARPEN)
    return imagem


def preprocessar_para_total(imagem: Image.Image) -> Image.Image:
    imagem = preprocessar_base(imagem)
    return imagem


def ler_texto_regiao(imagem: Image.Image, lang: str = "por+eng", psm: int = 6):
    config = f"--oem 3 --psm {psm}"
    return pytesseract.image_to_string(imagem, lang=lang, config=config)


def limpar_estabelecimento_final(texto: str | None) -> str | None:
    if not texto:
        return None

    texto = texto.strip()
    texto = re.sub(r"\s+", " ", texto)

    if len(texto) < 8:
        return None

    # corta prefixos de endereço muito comuns
    texto = re.sub(
        r"^(avenida|av|av\.|rua|r\.|travessa|tv|rodovia|rod|estrada)\s+",
        "",
        texto,
        flags=re.IGNORECASE,
    ).strip()

    # se houver LTDA/EIRELI/ME/SA/CIA, corta até ali
    m = re.search(r"\b(ltda|eireli|me|sa|cia)\b", texto, flags=re.IGNORECASE)
    if m:
        texto = texto[:m.end()].strip()

    # rejeita lixo
    if len(texto) < 8:
        return None

    palavras = texto.split()
    if len(palavras) < 2:
        return None

    qtd_letras = sum(c.isalpha() for c in texto)
    if qtd_letras < 6:
        return None

    # se tiver muitas letras soltas/ruído, rejeita
    curtas = sum(1 for p in palavras if len(p) <= 2)
    if len(palavras) >= 3 and curtas >= len(palavras) // 2:
        return None

    return texto


def processar_comprovante(caminho_imagem: str):
    imagem_original = Image.open(caminho_imagem)

    imagem_base = preprocessar_base(imagem_original)
    imagem_total = preprocessar_para_total(imagem_original)

    largura, altura = imagem_base.size

    # usa um topo mais amplo, mas SEM binarização agressiva
    regiao_topo = imagem_base.crop((0, 0, largura, int(altura * 0.28)))
    regiao_total = imagem_total.crop((0, int(altura * 0.45), largura, altura))

    texto_completo = ler_texto_regiao(imagem_base, psm=6)
    texto_topo = ler_texto_regiao(regiao_topo, psm=6)
    texto_total = ler_texto_regiao(regiao_total, psm=6)

    # 1) tenta no topo
    estabelecimento = extrair_estabelecimento(texto_topo)
    estabelecimento = limpar_estabelecimento_final(estabelecimento)

    # 2) fallback no texto completo
    if not estabelecimento:
        estabelecimento = extrair_estabelecimento(texto_completo)
        estabelecimento = limpar_estabelecimento_final(estabelecimento)

    # 3) fallback nas primeiras linhas do texto completo
    if not estabelecimento:
        linhas_iniciais = "\n".join(texto_completo.splitlines()[:15])
        estabelecimento = extrair_estabelecimento(linhas_iniciais)
        estabelecimento = limpar_estabelecimento_final(estabelecimento)

    # 4) melhor não inventar nome
    if not estabelecimento:
        estabelecimento = "Não identificado"

    valor_total = extrair_valor_total(texto_total)
    if valor_total is None:
        valor_total = extrair_valor_total(texto_completo)

    categoria_sugerida = sugerir_categoria_comprovante(
        texto=texto_completo,
        estabelecimento=None if estabelecimento == "Não identificado" else estabelecimento,
    )

    return {
        "texto_extraido": texto_completo,
        "texto_topo": texto_topo,
        "texto_total": texto_total,
        "valor_total": valor_total,
        "estabelecimento": estabelecimento,
        "categoria_sugerida": categoria_sugerida,
    }