# Funcoes que o experimento usa para criar a falha e conferir o resultado.
# Elas falam direto com o Mininet e nao passam pelo agente.

import re


def injetar_perda(rede, perda):
    """Coloca perda de pacotes (em %) nos dois sentidos do enlace r1-r2."""
    if perda == 0:
        return
    for no, interface in (("r1", "r1-r2"), ("r2", "r2-r1")):
        _, erro, codigo = rede.get(no).pexec(
            "tc", "qdisc", "add", "dev", interface, "root", "netem", "loss", f"{perda}%"
        )
        if codigo:
            raise RuntimeError(f"Nao foi possivel configurar perda em {no}:{interface}: {erro}")


def pacotes_recebidos(rede, quantidade):
    """Envia pings de h1 para h2 e devolve quantos voltaram."""
    saida = rede.get("h1").cmd(f"LC_ALL=C ping -c {quantidade} -i 0.2 -W 1 10.0.2.1")
    achou = re.search(r"(\d+) received", saida)
    if achou:
        return int(achou.group(1))
    return 0


def perda_continua(rede, perda):
    """Confere se a perda ainda esta no enlace (o executor nao pode remove-la)."""
    if perda == 0:
        return True
    r1 = rede.get("r1").cmd("LC_ALL=C tc qdisc show dev r1-r2")
    r2 = rede.get("r2").cmd("LC_ALL=C tc qdisc show dev r2-r1")
    return f"loss {perda}%" in r1 and f"loss {perda}%" in r2


def rotas_dos_roteadores(rede):
    """Tabela de rotas de cada roteador, para saber se alguem mudou algo."""
    rotas = {}
    for nome in ["r1", "r2", "r3"]:
        saida, erro, codigo = rede.get(nome).pexec("ip", "-4", "route", "show")
        if codigo:
            raise RuntimeError(f"Nao foi possivel ler rotas de {nome}: {erro}")
        rotas[nome] = saida
    return rotas


def desvio_por_r3(rotas):
    """Confere o caminho de ida e o de volta pelo roteador r3."""
    ida = rotas["r1"]
    volta = rotas["r2"]
    return ("10.0.2.0/24 via 10.0.13.3" in ida and
            "10.0.1.0/24 via 10.0.23.3" in volta)
