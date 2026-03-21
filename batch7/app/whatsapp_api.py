import requests

from app.logger import logger
from app.settings import (
    get_whatsapp_graph_version,
    get_whatsapp_phone_number_id,
    get_whatsapp_token,
    mask_secret,
)


def _get_runtime_config():
    graph_api_version = get_whatsapp_graph_version()
    token = get_whatsapp_token()
    phone_number_id = get_whatsapp_phone_number_id()
    return graph_api_version, token, phone_number_id


def _validar_configuracao():
    _, token, phone_number_id = _get_runtime_config()

    if not token:
        raise RuntimeError(
            "WHATSAPP_TOKEN não configurado. Defina a variável de ambiente antes de iniciar a aplicação."
        )
    if not phone_number_id:
        raise RuntimeError(
            "WHATSAPP_PHONE_NUMBER_ID não configurado. Defina a variável de ambiente antes de iniciar a aplicação."
        )


def _headers_json():
    _validar_configuracao()
    _, token, _ = _get_runtime_config()
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _headers_auth():
    _validar_configuracao()
    _, token, _ = _get_runtime_config()
    return {
        "Authorization": f"Bearer {token}",
    }


def enviar_mensagem_texto(texto: str, destinatario: str):
    try:
        graph_api_version, token, phone_number_id = _get_runtime_config()
        url = f"https://graph.facebook.com/{graph_api_version}/{phone_number_id}/messages"

        payload = {
            "messaging_product": "whatsapp",
            "to": destinatario,
            "type": "text",
            "text": {
                "body": texto
            }
        }

        logger.info(
            "ENVIANDO WHATSAPP | to=%s | phone_id=%s | token=%s",
            destinatario,
            phone_number_id or "(vazio)",
            mask_secret(token),
        )

        resposta = requests.post(url, headers=_headers_json(), json=payload, timeout=30)

        try:
            corpo = resposta.json()
        except Exception:
            corpo = {"text": resposta.text}

        if resposta.status_code >= 400:
            logger.error(
                "ERRO AO ENVIAR WHATSAPP | status=%s | resposta=%s",
                resposta.status_code,
                corpo,
            )
        else:
            logger.info(
                "WHATSAPP ENVIADO COM SUCESSO | status=%s | resposta=%s",
                resposta.status_code,
                corpo,
            )

        return {
            "status_code": resposta.status_code,
            "json": corpo,
        }
    except Exception as e:
        logger.error(f"FALHA INTERNA AO ENVIAR WHATSAPP: {str(e)}")
        return {
            "status_code": 500,
            "json": {"error": str(e)},
        }


def obter_url_midia(media_id: str):
    try:
        graph_api_version, _, _ = _get_runtime_config()
        url = f"https://graph.facebook.com/{graph_api_version}/{media_id}"
        resposta = requests.get(url, headers=_headers_auth(), timeout=30)

        try:
            corpo = resposta.json()
        except Exception:
            corpo = {"text": resposta.text}

        return {
            "status_code": resposta.status_code,
            "json": corpo,
        }
    except Exception as e:
        logger.error(f"FALHA AO OBTER URL DA MIDIA: {str(e)}")
        return {
            "status_code": 500,
            "json": {"error": str(e)},
        }


def baixar_midia(url_midia: str, caminho_destino: str):
    try:
        resposta = requests.get(url_midia, headers=_headers_auth(), stream=True, timeout=60)

        if resposta.status_code != 200:
            logger.error("FALHA AO BAIXAR MIDIA | status=%s | url=%s", resposta.status_code, url_midia)
            return False

        with open(caminho_destino, "wb") as arquivo:
            for chunk in resposta.iter_content(chunk_size=8192):
                if chunk:
                    arquivo.write(chunk)

        return True
    except Exception as e:
        logger.error(f"FALHA INTERNA AO BAIXAR MIDIA: {str(e)}")
        return False
