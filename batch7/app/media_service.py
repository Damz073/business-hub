import os
from app.whatsapp_api import obter_url_midia, baixar_midia

MEDIA_DIR = "media"


def garantir_pasta_media():
    os.makedirs(MEDIA_DIR, exist_ok=True)


def baixar_imagem_whatsapp(media_id: str, extensao: str = ".jpg"):
    garantir_pasta_media()

    info_midia = obter_url_midia(media_id)

    if "json" not in info_midia:
        return None, info_midia

    dados = info_midia["json"]

    if info_midia.get("status_code") != 200:
        return None, info_midia

    if "url" not in dados:
        return None, info_midia

    url_midia = dados["url"]
    nome_arquivo = f"{media_id}{extensao}"
    caminho = os.path.join(MEDIA_DIR, nome_arquivo)

    sucesso = baixar_midia(url_midia, caminho)

    if not sucesso:
        return None, {
            "erro": "Não foi possível baixar a mídia.",
            "media_id": media_id,
            "status_code": info_midia.get("status_code"),
            "json": dados,
        }

    return caminho, info_midia
