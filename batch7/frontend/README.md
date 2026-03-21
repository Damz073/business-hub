# Finance Bot Dashboard Frontend

## Requisitos
- Node.js 20+
- Backend rodando em `http://127.0.0.1:8000`

## Instalação
```bash
npm install
cp .env.local.example .env.local
npm run dev
```

Abra `http://localhost:3000`.

## Login
Use o login web criado pelo comando admin no WhatsApp:

```text
/admin criar login <restaurant_id> <email> | <nome>
```

## API esperada
Por padrão o frontend consome:

```text
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```
