"""Painel web do experimento Mininet."""

import argparse
import json
import secrets
import subprocess
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from visualizacao import Visualizacao

PASTA = Path(__file__).resolve().parent
MARCADOR = "FCAPS_WEB:"


class VisualizacaoWeb(Visualizacao):
    def __init__(self, total_testes):
        super().__init__(total_testes, interativo=False)
        self.eventos = []
        self.resultados = []
        self.falha_ativa = False
        self.rotas_confirmadas = False
        self.pasta_resultados = None

    def evento(self, tipo, texto):
        self.eventos.append({"hora": datetime.now().strftime("%H:%M:%S"),
                             "tipo": tipo, "texto": texto[:12000]})
        self.eventos = self.eventos[-300:]

    def iniciar_teste(self, nome, perda, executor, repeticao):
        self.falha_ativa = False
        self.rotas_confirmadas = False
        self.evento("teste", f"{nome} / {executor} / repeticao {repeticao}")
        super().iniciar_teste(nome, perda, executor, repeticao)

    def atualizar(self, etapa):
        if etapa in ("Agente inspecionando e tentando corrigir", "Script comparativo executando"):
            self.falha_ativa = True
        if etapa == "Encerrando topologia Mininet":
            self.falha_ativa = False
        self.evento("etapa", etapa)
        super().atualizar(etapa)

    def rota_alterada(self, sentido):
        self.rotas_confirmadas = False
        self.evento("rota", f"Comando de desvio de {sentido} concluido; aguardando verificacao")
        super().rota_alterada(sentido)

    def confirmar_rotas(self, ida_r3, volta_r3):
        self.rotas_confirmadas = True
        self.evento("verificacao", f"Rotas verificadas: ida por r3={ida_r3}, volta por r3={volta_r3}")
        super().confirmar_rotas(ida_r3, volta_r3)

    def mostrar_mensagem_modelo(self, mensagem):
        if mensagem:
            self.evento("modelo", mensagem)
        super().mostrar_mensagem_modelo(mensagem)

    def mostrar_ferramenta(self, comando, resultado=None, sucesso=None):
        texto = comando if resultado is None else f"{comando}\n{'OK' if sucesso else 'ERRO'}\n{resultado}"
        self.evento("comando" if resultado is None else "resposta", texto)
        super().mostrar_ferramenta(comando, resultado, sucesso)

    def registrar(self, resultado):
        self.resultados.append(dict(resultado))
        self.evento("resultado", f"{resultado['teste']}: {'sucesso' if resultado['sucesso'] else 'falha'}")
        super().registrar(resultado)

    def finalizar(self, pasta, interrompido=False):
        self.pasta_resultados = str(pasta)
        self.falha_ativa = False
        super().finalizar(pasta, interrompido=interrompido)

    def _desenhar(self, final=False):
        dados = {"estado": dict(self.estado), "total": self.total_testes,
                 "concluidos": self.concluidos, "sucessos": self.sucessos,
                 "tokens": self.tokens_execucao, "tokens_total": self.tokens_total,
                 "uso_tokens": self.uso_tokens, "eventos": self.eventos,
                 "resultados": self.resultados, "falha_ativa": self.falha_ativa,
                 "rotas_confirmadas": self.rotas_confirmadas,
                 "pasta": self.pasta_resultados}
        print(MARCADOR + json.dumps(dados, ensure_ascii=True), flush=True)


