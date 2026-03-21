import re
import unicodedata
from datetime import datetime, timedelta

from app.logger import logger
from app.parser import interpretar_texto
from app.storage import (
    salvar_transacao,
    gerar_relatorio,
    salvar_receipt_processado,
    atualizar_receipt_status,
    registrar_ocorrencia_merchant,
    obter_ou_criar_merchant_normalizado,
)
from app.whatsapp_api import enviar_mensagem_texto
from app.access import (
    eh_admin_plataforma,
    buscar_restaurante_por_usuario,
    restaurante_ativo,
)
from app.media_service import baixar_imagem_whatsapp
from app.receipt_service import processar_comprovante
from app.pending_receipts import (
    salvar_comprovante_pendente,
    obter_comprovante_pendente,
    remover_comprovante_pendente,
)
from app.admin_commands import processar_comando_admin, processar_comando_negocio
from app.core_services import (
    ensure_chat_session,
    get_bot_settings,
    get_business_by_legacy_restaurant_id,
    log_chat_message,
    update_chat_session_status,
    upsert_customer_profile,
)
from app.database import conectar
from app.settings import get_default_public_business_id
from app.modules.hospitality.service import (
    list_room_types, criar_reserva_manual, get_effective_rate, list_chat_messages,
    mark_reservation_payment_pending_confirmation,
)


DATE_PATTERN = re.compile(r'(\d{1,2}/\d{1,2}(?:/\d{2,4})?)')
MONTHS = {'janeiro': 1, 'fevereiro': 2, 'marco': 3, 'março': 3, 'abril': 4, 'maio': 5, 'junho': 6, 'julho': 7, 'agosto': 8, 'setembro': 9, 'outubro': 10, 'novembro': 11, 'dezembro': 12}


NUMBER_WORDS = {
    'um': 1, 'uma': 1, 'dois': 2, 'duas': 2, 'tres': 3, 'três': 3, 'quatro': 4, 'cinco': 5,
    'seis': 6, 'sete': 7, 'oito': 8, 'nove': 9, 'dez': 10,
}

INVALID_GUEST_NAME_TERMS = {
    'oi', 'ola', 'olá', 'bom dia', 'boa tarde', 'boa noite', 'quero reservar', 'reserva', 'quero o casal',
    'quero o quarto casal', 'quero o mais barato', 'me passa o pix', 'pix', 'paguei', 'ok', 'sim', 'nao', 'não', 'ola tudo bem', 'olá tudo bem'
}


def _extract_guest_count(texto: str):
    lower = (texto or '').lower()
    if any(term in lower for term in ['casal', 'duas pessoas', '2 pessoas', '2 hóspedes', '2 hospedes']):
        return 2
    if any(term in lower for term in ['família de 4', 'familia de 4', '4 pessoas', '4 hóspedes', '4 hospedes']):
        return 4
    match = re.search(r'(\d+)\s*(h[oó]spede(?:s)?|adult(?:o|os)?|pessoa(?:s)?)', lower)
    if match:
        try:
            return max(1, int(match.group(1)))
        except Exception:
            return None
    word_match = re.search(r'\b(' + '|'.join(map(re.escape, NUMBER_WORDS.keys())) + r')\b\s+(h[oó]spede(?:s)?|adult(?:o|os)?|pessoa(?:s)?)', lower)
    if word_match:
        return NUMBER_WORDS.get(word_match.group(1))
    return None


def _is_checkout_hint(texto: str):
    lower = _normalize_text(texto)
    return any(term in lower for term in ['saida', 'checkout', 'saindo', 'vou sair', 'sairei', 'deixo no dia'])


def _recent_hospitality_context(session_id: int):
    messages = list_chat_messages(session_id)
    checkin = None
    checkout = None
    guest_count = None
    awaiting_checkout = False
    last_single_date = None
    for msg in messages[-20:]:
        body = (msg.get('text_content') or '').strip()
        if not body:
            continue
        if msg.get('direction') == 'outbound' and 'data de saída' in body.lower():
            awaiting_checkout = True
        if msg.get('direction') != 'inbound':
            continue
        msg_dates = _extract_dates(body)
        msg_guests = _extract_guest_count(body)
        if msg_guests:
            guest_count = msg_guests
        if len(msg_dates) >= 2:
            checkin = msg_dates[0]
            checkout = msg_dates[1]
            last_single_date = msg_dates[0]
            awaiting_checkout = False
        elif len(msg_dates) == 1:
            last_single_date = msg_dates[0]
            if _is_checkout_hint(body) and checkin:
                checkout = msg_dates[0]
                awaiting_checkout = False
            elif not checkin:
                checkin = msg_dates[0]
    return {
        'checkin': checkin,
        'checkout': checkout,
        'guest_count': guest_count,
        'awaiting_checkout': awaiting_checkout,
        'last_single_date': last_single_date,
    }


def _is_human_handoff_request(texto: str):
    lower = _normalize_text(texto)
    terms = [
        '/humano', 'falar com atendente', 'falar com um atendente', 'atendente humano',
        'quero falar com atendente', 'quero atendimento humano', 'atendimento humano',
        'gostaria de falar com um atendente', 'me passa para uma pessoa', 'tem alguem ai',
        'quero falar com uma pessoa', 'pode me passar para alguem', 'atendimento com humano',
        'quero um atendente', 'preciso de uma pessoa'
    ]
    return any(term in lower for term in terms)


def _mentions_payment(texto: str):
    lower = _normalize_text(texto)
    return any(term in lower for term in ['pix', 'pagamento', 'pagar', 'sinal', 'link de pagamento', 'chave pix', 'forma de pagamento'])


def _mentions_reservation(texto: str):
    lower = _normalize_text(texto)
    return any(term in lower for term in ['dispon', 'vaga', 'reserva', 'quarto', 'hosped', 'diaria', 'cotacao', 'valor', 'preco', 'estadia', 'acomodacao'])


