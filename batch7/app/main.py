from fastapi import FastAPI, Request, Query
from contextlib import asynccontextmanager
import threading
import time
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
import traceback

from app.logger import logger
from app.discord_notifier import enviar_alerta_discord
from app.database import criar_tabelas
from app.models import Mensagem
from app.parser import interpretar_texto
from app.access import seed_admin_principal
from app.settings import (
    get_verify_token,
    get_whatsapp_phone_number_id,
    get_whatsapp_token,
    mask_secret,
    get_frontend_origins,
)
from app.message_service import processar_evento_whatsapp
from app.auth_router import router as auth_router
from app.dashboard_router import router as dashboard_router
from app.core_router import router as core_router
from app.transactions_router import router as transactions_router
from app.management_router import router as management_router
from app.modules.hospitality.router import router as hospitality_router
from app.modules.restaurant.router import router as restaurant_router
from app.modules.beauty.router import router as beauty_router
from app.modules.rental.router import router as rental_router
from app.modules.hospitality.service import prompt_daily_rates_if_needed


stop_scheduler = threading.Event()


def _rate_prompt_worker():
    while not stop_scheduler.is_set():
        try:
            sent = prompt_daily_rates_if_needed()
            if sent:
                logger.info('RATE PROMPT WORKER | prompts enviados=%s', sent)
        except Exception:
            logger.exception('Falha no worker de coleta de tarifas')
        stop_scheduler.wait(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    criar_tabelas()
    seed_admin_principal()
    worker = threading.Thread(target=_rate_prompt_worker, daemon=True)
    worker.start()
    yield
    stop_scheduler.set()


app = FastAPI(lifespan=lifespan)

frontend_origins = get_frontend_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(core_router)
app.include_router(transactions_router)
app.include_router(management_router)
app.include_router(hospitality_router)
app.include_router(restaurant_router)
app.include_router(beauty_router)
app.include_router(rental_router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    erro_completo = traceback.format_exc()

    logger.error("ERRO GLOBAL NO SERVIDOR")
    logger.error(erro_completo)

    enviar_alerta_discord(
        "Erro global no servidor",
        erro_completo
    )

    return {
        "ok": False,
        "erro": "Erro interno do servidor"
    }


VERIFY_TOKEN = get_verify_token()

logger.info(
    "CONFIG INICIAL | verify_token=%s | phone_id=%s | token=%s | cors=%s",
    VERIFY_TOKEN,
    get_whatsapp_phone_number_id() or "(vazio)",
    mask_secret(get_whatsapp_token()),
    ", ".join(frontend_origins) if frontend_origins else "(nenhuma)",
)


@app.get("/")
def home():
    return {"mensagem": "Servidor do bot funcionando!"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/mensagem")
def receber_mensagem(mensagem: Mensagem):
    resultado = interpretar_texto(mensagem.texto)
    return {"ok": True, "resultado": resultado}


@app.get("/webhook")
def verificar_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return PlainTextResponse(hub_challenge)
    return PlainTextResponse("Token inválido", status_code=403)


@app.post("/webhook")
async def receber_webhook(request: Request):
    dados = await request.json()
    logger.info("WEBHOOK RECEBIDO")
    logger.info(str(dados))

    try:
        return processar_evento_whatsapp(dados)
    except Exception:
        erro_completo = traceback.format_exc()
        logger.error("ERRO NO WEBHOOK")
        logger.error(erro_completo)

        enviar_alerta_discord(
            "Erro no webhook",
            erro_completo
        )
        return {"ok": True}