class Laboratorio:
    def __init__(self):
        self.trava = threading.Lock()
        self.estado = {"status": "pronto", "dados": None, "erro": "", "log": ""}
        self.token = secrets.token_urlsafe(32)
        self.processo = None
        self.parada_solicitada = False

    def iniciar(self, repeticoes, so_script):
        with self.trava:
            if self.estado["status"] in ("executando", "parando"):
                return False
            self.parada_solicitada = False
            self.estado = {"status": "executando", "dados": None, "erro": "", "log": ""}
        threading.Thread(target=self.executar, args=(repeticoes, so_script), daemon=True).start()
        return True

    def enviar_parada(self):
        if self.processo is not None:
            try:
                self.processo.stdin.write("parar\n")
                self.processo.stdin.flush()
            except (BrokenPipeError, OSError):
                pass

    def parar(self):
        with self.trava:
            if self.estado["status"] == "parando":
                return True
            if self.estado["status"] != "executando":
                return False
            self.parada_solicitada = True
            self.estado["status"] = "parando"
            self.enviar_parada()
        return True

    def executar(self, repeticoes, so_script):
        comando = ["sudo", "-n", "python3", "-u", str(PASTA / "experimentar.py"),
                   str(repeticoes), "--web"]
        if so_script:
            comando.append("--so-script")
        try:
            processo = subprocess.Popen(comando, cwd=PASTA, stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT, stdin=subprocess.PIPE,
                                        text=True, errors="replace")
            with self.trava:
                self.processo = processo
                if self.parada_solicitada:
                    self.enviar_parada()
            for linha in processo.stdout:
                with self.trava:
                    if linha.startswith(MARCADOR):
                        self.estado["dados"] = json.loads(linha[len(MARCADOR):])
                    else:
                        self.estado["log"] = (self.estado["log"] + linha)[-12000:]
            codigo = processo.wait()
            processo.stdin.close()
            with self.trava:
                self.processo = None
                interrompido = self.parada_solicitada and codigo == 130
                self.estado["status"] = "interrompido" if interrompido else "concluido" if codigo == 0 else "erro"
                if codigo != 0 and not interrompido:
                    self.estado["erro"] = self.estado["log"] or f"Experimento terminou com codigo {codigo}."
        except (OSError, ValueError) as erro:
            with self.trava:
                self.processo = None
                self.estado.update(status="erro", erro=str(erro))


class Servidor(ThreadingHTTPServer):
    def __init__(self, endereco):
        super().__init__(endereco, Pagina)
        self.laboratorio = Laboratorio()


class Pagina(BaseHTTPRequestHandler):
    def resposta(self, codigo, corpo, tipo="application/json; charset=utf-8"):
        conteudo = json.dumps(corpo).encode() if isinstance(corpo, dict) else corpo
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(conteudo)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(conteudo)

    def local(self):
        return self.headers.get("Host") in (
            f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}")

    def do_GET(self):
        if not self.local():
            self.resposta(403, {"erro": "Acesso apenas local."})
        elif self.path == "/":
            self.resposta(200, (PASTA / "painel.html").read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/estado":
            with self.server.laboratorio.trava:
                self.resposta(200, {**self.server.laboratorio.estado, "token": self.server.laboratorio.token})
        else:
            self.resposta(404, {"erro": "Nao encontrado."})

    def do_POST(self):
        laboratorio = self.server.laboratorio
        if not self.local() or self.headers.get("X-FCAPS-Token") != laboratorio.token:
            self.resposta(403, {"erro": "Requisicao nao autorizada."})
            return
        if self.path == "/api/parar":
            if laboratorio.parar():
                self.resposta(202, {"ok": True})
            else:
                self.resposta(409, {"erro": "Nenhum experimento em execucao."})
            return
        if self.path != "/api/iniciar":
            self.resposta(404, {"erro": "Nao encontrado."})
            return
        try:
            tamanho = int(self.headers.get("Content-Length", "0"))
            if not 0 < tamanho <= 1024:
                raise ValueError()
            pedido = json.loads(self.rfile.read(tamanho))
            repeticoes = pedido["repeticoes"]
            so_script = pedido.get("so_script", False)
            if type(repeticoes) is not int or not 1 <= repeticoes <= 20 or type(so_script) is not bool:
                raise ValueError()
        except (ValueError, KeyError, TypeError):
            self.resposta(400, {"erro": "Numero de repeticoes invalido (1 a 20)."})
            return
        if laboratorio.iniciar(repeticoes, so_script):
            self.resposta(202, {"ok": True})
        else:
            self.resposta(409, {"erro": "Ja existe um experimento em execucao."})

    def log_message(self, formato, *argumentos):
        pass


def main():
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--porta", type=int, default=8765)
    porta = argumentos.parse_args().porta
    servidor = Servidor(("127.0.0.1", porta))
    print(f"Painel: http://127.0.0.1:{servidor.server_port}", flush=True)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.server_close()


if __name__ == "__main__":
    main()