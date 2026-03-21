from datetime import date, timedelta

from app.admin_service import (
    cadastrar_restaurante, adicionar_usuario_restaurante, ativar_restaurante,
    desativar_restaurante, resetar_transacoes_restaurante, listar_restaurantes,
    criar_login_web_restaurante, listar_usuarios_restaurante, remover_usuario_restaurante,
    obter_restaurante, listar_admins_plataforma,
)
from app.database import conectar
from app.core_services import update_chat_session_status, upsert_bot_settings
from app.modules.hospitality.service import (
    upsert_room_type, list_room_types, summarize_hospitality_operations, delete_room_type,
    find_session_by_phone, criar_reserva_manual, set_manual_rate,
    manual_rates_status_text, list_pending_payment_confirmations,
    confirm_reservation_payment,
)

BUSINESS_TYPES = {'hospitality', 'restaurant', 'retail', 'services', 'beauty', 'rental'}


def _admin_help():
    return (
        'Comandos da plataforma:\n'
        '/plataforma listar negocios\n'
        '/plataforma criar negocio NOME | hospitality\n'
        '/plataforma negocio ID\n'
        '/plataforma listar usuarios ID\n'
        '/plataforma adicionar usuario ID | Nome | 557399999999 | admin\n'
        '/plataforma remover usuario ID | 557399999999\n'
        '/plataforma listar admins\n'
        '/plataforma definir tipo ID | hospitality\n'
        '/plataforma criar login web ID | email@dominio.com | Nome do Admin\n'
        '/quem sou'
    )


def _format_business_line(item: dict):
    return f"ID {item['id']} • {item['nome']} • tipo: {item.get('business_type') or 'restaurant'} • status: {item.get('status') or item.get('restaurant_status') or '-'}"


def _platform_identity(admin_phone: str | None = None):
    lines = ['👤 Você está falando como administrador da plataforma.']
    if admin_phone:
        lines.append(f'Telefone: {admin_phone}')
    lines.append('Use /plataforma listar negocios para começar ou /plataforma listar admins para ver os administradores mestres.')
    return '\n'.join(lines)


def _set_business_type(restaurant_id: int, business_type: str):
    conn = conectar(); cur = conn.cursor(); cur.execute("UPDATE businesses SET business_type = ?, updated_at = CURRENT_TIMESTAMP WHERE legacy_restaurant_id = ?", (business_type, restaurant_id)); conn.commit(); conn.close()


def _room_types_help():
    return (
        'Comandos operacionais de hospedagem:\n'
        '/config listar quartos\n'
        '/config criar tipo CODIGO | Nome | quantidade | camas | capacidade | valor\n'
        '/config quantidade CODIGO 8\n'
        '/config camas CODIGO 1 casal + 1 solteiro\n'
        '/config capacidade CODIGO 3\n'
        '/config valor CODIGO 320\n'
        '/config pix sua-chave\n'
        '/config modo manual_rates | pms_integrated\n'
        '/config coleta daily 08:00\n'
        '/tarifas\n'
        '/tarifas hoje CODIGO 320, OUTRO 420\n'
        '/tarifas semana CODIGO 320, OUTRO 420\n'
        '/reserva balcão Nome; 557399999999; CODIGO; 2026-03-20; 2026-03-22; 560; observação\n'
        '/inbox\n'
        '/reservas hoje\n'
        '/assumir 5573999999999\n'
        '/liberar 5573999999999\n'
        '/pendentes\n'
        '/confirmar pagamento 5573999999999'
    )


