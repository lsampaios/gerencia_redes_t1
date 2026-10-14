#!/usr/bin/python3 -I
# Comando "rede": a unica ferramenta que o agente pode usar.
# Ele roda um comando dentro de um no do Mininet, mas so se o comando
# estiver na lista de permitidos. Assim o agente nao pode, por exemplo,
# apagar a falha, desligar interfaces ou mexer nos computadores.
#
# Exemplos:
#   rede h1 ping -c 10 10.0.2.1
#   rede r1 ip route
#   rede r1 ip route replace 10.0.2.0/24 via 10.0.13.3

import ipaddress
import os
import subprocess
import sys

NOS = ["h1", "h2", "r1", "r2", "r3"]

AJUDA = """Comandos permitidos:
  rede <no> ping -c <N> <IP>                   (N de 1 a 50)
  rede <no> traceroute -n <IP>
  rede <no> ip addr
  rede <no> ip route
  rede <no> tc qdisc show
    rede <r1|r2> ip route replace <rede> via <IP>
Nos: h1 h2 r1 r2 r3"""


def eh_ip(texto):
    try:
        ipaddress.ip_address(texto)
        return True
    except ValueError:
        return False


def comando_permitido(no, comando):
    # Comandos que so consultam a rede
    if comando in [["ip", "addr"], ["ip", "route"], ["tc", "qdisc", "show"]]:
        return True

    if len(comando) == 4 and comando[:2] == ["ping", "-c"]:
        quantidade = comando[2]
        return quantidade.isdigit() and 1 <= int(quantidade) <= 50 and eh_ip(comando[3])

    if len(comando) == 3 and comando[:2] == ["traceroute", "-n"]:
        return eh_ip(comando[2])

    # Unico comando que altera a rede: trocar uma rota, so nos roteadores
    if len(comando) == 6 and comando[:3] == ["ip", "route", "replace"] and comando[4] == "via":
        if no == "r1":
            return comando[3] == "10.0.2.0/24" and comando[5] in ("10.0.12.2", "10.0.13.3")
        if no == "r2":
            return comando[3] == "10.0.1.0/24" and comando[5] in ("10.0.12.1", "10.0.23.3")

    return False


def processo_do_no(no):
    # Cada no do Mininet e um processo "bash ... mininet:<no>".
    busca = subprocess.run(["pgrep", "-f", f"mininet:{no}$"], capture_output=True, text=True)
    numeros = busca.stdout.split()
    if not numeros:
        sys.exit(f"No {no} nao esta ativo no Mininet.")
    return numeros[0]


def main():
    if os.geteuid() != 0:
        # Mexer na rede exige root. O sudo esta liberado so para este comando.
        os.execv("/usr/bin/sudo", ["sudo", "-n", "/usr/local/bin/rede", *sys.argv[1:]])

    if len(sys.argv) < 3 or sys.argv[1] not in NOS:
        sys.exit(AJUDA)

    no = sys.argv[1]
    comando = sys.argv[2:]
    if not comando_permitido(no, comando):
        sys.exit("NEGADO: comando nao permitido.\n" + AJUDA)

    # nsenter entra na rede do no e executa o comando la dentro
    resultado = subprocess.run(
        ["nsenter", "-t", processo_do_no(no), "-n", *comando],
        env={**os.environ, "LC_ALL": "C"},
    )
    sys.exit(resultado.returncode)


if __name__ == "__main__":
    main()
