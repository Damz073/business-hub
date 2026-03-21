from __future__ import annotations

MODULE_MANIFEST = {
    "hospitality": {
        "label": "Hospedagem",
        "description": "Reservas, quartos, tarifas, ocupação e atendimento híbrido.",
        "core_features": ["inbox", "crm", "finance", "payments"],
        "module_features": ["reservations", "rooms", "rates", "occupancy", "pms_sync"],
        "icon": "🏨",
        "color": "#f59e0b",
    },
    "restaurant": {
        "label": "Restaurante",
        "description": "Pedidos, cardápio, balcão, delivery e operação por WhatsApp.",
        "core_features": ["inbox", "crm", "finance", "payments"],
        "module_features": ["menu", "orders", "counter_sales", "delivery"],
        "icon": "🍽️",
        "color": "#ef4444",
    },
    "beauty": {
        "label": "Beleza",
        "description": "Agenda, serviços, profissionais e confirmação automática.",
        "core_features": ["inbox", "crm", "finance", "payments"],
        "module_features": ["appointments", "services", "professionals", "reminders"],
        "icon": "💇",
        "color": "#ec4899",
    },
    "rental": {
        "label": "Locadora",
        "description": "Frota, reservas, retirada/devolução e acompanhamento financeiro.",
        "core_features": ["inbox", "crm", "finance", "payments"],
        "module_features": ["fleet", "rentals", "returns", "deposits"],
        "icon": "🚗",
        "color": "#10b981",
    },
}


def normalize_business_type(value: str | None) -> str:
    key = (value or 'restaurant').strip().lower()
    return key if key in MODULE_MANIFEST else 'restaurant'


def get_module_manifest(value: str | None):
    key = normalize_business_type(value)
    item = dict(MODULE_MANIFEST[key])
    item['key'] = key
    return item


def list_module_manifests():
    return [get_module_manifest(key) for key in MODULE_MANIFEST.keys()]
