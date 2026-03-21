import os
from pathlib import Path


def get_env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


def get_verify_token() -> str:
    return get_env("VERIFY_TOKEN", "financebot_verificacao_123")


def get_admin_principal() -> str:
    return get_env("ADMIN_PRINCIPAL", "")


def get_tesseract_cmd() -> str | None:
    value = get_env("TESSERACT_CMD")
    if value:
        return value

    default_windows = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    if default_windows.exists():
        return str(default_windows)

    return None


def get_whatsapp_graph_version() -> str:
    return get_env("WHATSAPP_GRAPH_VERSION", "v23.0")


def get_whatsapp_token() -> str | None:
    return get_env("WHATSAPP_TOKEN", "")


def get_whatsapp_phone_number_id() -> str | None:
    return get_env("WHATSAPP_PHONE_NUMBER_ID", "")


def get_discord_webhook_url() -> str | None:
    return get_env("DISCORD_WEBHOOK_URL", "")


def mask_secret(value: str | None, visible: int = 6) -> str:
    if not value:
        return "(vazio)"
    if len(value) <= visible:
        return "*" * len(value)
    return value[:visible] + "..." + ("*" * 4)



def get_jwt_secret_key() -> str:
    return os.getenv("JWT_SECRET_KEY", "trocar_essa_chave_em_producao")


def get_jwt_algorithm() -> str:
    return os.getenv("JWT_ALGORITHM", "HS256")


def get_jwt_expire_minutes() -> int:
    try:
        return int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))
    except ValueError:
        return 1440



def get_frontend_origins() -> list[str]:
    raw = os.getenv("FRONTEND_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    return [item.strip() for item in raw.split(",") if item.strip()]


def get_default_public_business_id() -> int | None:
    raw = get_env('DEFAULT_PUBLIC_BUSINESS_ID')
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None
