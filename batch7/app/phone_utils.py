import re


def limpar_telefone(telefone: str) -> str:
    """
    Remove tudo que não for número.
    Ex:
    '+55 (73) 98889-8124' -> '5573988898124'
    """
    return re.sub(r"\D", "", telefone or "")


def normalizar_telefone_br(telefone: str) -> str:
    """
    Normaliza o telefone para um formato numérico limpo.

    Regras:
    - remove caracteres não numéricos
    - mantém com DDI 55 se existir
    - se vier sem 55, mantém sem 55
    """
    telefone = limpar_telefone(telefone)

    # remove zeros à esquerda estranhos
    telefone = telefone.lstrip("0")

    return telefone


def gerar_variantes_telefone_br(telefone: str) -> list[str]:
    """
    Gera variantes equivalentes para comparação no Brasil.

    Exemplos equivalentes:
    5573988898124
    557388898124
    73988898124
    7388898124

    Ideia:
    - aceitar com e sem 55
    - aceitar com e sem o 9 após DDD
    """
    telefone = normalizar_telefone_br(telefone)
    variantes = set()

    if not telefone:
        return []

    variantes.add(telefone)

    # versão sem 55
    sem_55 = telefone[2:] if telefone.startswith("55") else telefone
    variantes.add(sem_55)

    # versão com 55
    com_55 = telefone if telefone.startswith("55") else f"55{telefone}"
    variantes.add(com_55)

    # Função interna para adicionar/remover o 9 após DDD
    def alternar_nono_digito(numero: str):
        # Formato esperado sem 55:
        # DDD(2) + número(8 ou 9 dígitos)
        if len(numero) == 10:
            # ex: 73 + 88898124  -> adiciona 9 => 73 + 9 + 88898124
            ddd = numero[:2]
            restante = numero[2:]
            return {numero, f"{ddd}9{restante}"}

        if len(numero) == 11:
            # ex: 73 + 988898124 -> remove 9 => 73 + 88898124
            ddd = numero[:2]
            restante = numero[2:]
            if restante.startswith("9"):
                return {numero, f"{ddd}{restante[1:]}"}
            return {numero}

        return {numero}

    base_sem_55 = set()
    for v in list(variantes):
        if v.startswith("55"):
            base_sem_55.add(v[2:])
        else:
            base_sem_55.add(v)

    expandidas_sem_55 = set()
    for numero in base_sem_55:
        expandidas_sem_55.update(alternar_nono_digito(numero))

    for numero in expandidas_sem_55:
        variantes.add(numero)
        variantes.add(f"55{numero}")

    return sorted(variantes)


def telefone_equivalente(telefone_a: str, telefone_b: str) -> bool:
    """
    Verifica se dois telefones podem ser considerados equivalentes
    pelo padrão brasileiro.
    """
    variantes_a = set(gerar_variantes_telefone_br(telefone_a))
    variantes_b = set(gerar_variantes_telefone_br(telefone_b))
    return bool(variantes_a & variantes_b)