from app.core_services import get_business_profile


def get_rental_summary(business_id: int):
    profile = get_business_profile(business_id)
    return {
        'module': 'rental',
        'label': 'Locadora',
        'status': 'foundation',
        'profile': profile,
        'next_capabilities': [
            'Inbox universal',
            'CRM universal',
            'Financeiro transversal',
            'Motor de conversa por vertical',
        ],
    }
