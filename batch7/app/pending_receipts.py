pendentes = {}


def salvar_comprovante_pendente(telefone: str, dados: dict):
    pendentes[telefone] = dados


def obter_comprovante_pendente(telefone: str):
    return pendentes.get(telefone)


def remover_comprovante_pendente(telefone: str):
    if telefone in pendentes:
        del pendentes[telefone]