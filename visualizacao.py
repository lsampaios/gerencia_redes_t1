"""Painel simples de terminal para acompanhar o experimento FCAPS."""

import sys
import textwrap
from threading import Event, Lock, Thread


class Visualizacao:
    def __init__(self, total_testes, interativo=None):
        self.total_testes = total_testes
        self.interativo = sys.stdout.isatty() if interativo is None else interativo
        self.concluidos = 0
        self.sucessos = 0
        self.tokens_total = 0
        self.tokens_execucao = None
        self.uso_tokens = ""
        self.historico = []
        self.estado = {
            "teste": "Preparando",
            "perda": 0,
            "executor": "-",
            "repeticao": 0,
            "etapa": "Aguardando inicio",
            "saida_modelo": "Aguardando resposta do modelo",
            "atividade": "-",
            "ida_r3": False,
            "volta_r3": False,
        }
        self._parar = Event()
        self._trava = Lock()
        self._animador = None
        self._quadros = "|/-\\"
        self._quadro = 0

    def iniciar(self):
        if self.interativo:
            self._animador = Thread(target=self._animar, daemon=True)
            self._animador.start()
        self._desenhar()

    def iniciar_teste(self, nome, perda, executor, repeticao):
        with self._trava:
            self.estado.update({
                "teste": nome,
                "perda": perda,
                "executor": executor,
                "repeticao": repeticao,
                "etapa": "Iniciando teste",
                "saida_modelo": "Aguardando resposta do modelo" if executor == "agente" else "Script sem modelo de linguagem",
                "atividade": "Aguardando primeira acao",
                "ida_r3": False,
                "volta_r3": False,
            })
            self.tokens_execucao = None if executor == "agente" else "N/A"
            self.uso_tokens = ""
            self._desenhar()

    def atualizar(self, etapa):
        with self._trava:
            self.estado["etapa"] = etapa
            self._desenhar()

    def rota_alterada(self, sentido):
        with self._trava:
            chave = "ida_r3" if sentido == "ida" else "volta_r3"
            self.estado[chave] = True
            self.estado["etapa"] = f"Rota de {sentido} alterada para r3"
            self._desenhar()

    def confirmar_rotas(self, ida_r3, volta_r3):
        with self._trava:
            self.estado["ida_r3"] = ida_r3
            self.estado["volta_r3"] = volta_r3
            self._desenhar()

    def mostrar_mensagem_modelo(self, mensagem):
        if not mensagem:
            return
        with self._trava:
            self.estado["saida_modelo"] = " ".join(mensagem.split())
            self._desenhar()

    def mostrar_ferramenta(self, comando, resultado=None, sucesso=None):
        with self._trava:
            if resultado is None:
                self.estado["atividade"] = f"Executando: {comando}"
            else:
                linhas = [linha.strip() for linha in resultado.splitlines() if linha.strip()]
                resumo = linhas[-1] if linhas else "sem saida"
                estado = "OK" if sucesso else "erro"
                self.estado["atividade"] = f"Concluido ({estado}): {comando} | {resumo}"
            self._desenhar()

    def atualizar_tokens(self, tokens):
        with self._trava:
            self.tokens_execucao = tokens
            self._desenhar()

    def mostrar_uso_tokens(self, uso):
        with self._trava:
            self.uso_tokens = (
                f"Entrada: {uso['entrada']} (cache lido: {uso['cache']}) | "
                f"Saida: {uso['saida']} | Chamadas modelo: {uso['chamadas']}"
            )
            self._desenhar()

    def parar(self):
        self._parar.set()
        if self._animador:
            self._animador.join()

    def registrar(self, resultado):
        with self._trava:
            self.concluidos += 1
            if resultado["sucesso"]:
                self.sucessos += 1
            tokens = resultado.get("tokens", "")
            if isinstance(tokens, int):
                self.tokens_total += tokens
            tokens_texto = (
                str(tokens) if isinstance(tokens, int)
                else "N/A" if resultado["executor"] == "script"
                else "indisponivel"
            )
            status = "OK" if resultado["sucesso"] else "FALHOU"
            self.historico.append(
                f"{resultado['teste']} {resultado['executor']} "
                f"R{resultado['repeticao']}: {status} "
                f"({resultado['ttr_segundos']} s), tokens={tokens_texto}"
            )
            self.estado["etapa"] = f"Teste finalizado: {status}"
            self._desenhar()

    def finalizar(self, pasta, interrompido=False):
        self.parar()
        with self._trava:
            status = "interrompida" if interrompido else "concluida"
            self.estado["etapa"] = f"Rodada {status}. Resultados: {pasta}"
            self._desenhar(final=True)

    def _animar(self):
        while not self._parar.wait(0.3):
            with self._trava:
                self._quadro = (self._quadro + 1) % len(self._quadros)
                self._desenhar()

    @staticmethod
    def _linha(conteudo):
        return f"| {conteudo[:58]:<58} |"

    def _desenhar(self, final=False):
        if not self.interativo:
            perda = self.estado["perda"]
            ida = "h1 > r1 > r3 > r2 > h2" if self.estado["ida_r3"] else "h1 > r1 > r2 > h2"
            volta = "h2 > r2 > r3 > r1 > h1" if self.estado["volta_r3"] else "h2 > r2 > r1 > h1"
            tokens = self.tokens_execucao if self.tokens_execucao is not None else "aguardando"
            print(
                f"[{self.concluidos}/{self.total_testes}] {self.estado['teste']} "
                f"{self.estado['executor']} perda={perda}%: {self.estado['etapa']}\n"
                f"  Ida: {ida}\n  Volta: {volta}\n"
                f"  Tokens nesta execucao: {tokens}; acumulado: {self.tokens_total}\n"
                f"  Modelo: {self.estado['saida_modelo'][:220]}\n"
                f"  Atividade: {self.estado['atividade'][:220]}",
                flush=True,
            )
            return

        perda = self.estado["perda"]
        if perda == 0:
            principal = "sem falha"
        elif self.estado["ida_r3"] and self.estado["volta_r3"]:
            principal = "contornado"
        elif self.estado["ida_r3"] or self.estado["volta_r3"]:
            principal = "mudanca parcial"
        else:
            principal = f"perda {perda}%"
        ida = "[h1] -> [r1] -> [r3] -> [r2] -> [h2]" if self.estado["ida_r3"] else "[h1] -> [r1] -> [r2] -> [h2]"
        volta = "[h2] -> [r2] -> [r3] -> [r1] -> [h1]" if self.estado["volta_r3"] else "[h2] -> [r2] -> [r1] -> [h1]"

        progresso = self.concluidos / self.total_testes if self.total_testes else 0
        preenchido = int(progresso * 24)
        barra = "#" * preenchido + "-" * (24 - preenchido)
        marcador = " " if final else self._quadros[self._quadro]
        tokens_execucao = self.tokens_execucao if self.tokens_execucao is not None else "aguardando"
        linhas = [
            "+------------------------------------------------------------+",
            "|                 EXPERIMENTO DE REDE FCAPS                  |",
            "+------------------------------------------------------------+",
            self._linha(f"Progresso: [{barra}] {self.concluidos:02}/{self.total_testes:02}"),
            self._linha(f"Teste: {self.estado['teste']}  perda: {perda}%  repeticao: {self.estado['repeticao']}"),
            self._linha(f"Executor: {self.estado['executor']}"),
            *self._linhas(f"Etapa: {marcador} {self.estado['etapa']}"),
            self._linha(""),
            self._linha("  [h1] ---- [r1] ---- [r2] ---- [h2]"),
            self._linha("             \\          /"),
            self._linha("              +-- [r3] --+"),
            self._linha(""),
            self._linha(f"Topologia atual: {principal}"),
            *self._linhas(f"IDA:   {ida}"),
            *self._linhas(f"VOLTA: {volta}"),
            *self._linhas(f"Tokens desta execucao: {tokens_execucao}  Total agente: {self.tokens_total}"),
            *self._linhas(self.uso_tokens),
            *self._linhas(f"Modelo: {self.estado['saida_modelo']}"),
            *self._linhas(f"Atividade: {self.estado['atividade']}"),
            "+------------------------------------------------------------+",
            self._linha(f"Concluidos: {self.concluidos:02}/{self.total_testes:02}   Sucessos: {self.sucessos:02}   Falhas: {self.concluidos - self.sucessos:02}"),
        ]
        for linha in self.historico:
            linhas.extend(self._linhas(linha))
        linhas.append("+------------------------------------------------------------+")
        sys.stdout.write("\033[2J\033[H" + "\n".join(linhas) + "\n")
        sys.stdout.flush()

    @classmethod
    def _linhas(cls, conteudo):
        return [cls._linha(parte) for parte in textwrap.wrap(conteudo, width=58)] or [cls._linha("")]