def _apply_bulk_rates(business_id: int, payload: str, period: str):
    pairs = [p.strip() for p in payload.split(',') if p.strip()]
    if not pairs:
        return 'Informe pelo menos uma tarifa. Ex.: /tarifas semana CASAL 320, FAMILIA 420'
    applied = []
    for pair in pairs:
        parts = pair.split()
        if len(parts) < 2:
            continue
        code = parts[0].upper()
        rate = float(parts[1].replace(',', '.'))
        info = set_manual_rate(business_id, code, rate, period='weekly' if period == 'semana' else 'daily')
        applied.append(f"{info['room_code']}: R$ {info['rate_value']:.2f}")
    if not applied:
        return 'Não consegui interpretar as tarifas enviadas.'
    return '✅ Tarifas aplicadas:\n' + '\n'.join(applied)


def processar_comando_negocio(texto: str, business: dict, admin_phone: str | None = None):
    lower = texto.lower().strip(); partes = texto.strip().split(); business_id = business['business_id']

    if lower in {'/quem sou', '/negocio quem sou'}:
        return (
            f"👤 Você está como usuário do negócio {business.get('business_name') or business.get('restaurant_nome')}.\n"
            f"Nome: {business.get('user_nome') or '-'}\n"
            f"Papel: {business.get('user_role') or '-'}\n"
            f"Tipo: {business.get('business_type') or '-'}"
        )

    if lower == '/config listar quartos':
        items = list_room_types(business_id)
        if not items:
            return 'Nenhum tipo de quarto configurado ainda.'
        linhas = ['🏨 Tipos de quarto cadastrados:']
        for item in items:
            linhas.append(f"{item['code']} • {item['name']} | qtd: {item.get('quantity_total') or 0} | camas: {item.get('bed_setup') or '-'} | cap: {item.get('capacity') or 0} | base: R$ {float(item.get('base_rate') or 0):.2f}")
        return '\n'.join(linhas)

    if lower.startswith('/config criar tipo '):
        payload = texto[len('/config criar tipo '):].strip(); partes_payload = [p.strip() for p in payload.split('|')]
        if len(partes_payload) < 6:
            return 'Uso: /config criar tipo CODIGO | Nome | quantidade | camas | capacidade | valor'
        code, name, quantity_raw, bed_setup, capacity_raw, base_rate_raw = partes_payload[:6]
        item = upsert_room_type(business_id, code=code.upper(), name=name, quantity_total=int(quantity_raw), bed_setup=bed_setup, capacity=int(capacity_raw), base_rate=float(str(base_rate_raw).replace(',', '.')))
        return f"✅ Tipo {item['code']} salvo com sucesso."

    if lower.startswith('/config quantidade '):
        code = partes[2]; quantity_total = int(partes[3]); item = upsert_room_type(business_id, code=code.upper(), quantity_total=quantity_total); return f"✅ Quantidade do tipo {item['code']} atualizada para {quantity_total}."
    if lower.startswith('/config camas '):
        code = partes[2]; bed_setup = texto.split(None, 3)[3]; item = upsert_room_type(business_id, code=code.upper(), bed_setup=bed_setup); return f"✅ Configuração de camas do tipo {item['code']} atualizada."
    if lower.startswith('/config capacidade '):
        code = partes[2]; capacity = int(partes[3]); item = upsert_room_type(business_id, code=code.upper(), capacity=capacity); return f"✅ Capacidade do tipo {item['code']} atualizada para {capacity}."
    if lower.startswith('/config valor '):
        code = partes[2]; base_rate = float(partes[3].replace(',', '.')); item = upsert_room_type(business_id, code=code.upper(), base_rate=base_rate); return f"✅ Valor base do tipo {item['code']} atualizado para R$ {base_rate:.2f}."
    if lower.startswith('/config excluir quarto ') or lower.startswith('/config remover quarto '):
        role = (business.get('user_role') or '').lower()
        if role not in {'admin', 'gerente', 'owner'}:
            return '⚠️ Apenas administradores do negócio podem excluir tipos de quarto.'
        code = partes[-1].upper()
        items = list_room_types(business_id)
        target = next((item for item in items if str(item.get('code','')).upper() == code), None)
        if not target:
            return 'Tipo de quarto não encontrado.'
        delete_room_type(business_id, int(target['id']))
        return f"✅ Tipo de quarto {code} removido com sucesso."
    if lower.startswith('/config pix '):
        pix_key = texto[len('/config pix '):].strip(); upsert_bot_settings(business_id, pix_key=pix_key); return '✅ Chave Pix atualizada com sucesso.'
    if lower.startswith('/config mensagem boasvindas '):
        welcome_message = texto[len('/config mensagem boasvindas '):].strip(); upsert_bot_settings(business_id, welcome_message=welcome_message); return '✅ Mensagem de boas-vindas atualizada.'
    if lower.startswith('/config modo '):
        mode = texto[len('/config modo '):].strip(); upsert_bot_settings(business_id, hospitality_mode=mode); return f'✅ Modo operacional ajustado para {mode}.'
    if lower.startswith('/config coleta '):
        if len(partes) < 4:
            return 'Uso: /config coleta daily 08:00'
        upsert_bot_settings(business_id, rate_collection_frequency=partes[2], rate_collection_time=partes[3]); return '✅ Rotina de coleta ajustada.'
    if lower == '/tarifas' or lower == '/tarifas status':
        return manual_rates_status_text(business_id)
    if lower.startswith('/tarifas hoje '):
        return _apply_bulk_rates(business_id, texto[len('/tarifas hoje '):].strip(), 'hoje')
    if lower.startswith('/tarifas semana '):
        return _apply_bulk_rates(business_id, texto[len('/tarifas semana '):].strip(), 'semana')
    if lower == '/solicitar tarifas':
        upsert_bot_settings(business_id, last_rate_prompt_at=None)
        return '✅ Solicitação de tarifas liberada. O sistema poderá perguntar novamente no próximo ciclo.'

    if lower.startswith('/reserva balcão '):
        payload = texto[len('/reserva balcão '):].strip(); parts = [p.strip() for p in payload.split(';')]
        if len(parts) < 6:
            return 'Uso: /reserva balcão Nome; 557399999999; CODIGO; 2026-03-20; 2026-03-22; 560; observação'
        guest_name, guest_phone, room_code, checkin, checkout, amount = parts[:6]
        notes = parts[6] if len(parts) > 6 else 'Reserva lançada manualmente via WhatsApp admin'
        item = criar_reserva_manual(business_id, guest_name=guest_name, guest_phone=guest_phone, checkin_date=checkin, checkout_date=checkout, guest_count=None, unit_category=room_code.upper(), quoted_amount=float(amount.replace(',', '.')), notes=notes, status='quoted', payment_status='aguardando_pagamento', source='admin_manual')
        return f"✅ Reserva lançada. ID {item['id']} | {guest_name} | {room_code.upper()} | R$ {float(item.get('quoted_amount') or 0):.2f}"

    if lower == '/inbox':
        resumo = summarize_hospitality_operations(business_id); linhas = ['📥 Inbox atual:']
        for item in resumo['recent_sessions'][:8]:
            linhas.append(f"{item['customer_phone']} | {item.get('customer_name') or '-'} | {item['status']} | {item.get('last_customer_message') or '-'}")
        if len(linhas) == 1:
            linhas.append('Nenhuma conversa recente.')
        return '\n'.join(linhas)

    if lower.startswith('/reservas hoje'):
        resumo = summarize_hospitality_operations(business_id); today = date.today().isoformat(); linhas = [f'🗓 Reservas com check-in em {today}:']; found = 0
        for item in resumo['recent_reservations']:
            if item.get('checkin_date') == today:
                found += 1; linhas.append(f"{item.get('guest_name') or item['guest_phone']} | {item.get('unit_category') or '-'} | {item['status']} | R$ {float(item.get('quoted_amount') or 0):.2f}")
        if not found:
            linhas.append('Nenhuma reserva com check-in hoje nas últimas movimentações.')
        return '\n'.join(linhas)

    if lower.startswith('/reservas amanha'):
        resumo = summarize_hospitality_operations(business_id); target = (date.today() + timedelta(days=1)).isoformat(); linhas = [f'🗓 Reservas com check-in em {target}:']; found = 0
        for item in resumo['recent_reservations']:
            if item.get('checkin_date') == target:
                found += 1; linhas.append(f"{item.get('guest_name') or item['guest_phone']} | {item.get('unit_category') or '-'} | {item['status']} | R$ {float(item.get('quoted_amount') or 0):.2f}")
        if not found:
            linhas.append('Nenhuma reserva com check-in amanhã nas últimas movimentações.')
        return '\n'.join(linhas)

    if lower.startswith('/assumir '):
        customer_phone = texto[len('/assumir '):].strip(); session = find_session_by_phone(customer_phone, business_id=business_id)
        if not session:
            return 'Conversa não encontrada para esse telefone.'
        update_chat_session_status(session['id'], 'human_active', assigned_to_phone=admin_phone, assigned_to_name=business.get('user_nome') or 'Equipe', handoff_reason='Assumido manualmente via WhatsApp')
        return f'✅ Conversa {customer_phone} assumida por humano.'
    if lower.startswith('/liberar '):
        customer_phone = texto[len('/liberar '):].strip(); session = find_session_by_phone(customer_phone, business_id=business_id)
        if not session:
            return 'Conversa não encontrada para esse telefone.'
        update_chat_session_status(session['id'], 'bot_active', assigned_to_phone=None, assigned_to_name=None, handoff_reason='Devolvido ao bot via WhatsApp')
        return f'✅ Conversa {customer_phone} devolvida ao bot.'

    if lower == '/pendentes' or lower == '/pagamentos pendentes':
        items = list_pending_payment_confirmations(business_id)
        if not items:
            return '✅ Nenhum pagamento aguardando confirmação no momento.'
        linhas = ['💳 Pagamentos aguardando confirmação:']
        for item in items[:10]:
            linhas.append(f"{item.get('guest_name') or item.get('guest_phone')} | {item.get('guest_phone')} | {item.get('unit_category') or '-'} | R$ {float(item.get('quoted_amount') or 0):.2f}")
        linhas.append('Use /confirmar pagamento TELEFONE para confirmar.')
        return '\n'.join(linhas)

    if lower.startswith('/confirmar pagamento '):
        customer_phone = texto[len('/confirmar pagamento '):].strip(); session = find_session_by_phone(customer_phone, business_id=business_id)
        if not session:
            return 'Conversa não encontrada para esse telefone.'
        pendentes = [item for item in list_pending_payment_confirmations(business_id) if item.get('guest_phone') == customer_phone]
        if not pendentes:
            return 'Nenhuma reserva pendente de confirmação encontrada para esse telefone.'
        item = pendentes[0]
        result = confirm_reservation_payment(item['id'], business_id=business_id, restaurant_id=business['restaurant_id'], actor_name=business.get('user_nome') or 'Equipe')
        update_chat_session_status(session['id'], 'human_active', assigned_to_phone=admin_phone, assigned_to_name=business.get('user_nome') or 'Equipe', handoff_reason='Pagamento confirmado via WhatsApp admin')
        return f"✅ Pagamento confirmado para {item.get('guest_name') or customer_phone}. Reserva {result['item']['id']} marcada como confirmada."

    return 'Não reconheci esse comando do negócio 🤖\n\n' + _room_types_help()


