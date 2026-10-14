# Roda os testes do trabalho e grava tudo em resultados/<data>/.
#
#   sudo python3 experimentar.py      1 repeticao  (6 execucoes)
#   sudo python3 experimentar.py 3    3 repeticoes (18 execucoes)

import csv
import os
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from statistics import mean

from topo import criar_rede
from falha import (injetar_perda, pacotes_recebidos, perda_continua,
                   rotas_dos_roteadores, desvio_por_r3)
from agente import (rodar_agente, ler_resultado, detalhes_tokens,
                    verificar_parada, encerrar_processo)
from visualizacao import Visualizacao

PASTA = Path(__file__).parent

# (nome do teste, perda em % no enlace r1-r2)
TESTES = [("T01", 30), ("T02", 80), ("T03", 0)]


def rodar_script(pasta_teste, usuario, visualizacao, parada=None):
    arquivo_acoes = pasta_teste / "acoes.txt"
    comando = ["timeout", "300", "sudo", "-u", usuario, "python3", "-u", str(PASTA / "comparar.py")]
    with arquivo_acoes.open("w") as saida:
        processo = subprocess.Popen(comando, stdout=saida, stderr=subprocess.STDOUT,
                                    stdin=subprocess.DEVNULL, start_new_session=True)
        try:
            with arquivo_acoes.open(errors="replace") as leitura:
                while processo.poll() is None:
                    verificar_parada(parada)
                    linha = leitura.readline()
                    if not linha:
                        time.sleep(0.1)
                        continue
                    if linha.strip() == "ROTA_ALTERADA=ida":
                        visualizacao.rota_alterada("ida")
                    elif linha.strip() == "ROTA_ALTERADA=volta":
                        visualizacao.rota_alterada("volta")
                for linha in leitura:
                    if linha.strip() == "ROTA_ALTERADA=ida":
                        visualizacao.rota_alterada("ida")
                    elif linha.strip() == "ROTA_ALTERADA=volta":
                        visualizacao.rota_alterada("volta")
            codigo_saida = processo.wait()
        finally:
            encerrar_processo(processo)
    arquivo = pasta_teste / "acoes.txt"
    texto = arquivo.read_text()
    comandos = texto.count("$ rede")
    arquivo.write_text("\n".join(
        linha for linha in texto.splitlines() if not linha.startswith("ROTA_ALTERADA=")
    ) + "\n")
    return comandos, "", codigo_saida  # o script nao usa tokens


def um_teste(nome, perda, executor, pasta_teste, usuario, visualizacao, parada=None):
    visualizacao.atualizar("Criando topologia Mininet")
    rede = criar_rede()
    try:
        verificar_parada(parada)
        visualizacao.atualizar("Testando conectividade inicial")
        if pacotes_recebidos(rede, 10) != 10:
            sys.exit("A rede iniciou com perda de pacotes antes da injecao da falha.")
        verificar_parada(parada)
        rotas_antes = rotas_dos_roteadores(rede)
        visualizacao.atualizar("Injetando falha no enlace r1-r2" if perda else "Confirmando teste sem falha")
        injetar_perda(rede, perda)

        inicio = time.time()
        if executor == "agente":
            visualizacao.atualizar("Agente inspecionando e tentando corrigir")
            def mostrar_evento(tipo, texto, resultado, sucesso):
                if tipo == "modelo":
                    visualizacao.mostrar_mensagem_modelo(texto)
                else:
                    visualizacao.mostrar_ferramenta(texto, resultado, sucesso)

            codigo_saida = rodar_agente(
                pasta_teste, usuario,
                ao_alterar_rota=visualizacao.rota_alterada,
                ao_evento=mostrar_evento,
                ao_tokens=visualizacao.atualizar_tokens,
                parada=parada,
            )
            comandos, tokens = ler_resultado(pasta_teste)
            if isinstance(tokens, int):
                visualizacao.atualizar_tokens(tokens)
            uso = detalhes_tokens(pasta_teste / "tokens.json")
            if uso:
                visualizacao.mostrar_uso_tokens(uso)
        else:
            visualizacao.atualizar("Script comparativo executando")
            comandos, tokens, codigo_saida = rodar_script(pasta_teste, usuario, visualizacao, parada)
            uso = None
        ttr = round(time.time() - inicio, 1)

        verificar_parada(parada)
        # Conferencia feita pelo experimento, depois que o executor terminou
        visualizacao.atualizar("Verificando ping, falha e rotas")
        recebidos = pacotes_recebidos(rede, 30)
        verificar_parada(parada)
        falha_mantida = perda_continua(rede, perda)
        rotas_depois = rotas_dos_roteadores(rede)
        mudou_rotas = rotas_depois != rotas_antes
        desvio_correto = perda == 0 or desvio_por_r3(rotas_depois)
        verificacao = (
            f"Ping: {recebidos}/30\nFalha mantida: {falha_mantida}\n"
            f"Desvio por r3: {desvio_correto}\nRotas alteradas: {mudou_rotas}\n"
            f"Codigo de saida: {codigo_saida}\n\n"
        )
        for roteador, tabela in rotas_depois.items():
            verificacao += f"{roteador}:\n{tabela}\n"
        (pasta_teste / "verificacao.txt").write_text(verificacao)
        visualizacao.confirmar_rotas(
            "10.0.2.0/24 via 10.0.13.3" in rotas_depois["r1"],
            "10.0.1.0/24 via 10.0.23.3" in rotas_depois["r2"],
        )
        visualizacao.atualizar("Verificacao independente concluida")
    finally:
        visualizacao.atualizar("Encerrando topologia Mininet")
        rede.stop()

    sucesso = recebidos == 30 and falha_mantida and desvio_correto
    if perda == 0:
        sucesso = sucesso and not mudou_rotas  # sem falha, o certo e nao mexer em nada

    return {"teste": nome, "perda": perda, "executor": executor, "sucesso": sucesso,
            "ttr_segundos": ttr, "comandos": comandos, "tokens": tokens,
            "pings_recebidos": recebidos, "rotas_alteradas": mudou_rotas,
            "desvio_por_r3": desvio_correto, "codigo_saida": codigo_saida,
            "tokens_entrada": uso["entrada"] if uso else "",
            "tokens_saida": uso["saida"] if uso else "",
            "tokens_cache_lido": uso["cache"] if uso else "",
            "chamadas_modelo": uso["chamadas"] if uso else ""}