def _night_count(checkin: str | None, checkout: str | None):
    if not checkin or not checkout:
        return 1
    try:
        start = datetime.fromisoformat(checkin)
        end = datetime.fromisoformat(checkout)
        delta = (end - start).days
        return max(1, delta)
    except Exception:
        return 1


def _quote_room_options(business_id: int, guest_count: int | None, nights: int):
    options = []
    for room in list_room_types(business_id):
        capacity = int(room.get('capacity') or 0)
        active = int(room.get('active') or 0)
        if not active:
            continue
        if guest_count and capacity and capacity < guest_count:
            continue
        rate = float(get_effective_rate(business_id, room.get('code'), room.get('base_rate') or 0))
        options.append({
            'code': room.get('code'),
            'name': room.get('name'),
            'capacity': capacity,
            'beds': room.get('bed_setup') or '-',
            'nightly_rate': rate,
            'total': rate * nights,
        })
    options.sort(key=lambda item: (item['nightly_rate'], item['capacity']))
    return options


def _latest_open_quote(session_id: int, business_id: int):
    conn = conectar(); cur = conn.cursor()
    cur.execute(
        """
        SELECT * FROM reservation_requests
        WHERE session_id = ? AND business_id = ? AND status IN ('lead','quoted')
        ORDER BY id DESC LIMIT 1
        """,
        (session_id, business_id),
    )
    row = cur.fetchone(); conn.close()
    return dict(row) if row else None