def processar_comando_admin(texto: str, admin_phone: str | None = None):
    linhas = [l.strip() for l in texto.splitlines() if l.strip()]
    if len(linhas) > 1:
        return '\n\n'.join(processar_comando_admin(linha, admin_phone=admin_phone) for linha in linhas)

    raw = texto.strip()
    lower = raw.lower()
    partes = raw.split()

    if lower in {'/quem sou', '/plataforma quem sou'}:
        return _platform_identity(admin_phone)

    if lower in {'/ajuda', '/plataforma ajuda', '/admin ajuda'}:
        return _admin_help()

    if lower in {'/plataforma listar admins', '/admin listar admins'}:
        items = listar_admins_plataforma()
        if not items:
            return 'Nenhum administrador de plataforma cadastrado.'
        lines = ['🛡️ Administradores da plataforma:']
        for item in items:
            status = 'ativo' if item.get('ativo') else 'inativo'
            lines.append(f"#{item['id']} • {item.get('nome') or 'Administrador'} • {item.get('telefone') or '-'} • {status}")
        return '\n'.join(lines)

    if lower.startswith('/plataforma criar negocio ') or lower.startswith('/admin cadastrar restaurante '):
        if lower.startswith('/plataforma criar negocio '):
            payload = raw[len('/plataforma criar negocio '):].strip()
            parts = [p.strip() for p in payload.split('|') if p.strip()]
            nome = parts[0] if parts else ''
            business_type = parts[1].lower() if len(parts) > 1 else 'hospitality'
        else:
            nome = raw[len('/admin cadastrar restaurante '):].strip()
            business_type = 'restaurant'
        if not nome:
            return 'Envie no formato: /plataforma criar negocio Nome do negócio | hospitality'
        if business_type not in BUSINESS_TYPES:
            return f'Tipo inválido. Use um destes: {", ".join(sorted(BUSINESS_TYPES))}'
        restaurant_id = cadastrar_restaurante(nome)
        _set_business_type(restaurant_id, business_type)
        return f'✅ Negócio criado com sucesso.\nID: {restaurant_id}\nNome: {nome}\nTipo: {business_type}\n\nPróximo passo: /plataforma adicionar usuario {restaurant_id} | Nome | 557399999999 | admin'

    if lower in {'/plataforma listar negocios', '/admin listar restaurantes'}:
        items = listar_restaurantes()
        if not items:
            return 'Ainda não há negócios cadastrados.'
        lines = ['🏢 Negócios cadastrados:']
        for item in items:
            lines.append(_format_business_line(item))
        lines.append('\nUse /plataforma negocio ID para ver detalhes.')
        return '\n'.join(lines)

    if lower.startswith('/plataforma negocio '):
        try:
            restaurant_id = int(partes[2])
        except Exception:
            return 'Uso: /plataforma negocio ID'
        item = obter_restaurante(restaurant_id)
        if not item:
            return 'Negócio não encontrado.'
        users = listar_usuarios_restaurante(restaurant_id)
        return (
            f"🏢 {item['nome']}\n"
            f"ID: {item['id']}\n"
            f"Tipo: {item.get('business_type') or 'restaurant'}\n"
            f"Status: {item.get('status') or '-'}\n"
            f"Slug: {item.get('slug') or '-'}\n"
            f"Usuários ativos: {sum(1 for u in users if u.get('ativo'))}"
        )

    if lower.startswith('/plataforma definir tipo ') or lower.startswith('/admin definir tipo '):
        if '|' in raw:
            payload = raw.split(' ', 3)[3]
            parts2 = [p.strip() for p in payload.split('|') if p.strip()]
            if len(parts2) < 2:
                return 'Uso: /plataforma definir tipo ID | hospitality'
            restaurant_id = int(parts2[0]); business_type = parts2[1].lower()
        else:
            if len(partes) < 4:
                return 'Uso: /plataforma definir tipo ID | hospitality'
            restaurant_id = int(partes[-2]); business_type = partes[-1].strip().lower()
        if business_type not in BUSINESS_TYPES:
            return f'Tipo inválido. Use: {", ".join(sorted(BUSINESS_TYPES))}'
        _set_business_type(restaurant_id, business_type)
        return f'✅ Tipo do negócio {restaurant_id} atualizado para {business_type}.'

    if lower.startswith('/plataforma listar usuarios ') or lower.startswith('/plataforma usuarios '):
        target = partes[3] if lower.startswith('/plataforma listar usuarios ') else partes[2]
        restaurant_id = int(target)
        users = listar_usuarios_restaurante(restaurant_id)
        if not users:
            return 'Nenhum usuário encontrado para esse negócio.'
        lines = [f'👥 Usuários do negócio {restaurant_id}:']
        for user in users:
            status = 'ativo' if user.get('ativo') else 'inativo'
            lines.append(f"#{user['id']} • {user.get('nome') or '-'} • {user.get('telefone') or '-'} • {user.get('role') or '-'} • {status}")
        return '\n'.join(lines)

    if lower.startswith('/plataforma adicionar usuario ') or lower.startswith('/admin adicionar usuario '):
        if lower.startswith('/plataforma adicionar usuario '):
            payload = raw[len('/plataforma adicionar usuario '):].strip()
            parts2 = [p.strip() for p in payload.split('|')]
            if len(parts2) < 4:
                return 'Uso: /plataforma adicionar usuario ID | Nome | 557399999999 | admin'
            restaurant_id = int(parts2[0]); nome = parts2[1]; telefone = parts2[2]; role = parts2[3]
        else:
            if len(partes) < 7:
                return 'Uso: /admin adicionar usuario ID TELEFONE NOME ROLE'
            restaurant_id = int(partes[3]); telefone = partes[4]; nome = partes[5]; role = partes[6]
        try:
            adicionar_usuario_restaurante(restaurant_id, telefone, nome, role)
        except ValueError as exc:
            return str(exc)
        return f'✅ Usuário adicionado com sucesso.\nNegócio: {restaurant_id}\nNome: {nome}\nTelefone: {telefone}\nPapel: {role}'

    if lower.startswith('/plataforma remover usuario '):
        payload = raw[len('/plataforma remover usuario '):].strip()
        parts2 = [p.strip() for p in payload.split('|')]
        if len(parts2) < 2:
            return 'Uso: /plataforma remover usuario ID | 557399999999'
        restaurant_id = int(parts2[0]); telefone = parts2[1]
        removed = remover_usuario_restaurante(restaurant_id, telefone)
        if not removed:
            return 'Não encontrei esse usuário nesse negócio.'
        return f"✅ Usuário removido.\nNome: {removed.get('nome') or '-'}\nTelefone: {removed.get('telefone') or '-'}"

    if lower.startswith('/plataforma criar login web ') or lower.startswith('/admin criar login web '):
        if lower.startswith('/plataforma criar login web '):
            payload = raw[len('/plataforma criar login web '):].strip()
            parts2 = [p.strip() for p in payload.split('|')]
            if len(parts2) < 3:
                return 'Uso: /plataforma criar login web ID | email@dominio.com | Nome do Admin'
            restaurant_id = int(parts2[0]); email = parts2[1]; nome = parts2[2]
        else:
            if len(partes) < 7:
                return 'Uso: /admin criar login web ID email nome'
            restaurant_id = int(partes[4]); email = partes[5]; nome = ' '.join(partes[6:])
        result = criar_login_web_restaurante(restaurant_id, email, nome)
        return f"✅ Login web criado.\nEmail: {result['email']}\nSenha temporária: {result['temporary_password']}"

    if lower.startswith('/admin ativar restaurante '):
        ativar_restaurante(int(partes[3])); return '✅ Negócio ativado com sucesso.'
    if lower.startswith('/admin desativar restaurante '):
        desativar_restaurante(int(partes[3])); return '✅ Negócio desativado com sucesso.'
    if lower.startswith('/admin resetar transacoes '):
        resetar_transacoes_restaurante(int(partes[3])); return '✅ Transações resetadas.'

    return 'Não reconheci esse comando de plataforma 😊\n\n' + _admin_help()
