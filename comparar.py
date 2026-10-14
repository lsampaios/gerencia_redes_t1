# Script fixo, sem IA, usado para comparar com o agente.
# Regra: se h1 perde pacotes ate h2, desvia o trafego do enlace r1-r2 para r3.

import re
import subprocess


def rede(*comando):
    print("$ rede", " ".join(comando), flush=True)
    resultado = subprocess.run(["rede", *comando], capture_output=True, text=True)
    print(resultado.stdout, flush=True)
    if resultado.returncode == 0 and comando[:4] == ("r1", "ip", "route", "replace"):
        print("ROTA_ALTERADA=ida", flush=True)
    elif resultado.returncode == 0 and comando[:4] == ("r2", "ip", "route", "replace"):
        print("ROTA_ALTERADA=volta", flush=True)
    return resultado.stdout


def perda_ate_h2():
    saida = rede("h1", "ping", "-c", "10", "10.0.2.1")
    achou = re.search(r"([\d.]+)% packet loss", saida)
    if achou:
        return float(achou.group(1))
    return 100.0


perda = perda_ate_h2()

if perda == 0:
    print("Sem perda. Nada foi alterado.")
else:
    rede("r1", "ip", "route", "replace", "10.0.2.0/24", "via", "10.0.13.3")  # ida por r3
    rede("r2", "ip", "route", "replace", "10.0.1.0/24", "via", "10.0.23.3")  # volta por r3
    print(f"Perda depois do desvio: {perda_ate_h2()}%")