def _update_quote_selection(reservation_id: int, room_code: str, room_name: str, total: float, notes_suffix: str = ''):
    conn = conectar(); cur = conn.cursor()
    cur.execute(
        """
        UPDATE reservation_requests
        SET unit_category = ?, quoted_amount = ?, payment_status = 'aguardando_pagamento',
            notes = COALESCE(notes, '') || ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (room_code, total, notes_suffix, reservation_id),
    )
    conn.commit(); conn.close()


def _find_room_choice(texto: str, options: list[dict]):
    lower = _normalize_text(texto)
    if not options:
        return None
    if any(term in lower for term in ['mais barato', 'mais em conta', 'economico', 'economico', 'menor valor']):
        return min(options, key=lambda item: item['nightly_rate'])
    for option in options:
        code = _normalize_text(option.get('code') or '')
        name = _normalize_text(option.get('name') or '')
        if code and code in lower:
            return option
        name_tokens = [tok for tok in name.replace('-', ' ').split() if len(tok) > 2]
        if name_tokens and all(tok in lower for tok in name_tokens[:2]):
            return option
    if 'casal' in lower:
        return next((opt for opt in options if 'casal' in _normalize_text(opt['name']) or 'casal' in _normalize_text(opt['beds'])), None)
    if 'twin' in lower or 'solteiro' in lower:
        return next((opt for opt in options if 'twin' in _normalize_text(opt['name']) or 'solteiro' in _normalize_text(opt['beds'])), None)
    if 'triplo' in lower or '3 pessoas' in lower:
        return next((opt for opt in options if 'triplo' in _normalize_text(opt['name']) or int(opt.get('capacity') or 0) == 3), None)
    if 'familia' in lower or 'família' in texto.lower() or 'crianca' in lower or 'criança' in texto.lower():
        return next((opt for opt in options if 'famil' in _normalize_text(opt['name']) or int(opt.get('capacity') or 0) >= 4), None)
    return None


def _payment_summary(settings: dict, amount: float | None = None):
    pix_key = settings.get('pix_key') or 'CHAVE_PIX_NAO_CONFIGURADA'
    payment_link = settings.get('payment_link_base')
    instructions = settings.get('reservation_payment_instructions') or 'Assim que pagar, envie o comprovante por foto. A confirmação final é feita por um atendente.'
    lines = ['Perfeito 😊 Vou deixar sua pré-reserva pronta para confirmação.']
    if amount:
        lines.append(f'Valor estimado: R$ {float(amount):.2f}')
    lines.append(f'🔑 Chave Pix: {pix_key}')
    if payment_link:
        lines.append(f'🔗 Link de pagamento: {payment_link}')
    lines.append(instructions)
    lines.append('Assim que você enviar o comprovante, eu aviso a equipe para confirmar seu pagamento.')
    return '\n'.join(lines)


def montar_resposta_whatsapp(resultado, restaurant_id: int):
    if resultado['tipo'] == 'despesa':
        valor = resultado['valor'] or 0
        return (
            '✅ Despesa registrada\n'
            f"Categoria: {resultado['categoria']}\n"
            f'Valor: R$ {valor:.2f}'
        )

    if resultado['tipo'] == 'entrada':
        valor = resultado['valor'] or 0
        return (
            '✅ Entrada registrada\n'
            f"Categoria: {resultado['categoria']}\n"
            f'Valor: R$ {valor:.2f}'
        )

    if resultado['tipo'] == 'relatorio':
        relatorio = gerar_relatorio(restaurant_id)
        return (
            '📊 Relatório atual\n'
            f"Entradas: R$ {relatorio['total_entradas']:.2f}\n"
            f"Despesas: R$ {relatorio['total_despesas']:.2f}\n"
            f"Saldo: R$ {relatorio['saldo']:.2f}"
        )

    return 'Não entendi sua mensagem. Exemplo: paguei 120 no mercado'



def montar_resposta_comprovante(resultado_ocr: dict):
    estabelecimento = resultado_ocr.get('estabelecimento') or 'Não identificado'
    valor = resultado_ocr.get('valor_total')
    categoria = resultado_ocr.get('categoria_sugerida') or 'geral'
    texto = resultado_ocr.get('texto_extraido', '').strip()

    if valor is not None:
        return (
            '🧾 Comprovante identificado\n'
            f'Estabelecimento: {estabelecimento}\n'
            f'Categoria sugerida: {categoria}\n'
            f'Valor detectado: R$ {valor:.2f}\n\n'
            'Envie:\n'
            '1 para confirmar\n'
            '2 para cancelar'
        )

    texto_resumido = texto[:500] if texto else 'Nenhum texto identificado.'
    return (
        '🧾 Recebi sua imagem, mas não consegui identificar o valor com segurança.\n\n'
        f'Estabelecimento: {estabelecimento}\n'
        f'Categoria sugerida: {categoria}\n'
        f'Texto lido:\n{texto_resumido}'
    )



def _send_and_log(remetente: str, texto: str, session_id: int | None = None, sender_type: str = 'bot'):
    resposta_envio = enviar_mensagem_texto(texto, remetente)
    if session_id:
        log_chat_message(
            session_id=session_id,
            direction='outbound',
            sender_type=sender_type,
            sender_phone=None,
            message_type='text',
            text_content=texto,
            payload=resposta_envio,
        )
    return resposta_envio



def _normalize_text(texto: str) -> str:
    texto = texto or ''
    texto = unicodedata.normalize('NFKD', texto)
    texto = ''.join(ch for ch in texto if not unicodedata.combining(ch))
    texto = texto.lower().strip()
    texto = re.sub(r'\s+', ' ', texto)
    return texto


def _normalize_partial_date(day: int, month: int | None = None):
    now = datetime.now()
    month = month or now.month
    year = now.year
    try:
        candidate = datetime(year, month, day)
        if candidate.date() < now.date() and month <= now.month:
            candidate = datetime(year + 1, month, day)
        return candidate.strftime('%Y-%m-%d')
    except Exception:
        return None


def _parse_date_raw(raw: str):
    try:
        clean = raw.strip().replace('-', '/')
        if clean.count('/') == 1:
            clean = f'{clean}/{datetime.now().year}'
        day, month, year = clean.split('/')
        if len(year) == 2:
            year = f'20{year}'
        candidate = datetime(int(year), int(month), int(day))
        if candidate.date() < datetime.now().date() and int(month) <= datetime.now().month:
            candidate = datetime(int(year) + 1, int(month), int(day))
        return candidate.strftime('%Y-%m-%d')
    except Exception:
        return None


def _extract_dates(texto: str):
    lower = _normalize_text(texto)
    matches = DATE_PATTERN.findall(texto or '')
    dates = []
    for raw in matches[:2]:
        parsed = _parse_date_raw(raw)
        if parsed:
            dates.append(parsed)
    if dates:
        return dates

    range_match = re.search(r'(?:de\s+)?(\d{1,2})\s*(?:a|ate|até)\s*(\d{1,2})(?:\s+de\s+([a-zç]+))?', lower)
    if range_match:
        month = MONTHS.get((range_match.group(3) or '').strip())
        first = _normalize_partial_date(int(range_match.group(1)), month)
        second = _normalize_partial_date(int(range_match.group(2)), month)
        return [value for value in [first, second] if value]

    month_name_match = re.search(r'(\d{1,2})\s+de\s+([a-zç]+)', lower)
    if month_name_match:
        month = MONTHS.get(month_name_match.group(2).strip())
        only = _normalize_partial_date(int(month_name_match.group(1)), month)
        return [only] if only else []

    single_day = re.search(r'(?:dia\s+)?(\d{1,2})', lower)
    if single_day and any(term in lower for term in ['dispon', 'vaga', 'reserva', 'quarto', 'hosped', 'dia', 'entrada', 'saida', 'saindo', 'checkin', 'checkout']):
        only = _normalize_partial_date(int(single_day.group(1)))
        return [only] if only else []

    return []


def _extract_single_date_after_keywords(texto: str, keywords: list[str]):
    lower = (texto or '').lower()
    for keyword in keywords:
        idx = lower.find(keyword)
        if idx >= 0:
            snippet = texto[idx:]
            dates = _extract_dates(snippet)
            if dates:
                return dates[0]
    return None


def _extract_checkin_checkout_hints(texto: str):
    return {
        'checkin': _extract_single_date_after_keywords(texto, ['entrada', 'check-in', 'checkin', 'entrando', 'dia']),
        'checkout': _extract_single_date_after_keywords(texto, ['saida', 'saída', 'checkout', 'check-out', 'saindo']),
    }


def _first_hospitality_business():
    preferred_id = get_default_public_business_id()
    conn = conectar()
    cur = conn.cursor()
    if preferred_id:
        cur.execute('SELECT * FROM businesses WHERE id = ? LIMIT 1', (preferred_id,))
        row = cur.fetchone()
        if row:
            conn.close()
            return dict(row)
    cur.execute(
        """
        SELECT * FROM businesses
        WHERE business_type = 'hospitality' AND status = 'ativo'
        ORDER BY id ASC
        LIMIT 1
        """
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None



def _responder_nao_autorizado(remetente: str):
    resposta = enviar_mensagem_texto(
        'Seu número não está autorizado para usar este sistema.',
        remetente,
    )
    logger.info('RESPOSTA NÃO AUTORIZADO: %s', resposta)
    return {'ok': True}



def _responder_restaurante_suspenso(remetente: str):
    resposta = enviar_mensagem_texto(
        'Este restaurante está suspenso. Fale com o administrador.',
        remetente,
    )
    logger.info('RESPOSTA RESTAURANTE SUSPENSO: %s', resposta)
    return {'ok': True}



def _confirmar_comprovante_pendente(remetente: str, restaurant_id: int, comprovante_pendente: dict, session_id: int | None = None):
    valor = comprovante_pendente.get('valor_total')
    estabelecimento = comprovante_pendente.get('estabelecimento') or 'comprovante'
    categoria = comprovante_pendente.get('categoria_sugerida') or 'geral'
    receipt_id = comprovante_pendente.get('receipt_id')
    merchant_id = comprovante_pendente.get('merchant_id')

    transacao = {
        'tipo': 'despesa',
        'categoria': categoria,
        'valor': valor,
        'descricao': estabelecimento,
    }

    transacao_id = salvar_transacao(
        restaurant_id,
        transacao,
        receipt_id=receipt_id,
        merchant_id=merchant_id,
    )

    if receipt_id:
        atualizar_receipt_status(
            receipt_id,
            status='confirmado',
            categoria_confirmada=categoria,
            transaction_id=transacao_id,
        )

    if merchant_id:
        registrar_ocorrencia_merchant(merchant_id, categoria_default=categoria)

    remover_comprovante_pendente(remetente)
    resposta = f'✅ Comprovante confirmado e despesa registrada.\nCategoria: {categoria}\nValor: R$ {valor:.2f}'
    resposta_envio = _send_and_log(remetente, resposta, session_id=session_id)
    logger.info('RESPOSTA CONFIRMAÇÃO: %s', resposta_envio)
    return {'ok': True}



def _cancelar_comprovante_pendente(remetente: str, comprovante_pendente: dict, session_id: int | None = None):
    receipt_id = comprovante_pendente.get('receipt_id')
    if receipt_id:
        atualizar_receipt_status(receipt_id, status='cancelado')

    remover_comprovante_pendente(remetente)
    resposta = _send_and_log(remetente, '❌ Comprovante cancelado.', session_id=session_id)
    logger.info('RESPOSTA CANCELAMENTO: %s', resposta)
    return {'ok': True}



def _processar_mensagem_admin(mensagem: dict, remetente: str):
    texto = mensagem['text']['body'].strip()
    resposta_admin = processar_comando_admin(texto, admin_phone=remetente)
    resposta_envio = enviar_mensagem_texto(resposta_admin, remetente)
    logger.info('RESPOSTA ADMIN: %s', resposta_envio)
    return {'ok': True}



def _processar_mensagem_negocio(mensagem: dict, remetente: str, business_context: dict, session_id: int | None = None):
    texto = mensagem['text']['body'].strip()
    resposta = processar_comando_negocio(texto, business_context, admin_phone=remetente)
    resposta_envio = _send_and_log(remetente, resposta, session_id=session_id, sender_type='human')
    logger.info('RESPOSTA COMANDO NEGOCIO: %s', resposta_envio)
    return {'ok': True}



def _processar_mensagem_texto(mensagem: dict, remetente: str, restaurant_id: int, session_id: int | None = None):
    texto = mensagem['text']['body'].strip()
    comprovante_pendente = obter_comprovante_pendente(remetente)

    if comprovante_pendente:
        if texto == '1':
            return _confirmar_comprovante_pendente(remetente, restaurant_id, comprovante_pendente, session_id=session_id)
        if texto == '2':
            return _cancelar_comprovante_pendente(remetente, comprovante_pendente, session_id=session_id)

    resultado = interpretar_texto(texto)

    if resultado['tipo'] in ['entrada', 'despesa']:
        salvar_transacao(restaurant_id, resultado)

    resposta_texto = montar_resposta_whatsapp(resultado, restaurant_id)
    resposta_envio = _send_and_log(remetente, resposta_texto, session_id=session_id)
    logger.info('RESPOSTA TEXTO: %s', resposta_envio)
    return {'ok': True}

def _is_valid_guest_name(value: str | None) -> bool:
    if not value:
        return False

    text = value.strip()
    if not text:
        return False

    lower = text.lower().strip()

    invalid_exact = {
        "oi",
        "ola",
        "olá",
        "bom dia",
        "boa tarde",
        "boa noite",
        "ok",
        "pix",
        "paguei",
        "segue comprovante",
        "quero reservar",
        "quero o casal",
        "quero o quarto casal",
        "me passa o pix",
    }

    if lower in invalid_exact:
        return False

    # evita textos muito curtos ou só números
    if len(text) < 3:
        return False

    if re.fullmatch(r"[\d\W_]+", text):
        return False

    # deve ter pelo menos uma letra
    if not re.search(r"[a-zA-ZÀ-ÿ]", text):
        return False

    return True


def _looks_like_guest_names(value: str | None) -> bool:
    if not value:
        return False

    text = value.strip()
    if not text:
        return False

    # aceita nome único, nome completo ou lista separada por vírgula
    if len(text) < 3:
        return False

    # evita frases típicas de intenção
    lower = text.lower()
    blocked_terms = [
        "quero",
        "reservar",
        "pix",
        "comprovante",
        "garagem",
        "piscina",
        "localizacao",
        "localização",
        "endereco",
        "endereço",
        "minha reserva",
        "status",
        "casal",
        "twin",
        "triplo",
        "familia",
        "família",
        "quarto",
        "mais barato",
        "mais em conta",
    ]
    if any(term in lower for term in blocked_terms):
        return False

    # precisa parecer nome, não pergunta
    if "?" in text:
        return False

    return bool(re.search(r"[a-zA-ZÀ-ÿ]", text))

def _processar_mensagem_imagem(mensagem: dict, remetente: str, restaurant_id: int, session_id: int | None = None):
    media_id = mensagem['image']['id']
    logger.info('MEDIA ID RECEBIDO: %s', media_id)

    caminho_imagem, info_midia = baixar_imagem_whatsapp(media_id)
    logger.info('CAMINHO IMAGEM: %s', caminho_imagem)
    logger.info('INFO MIDIA: %s', info_midia)

    if not caminho_imagem:
        resposta = _send_and_log(
            remetente,
            'Não consegui baixar a imagem enviada. Verifique o token da API do WhatsApp e tente novamente.',
            session_id=session_id,
        )
        logger.info('RESPOSTA ERRO MIDIA: %s', resposta)
        return {'ok': True}

    resultado_ocr = processar_comprovante(caminho_imagem)
    merchant_info = None
    if resultado_ocr.get('estabelecimento') and resultado_ocr['estabelecimento'] != 'Não identificado':
        merchant_info = obter_ou_criar_merchant_normalizado(
            restaurant_id=restaurant_id,
            nome_detectado=resultado_ocr['estabelecimento'],
            category_default=resultado_ocr.get('categoria_sugerida'),
        )
        if merchant_info and merchant_info.get('nome'):
            resultado_ocr['estabelecimento'] = merchant_info['nome']
            resultado_ocr['merchant_id'] = merchant_info['id']

    receipt_status = 'pendente_confirmacao' if resultado_ocr.get('valor_total') is not None else 'sem_valor_detectado'
    receipt_salvo = salvar_receipt_processado(
        restaurante_id=restaurant_id,
        telefone=remetente,
        caminho_imagem=caminho_imagem,
        resultado_ocr=resultado_ocr,
        media_id=media_id,
        status=receipt_status,
    )

    resultado_ocr['receipt_id'] = receipt_salvo['id']
    resultado_ocr['merchant_id'] = receipt_salvo.get('merchant_id') or resultado_ocr.get('merchant_id')
    if receipt_salvo.get('categoria_sugerida'):
        resultado_ocr['categoria_sugerida'] = receipt_salvo['categoria_sugerida']
    if receipt_salvo.get('merchant_name'):
        resultado_ocr['estabelecimento'] = receipt_salvo['merchant_name']

    if resultado_ocr.get('valor_total') is not None:
        salvar_comprovante_pendente(remetente, resultado_ocr)

    resposta_comprovante = montar_resposta_comprovante(resultado_ocr)
    resposta_envio = _send_and_log(remetente, resposta_comprovante, session_id=session_id)
    logger.info('RESPOSTA ENVIO COMPROVANTE: %s', resposta_envio)
    return {'ok': True}





def _find_latest_customer_reservation_info(business_id: int, phone: str, confirmed_only: bool = False):
    conn = conectar(); cur = conn.cursor()
    query = """
        SELECT id, guest_name, guest_phone, checkin_date, checkout_date, guest_count,
               unit_category, quoted_amount, status, payment_status, created_at, updated_at
        FROM reservation_requests
        WHERE business_id = ? AND guest_phone = ?
    """
    params = [business_id, phone]
    if confirmed_only:
        query += " AND status = 'confirmada'"
    query += " ORDER BY datetime(updated_at) DESC, id DESC LIMIT 1"
    cur.execute(query, tuple(params))
    row = cur.fetchone(); conn.close()
    return dict(row) if row else None


def _update_reservation_guest_names(reservation_id: int, business_id: int, phone: str, guest_name: str, session_id: int | None = None):
    conn = conectar(); cur = conn.cursor()
    cur.execute(
        "UPDATE reservation_requests SET guest_name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (guest_name, reservation_id),
    )
    if session_id:
        cur.execute(
            "UPDATE chat_sessions SET customer_name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (guest_name, session_id),
        )
    conn.commit(); conn.close()
    try:
        upsert_customer_profile(business_id, phone, guest_name)
    except Exception:
        pass


def _looks_like_guest_names(texto: str):
    lower = _normalize_text(texto)
    if not _is_valid_guest_name(texto):
        return False
    if _extract_dates(texto) or _mentions_payment(texto) or _mentions_reservation(texto):
        return False
    blocked_terms = ['pix', 'pagar', 'paguei', 'comprovante', 'garagem', 'piscina', 'localizacao', 'localização', 'endereco', 'endereço', 'reserva', 'quarto', 'valor', 'checkin', 'checkout']
    if any(term in lower for term in blocked_terms):
        return False
    return bool(re.fullmatch(r"[A-Za-zÀ-ÿ0-9 ,.&\-]{3,120}", texto.strip())) and any(ch.isalpha() for ch in texto)


def _location_response(settings: dict):
    lines = []
    public_name = settings.get('public_business_name') or 'a pousada'
    if settings.get('location_text'):
        lines.append(str(settings.get('location_text')).strip())
    else:
        parts = [settings.get('street_address'), settings.get('neighborhood'), settings.get('city_name'), settings.get('state_code')]
        address = ', '.join([str(part).strip() for part in parts if part and str(part).strip()])
        if address:
            lines.append(f'{public_name} fica em {address}.')
    if settings.get('public_contact_phone'):
        lines.append(f"☎️ Contato da recepção: {settings.get('public_contact_phone')}")
    if settings.get('maps_link'):
        lines.append(f"📍 Localização: {settings.get('maps_link')}")
    if not lines:
        return 'Ainda não tenho a localização cadastrada aqui. Posso te encaminhar para um atendente da equipe 😊'
    return '\n'.join(lines)


def _faq_response(texto: str, settings: dict):
    lower = _normalize_text(texto)
    if any(term in lower for term in ['localizacao', 'localização', 'endereco', 'endereço', 'onde fica', 'como chegar']):
        return _location_response(settings)
    if any(term in lower for term in ['garagem', 'estacionamento', 'vaga de carro']):
        if settings.get('garage_info'):
            return str(settings.get('garage_info')).strip()
        return 'Posso confirmar essa informação com a equipe para você 😊'
    if 'piscina' in lower:
        if settings.get('pool_info'):
            return str(settings.get('pool_info')).strip()
        return 'Posso confirmar essa informação com a equipe para você 😊'
    if any(term in lower for term in ['cafe da manha', 'café da manhã', 'cafe da manhã', 'cafe incluso', 'tem cafe']):
        if settings.get('breakfast_info'):
            return str(settings.get('breakfast_info')).strip()
        return 'Posso te passar isso certinho com a equipe 😊'
    if any(term in lower for term in ['pet', 'animais', 'cachorro', 'gato']):
        if settings.get('pet_policy'):
            return str(settings.get('pet_policy')).strip()
        return 'Posso confirmar a política para pets com a equipe 😊'
    if any(term in lower for term in ['estrutura', 'comodidades', 'amenities', 'o que tem', 'tem o que']):
        if settings.get('amenities_text'):
            return str(settings.get('amenities_text')).strip()
    if any(term in lower for term in ['checkin', 'check-in', 'entrada']) and 'reserva' not in lower:
        if settings.get('checkin_time'):
            return f"Nosso check-in padrão é a partir de {settings.get('checkin_time')} 😊"
    if any(term in lower for term in ['checkout', 'check-out', 'saida', 'saída']) and 'reserva' not in lower:
        if settings.get('checkout_time'):
            return f"Nosso check-out padrão vai até {settings.get('checkout_time')} 😊"
    return None


def _reservation_info_response(texto: str, business: dict, session: dict):
    lower = _normalize_text(texto)
    if not any(term in lower for term in ['minha reserva', 'reserva confirmada', 'sobre minha reserva', 'dados da reserva', 'check-in', 'checkout', 'check in', 'check out', 'ja reservei', 'já reservei', 'tenho reserva', 'ja comprei', 'já comprei', 'minha hospedagem', 'minha estadia', 'quarto que reservei', 'status da reserva']):
        return None
    reservation = _find_latest_customer_reservation_info(business['id'], session['customer_phone'])
    if not reservation:
        return 'Não encontrei uma reserva recente vinculada a este número. Se quiser, me diga as datas desejadas que eu te ajudo com uma nova cotação.'
    lines = []
    if reservation.get('status') == 'confirmada':
        lines.append('Encontrei sua reserva confirmada ✅')
    else:
        lines.append('Encontrei sua reserva mais recente 😊')
    if reservation.get('guest_name') and _is_valid_guest_name(reservation.get('guest_name')):
        lines.append(f"Hóspede principal: {reservation.get('guest_name')}")
    if reservation.get('checkin_date') or reservation.get('checkout_date'):
        lines.append(f"Check-in: {reservation.get('checkin_date') or '-'}")
        lines.append(f"Check-out: {reservation.get('checkout_date') or '-'}")
    settings = get_bot_settings(business['id']) or {}
    if settings.get('checkin_time') or settings.get('checkout_time'):
        lines.append(f"Horários padrão: check-in {settings.get('checkin_time') or '-'} | check-out {settings.get('checkout_time') or '-'}")
    if reservation.get('unit_category'):
        lines.append(f"Quarto: {reservation.get('unit_category')}")
    if reservation.get('guest_count'):
        lines.append(f"Hóspedes: {reservation.get('guest_count')}")
    if reservation.get('quoted_amount'):
        lines.append(f"Valor: R$ {float(reservation.get('quoted_amount') or 0):.2f}")
    lines.append(f"Status: {reservation.get('status')} | Pagamento: {reservation.get('payment_status')}")
    return '\n'.join(lines)

def _reply_hospitality(texto: str, session: dict, business: dict):
    settings = get_bot_settings(business['id']) or {}
    lower = _normalize_text(texto)

    if session['status'] == 'human_active':
        return None

    reservation_info = _reservation_info_response(texto, business, session)
    if reservation_info:
        return reservation_info

    faq = _faq_response(texto, settings)
    if faq:
        return faq

    if _is_human_handoff_request(texto):
        update_chat_session_status(session['id'], 'human_requested', handoff_reason='Cliente pediu atendimento humano')
        return 'Perfeito. Vou encaminhar seu atendimento para uma pessoa da equipe e pausar as respostas automáticas por enquanto.'

    context = _recent_hospitality_context(session['id'])
    latest_quote = _latest_open_quote(session['id'], business['id'])
    latest_quote_guest = latest_quote.get('guest_count') if latest_quote else None
    current_guest_name = latest_quote.get('guest_name') if latest_quote else None
    session_guest_name = session.get('customer_name')

    guest_count = _extract_guest_count(texto) or context.get('guest_count') or latest_quote_guest

    dates = _extract_dates(texto)
    hints = _extract_checkin_checkout_hints(texto)
    mentions_reservation = _mentions_reservation(texto) or bool(dates) or bool(guest_count)

    checkin = dates[0] if len(dates) >= 1 else None
    checkout = dates[1] if len(dates) >= 2 else None

    if hints.get('checkin'):
        checkin = hints['checkin']
    if hints.get('checkout'):
        checkout = hints['checkout']

    prior_checkin = context.get('checkin') or (latest_quote.get('checkin_date') if latest_quote else None)
    prior_checkout = context.get('checkout') or (latest_quote.get('checkout_date') if latest_quote else None)

    if len(dates) == 1 and context.get('awaiting_checkout') and prior_checkin and prior_checkin != dates[0]:
        checkin = prior_checkin
        checkout = dates[0]
    elif len(dates) == 1 and _is_checkout_hint(texto) and prior_checkin:
        checkin = prior_checkin
        checkout = dates[0]
    elif len(dates) == 1 and mentions_reservation and prior_checkin and prior_checkin != dates[0] and not prior_checkout:
        checkin = prior_checkin
        checkout = dates[0]
    elif len(dates) == 1 and (' so uma noite' in lower or 'só uma noite' in (texto or '').lower() or '1 noite' in lower):
        checkin = dates[0]
        checkout = (datetime.fromisoformat(dates[0]) + timedelta(days=1)).strftime('%Y-%m-%d')

    if not checkin and prior_checkin and any(term in lower for term in ['reserv', 'quero', 'estadia', 'hosped', 'mais barato', 'casal', 'familia', 'twin', 'triplo']):
        checkin = prior_checkin
    if not checkout and prior_checkout and any(term in lower for term in ['pix', 'quero', 'pode ser', 'mais barato', 'casal', 'familia', 'twin', 'triplo']):
        checkout = prior_checkout

    nights = _night_count(checkin, checkout)
    quote_options = _quote_room_options(business['id'], guest_count, nights if checkin and checkout else 1)
    chosen_room = _find_room_choice(texto, quote_options)

    if chosen_room and checkin and checkout:
        if latest_quote:
            _update_quote_selection(
                latest_quote['id'],
                chosen_room['code'],
                chosen_room['name'],
                chosen_room['total'],
                notes_suffix=f"\nQuarto escolhido pelo cliente: {chosen_room['name']}",
            )
            latest_quote = _latest_open_quote(session['id'], business['id'])
        else:
            latest_quote = criar_reserva_manual(
                business_id=business['id'],
                guest_name='',
                guest_phone=session['customer_phone'],
                checkin_date=checkin,
                checkout_date=checkout,
                guest_count=guest_count,
                unit_category=chosen_room['code'],
                quoted_amount=chosen_room['total'],
                status='quoted',
                payment_status='aguardando_pagamento',
                notes=f'Quarto escolhido automaticamente a partir da mensagem: {texto[:400]}',
                session_id=session['id'],
                source='whatsapp',
                sync_status='pending_external_sync',
            )

        guest_name = latest_quote.get('guest_name') if latest_quote else None

        if not _is_valid_guest_name(guest_name):
            return '\n'.join([
                f"Perfeito 😊 Separei a opção {chosen_room['name']} para sua reserva.",
                f"Período: {checkin} até {checkout}",
                f"Hóspedes: {guest_count or chosen_room['capacity']}",
                f"Valor estimado total: R$ {chosen_room['total']:.2f}",
                '',
                'Antes de te passar o Pix, me envie por favor o nome do hóspede principal ou os nomes dos hóspedes.'
            ])

        resumo = [
            f"Perfeito 😊 Separei a opção {chosen_room['name']} para sua cotação.",
            f"Período: {checkin} até {checkout}",
            f"Hóspedes: {guest_count or chosen_room['capacity']}",
            f"Valor estimado total: R$ {chosen_room['total']:.2f}",
            '',
            _payment_summary(settings, chosen_room['total']),
        ]
        return '\n'.join(resumo)

    if latest_quote and not latest_quote.get('guest_name') and _looks_like_guest_names(texto):
        guest_names = texto.strip()
        _update_reservation_guest_names(latest_quote['id'], business['id'], session['customer_phone'], guest_names, session_id=session['id'])
        amount = float(latest_quote.get('quoted_amount') or 0) if latest_quote.get('quoted_amount') else None
        return f'Perfeito 😊 Já anotei o(s) hóspede(s): {guest_names}.\n\n' + _payment_summary(settings, amount)

    if any(term in lower for term in ['paguei', 'ja paguei', 'já paguei', 'enviei o comprovante', 'segue comprovante', 'mandei o comprovante']):
        if latest_quote:
            update_chat_session_status(session['id'], 'awaiting_payment_confirmation', handoff_reason='Cliente informou pagamento/comprovante via texto')
            return 'Perfeito 😊 Assim que você enviar o comprovante por imagem, eu aviso a equipe para validar o pagamento e concluir a reserva.'
        return 'Perfeito 😊 Assim que você enviar o comprovante por imagem, eu aviso a equipe para validar o pagamento.'

    if _mentions_payment(texto) and latest_quote and latest_quote.get('quoted_amount'):
        if not _is_valid_guest_name(latest_quote.get('guest_name')):
            return 'Consigo sim 😊 Antes de te passar o Pix, me envie por favor o nome do hóspede principal ou a lista de hóspedes.'
        return _payment_summary(settings, float(latest_quote['quoted_amount']))
    if _mentions_payment(texto):
        return _payment_summary(settings, None)

    if checkin and checkout and mentions_reservation:
        options = _quote_room_options(business['id'], guest_count, nights)
        best = options[0] if options else None
        if best:
            criar_reserva_manual(
                business_id=business['id'],
                guest_name='',
                guest_phone=session['customer_phone'],
                checkin_date=checkin,
                checkout_date=checkout,
                guest_count=guest_count,
                unit_category=best['code'],
                quoted_amount=best['total'],
                status='quoted',
                payment_status='aguardando_pagamento',
                notes=f'Cotação automática criada a partir da mensagem: {texto[:400]}',
                session_id=session['id'],
                source='whatsapp',
                sync_status='pending_external_sync',
            )
            response_lines = [
                'Encontrei opções iniciais para sua estadia 😊',
                f'Check-in: {checkin}',
                f'Check-out: {checkout}',
                f'Diárias consideradas: {nights}',
            ]
            if guest_count:
                response_lines.append(f'Hóspedes: {guest_count}')
            response_lines.append('')
            for option in options[:4]:
                response_lines.append(f"• {option['name']} ({option['beds']}) — R$ {option['nightly_rate']:.2f}/diária | total estimado R$ {option['total']:.2f}")
            response_lines.append('')
            response_lines.append('Se quiser seguir, pode me responder com o tipo desejado, por exemplo: quero o casal, quero o mais barato ou me passa o pix.')
            return '\n'.join(response_lines)
        return 'Recebi suas datas, mas ainda não encontrei um tipo de quarto compatível configurado. Posso te encaminhar para um atendente da equipe.'

    if mentions_reservation and checkin and not checkout:
        if guest_count:
            return f'Perfeito 😊 Já anotei entrada em {checkin} para {guest_count} hóspede(s). Agora me confirme só a data de saída para eu montar a cotação.'
        return f'Perfeito 😊 Já anotei entrada em {checkin}. Agora me confirme só a data de saída e, se quiser, quantos hóspedes serão.'

    if any(term in lower for term in ['valor', 'preco', 'tarifa', 'quanto fica', 'quanto seria']):
        room_types = _quote_room_options(business['id'], guest_count, 1)
        if room_types:
            preview = '\n'.join(f"• {item['name']}: a partir de R$ {item['nightly_rate']:.2f}/diária" for item in room_types[:4])
            return 'Os valores variam conforme data, ocupação e tipologia. Hoje, as bases configuradas estão assim:\n' + preview + '\n\nMe envie as datas desejadas e a quantidade de hóspedes para eu montar a cotação completa.'
        return 'Os valores variam conforme data, ocupação e tipo de acomodação. Me envie as datas desejadas e a quantidade de hóspedes que eu organizo a cotação inicial.'

    if any(term in lower for term in ['oi', 'ola', 'bom dia', 'boa tarde', 'boa noite']):
        assistant = settings.get('assistant_name') or 'assistente da pousada'
        public_name = settings.get('public_business_name') or business.get('nome') or 'nossa pousada'
        return f'Olá 😊 Eu sou a {assistant} da {public_name}. Posso te ajudar com disponibilidade, valores, reserva, localização e dúvidas da hospedagem. Para uma cotação rápida, me envie as datas e a quantidade de hóspedes. Exemplo: 10/04 a 12/04 para 2 hóspedes.'

    if dates or guest_count:
        if len(dates) == 1 and not checkout:
            return 'Já peguei parte das informações 😊 Me confirme só a data de saída para eu montar a cotação. Exemplo: saída 11/03.'
        return 'Recebi suas informações e já estou montando a melhor opção. Se quiser, também posso te passar direto para um atendente.'

    return settings.get('fallback_message') or 'Recebi sua mensagem 😊 Posso te ajudar com disponibilidade, valores e reservas. Se quiser, me envie algo como 10/04 a 12/04 para 2 pessoas.'

def _processar_fluxo_publico_hospitality(mensagem: dict, remetente: str, business: dict):
    session = ensure_chat_session(business['id'], remetente)

    if mensagem.get('type') == 'text':
        texto = mensagem['text']['body'].strip()
        log_chat_message(session['id'], 'inbound', 'customer', remetente, 'text', texto, payload=mensagem)
        resposta = _reply_hospitality(texto, session, business)
        if resposta:
            _send_and_log(remetente, resposta, session_id=session['id'])
        return {'ok': True}

    if mensagem.get('type') == 'image':
        log_chat_message(session['id'], 'inbound', 'customer', remetente, 'image', '[imagem]', payload=mensagem)
        pending = mark_reservation_payment_pending_confirmation(
            business_id=business['id'],
            guest_phone=remetente,
            proof_note='Comprovante recebido por imagem via WhatsApp.',
            session_id=session['id'],
            customer_name=session.get('customer_name'),
        )
        if pending:
            resposta = 'Recebi seu comprovante 😊 Já avisei a equipe e sua reserva ficou em aguardando confirmação de pagamento. Assim que validarem, te avisamos por aqui.'
        else:
            resposta = 'Recebi sua imagem 😊 Se ela for um comprovante, a equipe consegue conferir manualmente no painel.'
        _send_and_log(remetente, resposta, session_id=session['id'])
        return {'ok': True}

    if mensagem.get('type') == 'unsupported':
        log_chat_message(session['id'], 'inbound', 'customer', remetente, 'unsupported', '[mensagem não suportada]', payload=mensagem)
        resposta = 'Recebi seu envio, mas ele chegou em um formato que o WhatsApp não liberou para leitura aqui 😕\n\nPode reenviar como foto normal da galeria/câmera ou mandar uma mensagem como “paguei” para eu avisar a equipe?'
        _send_and_log(remetente, resposta, session_id=session['id'])
        return {'ok': True}

    log_chat_message(session['id'], 'inbound', 'customer', remetente, mensagem.get('type') or 'unknown', '[mensagem não tratada]', payload=mensagem)
    resposta = 'Recebi sua mensagem 😊 Se preferir, me envie em texto ou como foto normal para eu continuar por aqui.'
    _send_and_log(remetente, resposta, session_id=session['id'])
    return {'ok': True}



def processar_evento_whatsapp(dados: dict):
    entry = dados.get('entry', [])
    if not entry:
        return {'ok': True}

    changes = entry[0].get('changes', [])
    if not changes:
        return {'ok': True}

    value = changes[0].get('value', {})
    messages = value.get('messages', [])
    if not messages:
        return {'ok': True}

    mensagem = messages[0]
    remetente = mensagem['from']

    if eh_admin_plataforma(remetente) and mensagem.get('type') == 'text':
        return _processar_mensagem_admin(mensagem, remetente)

    restaurante = buscar_restaurante_por_usuario(remetente)
    logger.info('REMETENTE: %s', remetente)
    logger.info('RESTAURANTE ENCONTRADO: %s', restaurante)

    if restaurante:
        if not restaurante_ativo(restaurante):
            return _responder_restaurante_suspenso(remetente)

        restaurant_id = restaurante['restaurant_id']
        business = get_business_by_legacy_restaurant_id(restaurant_id)
        session = ensure_chat_session(business['id'], remetente) if business else None
        if mensagem.get('type') == 'text':
            texto = mensagem['text']['body'].strip()
            if session:
                log_chat_message(session['id'], 'inbound', 'authorized_user', remetente, 'text', texto, payload=mensagem)
            if business and business.get('business_type') == 'hospitality' and texto.startswith('/'):
                contexto_negocio = dict(restaurante)
                contexto_negocio['business_id'] = business['id']
                return _processar_mensagem_negocio(mensagem, remetente, contexto_negocio, session_id=session['id'] if session else None)
            return _processar_mensagem_texto(mensagem, remetente, restaurant_id, session_id=session['id'] if session else None)
        if mensagem.get('type') == 'image':
            if session:
                log_chat_message(session['id'], 'inbound', 'authorized_user', remetente, 'image', '[imagem]', payload=mensagem)
            return _processar_mensagem_imagem(mensagem, remetente, restaurant_id, session_id=session['id'] if session else None)
        if mensagem.get('type') == 'unsupported' and session:
            log_chat_message(session['id'], 'inbound', 'authorized_user', remetente, 'unsupported', '[mensagem não suportada]', payload=mensagem)
            _send_and_log(remetente, 'Recebi seu envio, mas esse formato não veio legível aqui. Se for um comprovante, mande como foto normal ou PDF.', session_id=session['id'], sender_type='human')
            return {'ok': True}
        logger.info('TIPO DE MENSAGEM IGNORADO: %s', mensagem.get('type'))
        return {'ok': True}

    business = _first_hospitality_business()
    if business:
        return _processar_fluxo_publico_hospitality(mensagem, remetente, business)

    return _responder_nao_autorizado(remetente)
