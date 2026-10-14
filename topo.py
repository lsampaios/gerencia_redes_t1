# Rede do trabalho: dois computadores (h1 e h2) e tres roteadores.
#
#   h1 --- r1 ------- r2 --- h2     caminho principal
#            \       /
#               r3                  caminho alternativo
#
# Para abrir a rede e testar comandos na mao:  sudo python3 topo.py

from mininet.net import Mininet
from mininet.cli import CLI

# (no, outro no, IP do primeiro, IP do segundo)
ENLACES = [
    ("h1", "r1", "10.0.1.1/24", "10.0.1.254/24"),
    ("h2", "r2", "10.0.2.1/24", "10.0.2.254/24"),
    ("r1", "r2", "10.0.12.1/24", "10.0.12.2/24"),
    ("r1", "r3", "10.0.13.1/24", "10.0.13.3/24"),
    ("r3", "r2", "10.0.23.3/24", "10.0.23.2/24"),
]

# Rotas iniciais: o trafego entre h1 e h2 passa pelo enlace r1-r2.
ROTAS = {
    "h1": ["default via 10.0.1.254"],
    "h2": ["default via 10.0.2.254"],
    "r1": ["10.0.2.0/24 via 10.0.12.2"],
    "r2": ["10.0.1.0/24 via 10.0.12.1"],
    "r3": ["10.0.1.0/24 via 10.0.13.1", "10.0.2.0/24 via 10.0.23.2"],
}


def criar_rede():
    rede = Mininet(controller=None)  # sem switches: so computadores e roteadores Linux

    for nome in ROTAS:
        rede.addHost(nome, ip=None)

    for a, b, ip_a, ip_b in ENLACES:
        # A interface "r1-r2" e a placa de r1 que esta ligada em r2.
        rede.addLink(a, b, intfName1=f"{a}-{b}", intfName2=f"{b}-{a}",
                     params1={"ip": ip_a}, params2={"ip": ip_b})

    rede.start()

    for nome in ["r1", "r2", "r3"]:
        rede.get(nome).cmd("sysctl -w net.ipv4.ip_forward=1")  # vira roteador

    for nome, rotas in ROTAS.items():
        for rota in rotas:
            rede.get(nome).cmd(f"ip route add {rota}")

    return rede


if __name__ == "__main__":
    rede = criar_rede()
    CLI(rede)
    rede.stop()
