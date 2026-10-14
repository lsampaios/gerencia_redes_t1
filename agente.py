# Roda o agente (GitHub Copilot CLI) e le o que ele fez.

import json
import os
import shlex
import signal
import subprocess
import time
from pathlib import Path

# As regras locais desta pasta sao enviadas junto com o pedido ao Copilot.
PASTA_COPILOT = Path(__file__).parent / "copilot"
MODELO = "gpt-6-luna"
LIMITE_SEGUNDOS = 900


def verificar_parada(parada):
    if parada is not None and parada.is_set():
        raise KeyboardInterrupt()


def encerrar_processo(processo):
    if processo.poll() is not None:
        return
    try:
        os.killpg(processo.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        processo.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(processo.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        processo.wait()


def _sentido_da_rota(comando):
    try:
        partes = shlex.split(comando)
    except ValueError:
        return None
    rotas = {
        ("r1", "10.0.2.0/24", "10.0.13.3"): "ida",
        ("r2", "10.0.1.0/24", "10.0.23.3"): "volta",
    }
    if (len(partes) == 8 and partes[0] == "rede" and partes[1] in ("r1", "r2")
            and partes[2:5] == ["ip", "route", "replace"] and partes[6] == "via"):
        return rotas.get((partes[1], partes[5], partes[7]))
    return None


def detalhes_tokens(arquivo_tokens):
    try:
        uso = json.loads(arquivo_tokens.read_text())
        totais = {"entrada": 0, "saida": 0, "cache": 0, "chamadas": 0}
        encontrou = False
        for modelo in uso.get("modelMetrics", {}).values():
            dados = modelo.get("usage", {})
            entrada, saida = dados.get("inputTokens"), dados.get("outputTokens")
            if isinstance(entrada, int) and isinstance(saida, int):
                encontrou = True
                totais["entrada"] += entrada
                totais["saida"] += saida
                totais["cache"] += dados.get("cacheReadTokens", 0)
                totais["chamadas"] += modelo.get("requests", {}).get("count", 0)
        return totais if encontrou else None
    except (OSError, ValueError, AttributeError):
        return None


def _ler_tokens(arquivo_tokens):
    detalhes = detalhes_tokens(arquivo_tokens)
    return detalhes["entrada"] + detalhes["saida"] if detalhes else None


def _acompanhar_rotas(arquivo_log, processo, ao_alterar_rota,
                      ao_evento=None, arquivo_tokens=None, ao_tokens=None, parada=None):
    pendentes = {}
    parcial = ""
    ultimo_token = None
    with arquivo_log.open(errors="replace") as log:
        while processo.poll() is None:
            verificar_parada(parada)
            bloco = log.read()
            if bloco:
                parcial += bloco
                linhas = parcial.split("\n")
                parcial = linhas.pop()
                for linha in linhas:
                    _processar_evento_rota(linha, pendentes, ao_alterar_rota, ao_evento)
            else:
                time.sleep(0.2)
            if arquivo_tokens and ao_tokens:
                tokens = _ler_tokens(arquivo_tokens)
                if tokens is not None and tokens != ultimo_token:
                    ao_tokens(tokens)
                    ultimo_token = tokens

        parcial += log.read()
    for linha in parcial.split("\n"):
        _processar_evento_rota(linha, pendentes, ao_alterar_rota, ao_evento)
    if arquivo_tokens and ao_tokens:
        tokens = _ler_tokens(arquivo_tokens)
        if tokens is not None and tokens != ultimo_token:
            ao_tokens(tokens)


def _processar_evento_rota(linha, pendentes, ao_alterar_rota, ao_evento=None):
    try:
        evento = json.loads(linha)
    except (TypeError, ValueError):
        return

    dados = evento.get("data", {})
    tipo = evento.get("type")
    if tipo == "tool.execution_start":
        argumentos = dados.get("arguments") or {}
        comando = argumentos.get("command", "") if isinstance(argumentos, dict) else ""
        pendentes[dados.get("toolCallId")] = {
            "sentido": _sentido_da_rota(comando),
            "comando": comando,
        }
        if ao_evento and comando:
            ao_evento("ferramenta", comando, None, None)
    elif tipo == "tool.execution_complete":
        chamada = pendentes.pop(dados.get("toolCallId"), {})
        codigo = (dados.get("shellExecution") or {}).get("exitCode")
        sucesso = bool(dados.get("success") and codigo == 0)
        if chamada.get("sentido") and sucesso and ao_alterar_rota:
            ao_alterar_rota(chamada["sentido"])
        if ao_evento and chamada.get("comando"):
            resposta = dados.get("result") or {}
            texto = resposta.get("content", "") if isinstance(resposta, dict) else str(resposta)
            ao_evento("ferramenta", chamada["comando"], texto, sucesso)
    elif tipo == "assistant.message" and ao_evento:
        mensagem = dados.get("content", "")
        if mensagem:
            ao_evento("modelo", mensagem, None, None)


def rodar_agente(pasta_teste, usuario, ao_alterar_rota=None,
                 ao_evento=None, ao_tokens=None, parada=None):
    copilot = os.path.expanduser(f"~{usuario}/.local/bin/copilot")
    regras = (PASTA_COPILOT / "AGENTS.md").read_text()
    pedido = regras + "\n\nPedido:\n" + (PASTA_COPILOT / "prompt.txt").read_text()

    comando = [
        "timeout", str(LIMITE_SEGUNDOS),
        "sudo", "-u", usuario, "-H",        # o agente roda como usuario comum, nunca como root
        copilot, "-p", pedido,
        "--model", MODELO,
        "--reasoning-effort", "low",
        "--available-tools", "bash",        # so pode usar o terminal...
        "--allow-tool", "shell(rede:*)",    # ...e no terminal so o comando "rede"
        "--disable-builtin-mcps",
        "--no-custom-instructions",
        "--no-ask-user",
        "--output-format", "json",
        "--usage-output-file", str(pasta_teste / "tokens.json"),
    ]

    arquivo_log = pasta_teste / "agente.jsonl"
    arquivo_tokens = pasta_teste / "tokens.json"
    with open(arquivo_log, "w") as saida, open(pasta_teste / "erros.txt", "w") as erros:
        processo = subprocess.Popen(comando, stdout=saida, stderr=erros,
                                    stdin=subprocess.DEVNULL, cwd=PASTA_COPILOT,
                                    start_new_session=True)
        try:
            if ao_alterar_rota or ao_evento or ao_tokens or parada is not None:
                _acompanhar_rotas(arquivo_log, processo, ao_alterar_rota,
                                  ao_evento, arquivo_tokens, ao_tokens, parada)
            return processo.wait()
        finally:
            encerrar_processo(processo)


def ler_resultado(pasta_teste):
    """Cria acoes.txt (o que o agente disse e fez) e devolve (comandos, tokens)."""
    comandos = 0

    with open(pasta_teste / "agente.jsonl") as log, open(pasta_teste / "acoes.txt", "w") as acoes:
        for linha in log:
            try:
                evento = json.loads(linha)
            except ValueError:
                continue  # linha que nao e um evento do Copilot
            tipo = evento.get("type")
            dados = evento.get("data", {})

            if tipo == "assistant.message" and dados.get("content"):
                acoes.write(f"AGENTE: {dados['content']}\n\n")
            elif tipo == "tool.execution_start":
                comandos += 1
                argumentos = dados.get("arguments") or {}
                texto = argumentos.get("command", "") if isinstance(argumentos, dict) else str(argumentos)
                acoes.write(f"$ {texto}\n")
            elif tipo == "tool.execution_complete":
                resposta = dados.get("result") or {}
                texto = resposta.get("content", "(sem resposta)") if isinstance(resposta, dict) else str(resposta)
                acoes.write(f"{texto}\n\n")

    arquivo_tokens = pasta_teste / "tokens.json"
    tokens = _ler_tokens(arquivo_tokens) if arquivo_tokens.exists() else None
    if tokens is None:
        tokens = ""

    return comandos, tokens