def salvar_csv(pasta, linhas):
    with open(pasta / "resultados.csv", "w", newline="") as arquivo:
        tabela = csv.DictWriter(arquivo, fieldnames=linhas[0].keys())
        tabela.writeheader()
        tabela.writerows(linhas)


def resumo(linhas):
    texto = "teste  executor  sucessos  TTR medio(s)  comandos medios  tokens medios\n"
    for nome, perda in TESTES:
        for executor in ["agente", "script"]:
            grupo = [linha for linha in linhas if linha["teste"] == nome and linha["executor"] == executor]
            if not grupo:
                continue
            sucessos = [linha for linha in grupo if linha["sucesso"]]
            ttr = round(mean(linha["ttr_segundos"] for linha in sucessos), 1) if sucessos else "-"
            comandos = round(mean(linha["comandos"] for linha in grupo), 1)
            tokens = [linha["tokens"] for linha in grupo if linha["tokens"] != ""]
            tokens = round(mean(tokens)) if tokens else "-"
            texto += f"{nome}    {executor:8}  {len(sucessos)}/{len(grupo)}       {ttr:<12}  {comandos:<15}  {tokens}\n"
    return texto


def acompanhar_parada(parada):
    for linha in sys.stdin:
        if linha.strip() == "parar":
            parada.set()
            return


def main():
    usuario = os.environ.get("SUDO_USER")
    if os.geteuid() != 0 or not usuario:
        sys.exit("Execucao requer privilegios de root e SUDO_USER definido.")
    comando_rede = Path("/usr/local/bin/rede")
    if not comando_rede.exists():
        sys.exit("Comando 'rede' nao instalado em /usr/local/bin/rede.")
    if comando_rede.read_bytes() != (PASTA / "rede.py").read_bytes():
        sys.exit("A versao instalada de 'rede' difere do arquivo rede.py do projeto.")
    repeticoes = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    executores = ["script"] if "--so-script" in sys.argv[2:] else ["agente", "script"]

    pasta = PASTA / "resultados" / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    pasta.mkdir(parents=True)
    subprocess.run(["mn", "-c"], capture_output=True)  # limpa restos de execucoes anteriores

    classe_visualizacao = Visualizacao
    if "--web" in sys.argv[2:]:
        from painel import VisualizacaoWeb
        classe_visualizacao = VisualizacaoWeb
    visualizacao = classe_visualizacao(len(TESTES) * len(executores) * repeticoes)
    visualizacao.iniciar()
    linhas = []
    parada = threading.Event()
    try:
        if "--web" in sys.argv[2:]:
            threading.Thread(target=acompanhar_parada, args=(parada,), daemon=True).start()
        for repeticao in range(1, repeticoes + 1):
            for nome, perda in TESTES:
                for executor in executores:
                    verificar_parada(parada)
                    visualizacao.iniciar_teste(nome, perda, executor, repeticao)
                    pasta_teste = pasta / f"{nome}_{executor}_{repeticao}"
                    pasta_teste.mkdir()
                    shutil.chown(pasta_teste, usuario)  # o agente precisa gravar aqui

                    resultado = um_teste(nome, perda, executor, pasta_teste, usuario, visualizacao, parada)
                    resultado["repeticao"] = repeticao
                    linhas.append(resultado)
                    salvar_csv(pasta, linhas)  # salva a cada teste para nao perder nada
                    visualizacao.registrar(resultado)

        verificar_parada(parada)
        (pasta / "resumo.txt").write_text(resumo(linhas))
        subprocess.run(["chown", "-R", usuario, str(PASTA / "resultados")])
        visualizacao.finalizar(pasta)
    except KeyboardInterrupt:
        (pasta / "resumo.txt").write_text(resumo(linhas) if linhas else "Rodada interrompida sem testes concluidos.\n")
        subprocess.run(["chown", "-R", usuario, str(PASTA / "resultados")])
        visualizacao.finalizar(pasta, interrompido=True)
        sys.exit(130)
    except BaseException:
        visualizacao.parar()
        raise
    print()
    print((pasta / "resumo.txt").read_text())
    print("Resultados em", pasta)


if __name__ == "__main__":
    main()
