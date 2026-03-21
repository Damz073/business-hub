import os
import requests


def enviar_alerta_discord(titulo: str, mensagem: str):
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")

    if not webhook_url:
        return False

    payload = {
        "content": f"🚨 **{titulo}**\n```{mensagem[:1800]}```"
    }

    try:
        resposta = requests.post(webhook_url, json=payload, timeout=10)
        return resposta.status_code in (200, 204)
    except Exception:
        return False