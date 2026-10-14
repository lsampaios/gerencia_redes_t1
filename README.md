# Laboratorio FCAPS

Compara um agente de IA (Copilot CLI) com um script fixo para corrigir perda de
pacotes em uma rede Mininet. Os testes usam perdas de 30%, 80% e 0% no enlace
r1-r2. Quando ha falha, o trafego deve ser desviado por r3, sem remover a perda.

## Preparacao

Requer Linux, Python 3, Mininet, ferramentas de rede e acesso a `sudo`.
Para usar o agente, o Copilot CLI deve estar autenticado em `~/.local/bin/copilot`.

Na pasta do projeto, instale ou atualize o comando `rede`:

```bash
sudo install -m 755 rede.py /usr/local/bin/rede
```

Libere somente esse comando no sudoers:

```bash
sudo visudo -f /etc/sudoers.d/fcaps-rede
```

Substitua `SEU_USUARIO` pelo seu usuario:

```sudoers
SEU_USUARIO ALL=(root) NOPASSWD: /usr/local/bin/rede
```

## Pelo terminal

Na pasta do projeto, rode tres repeticoes (18 execucoes):

```bash
sudo python3 experimentar.py 3
```

Sem o numero, roda uma repeticao. Para executar somente o script:

```bash
sudo python3 experimentar.py 1 --so-script
```

## Pelo navegador

```bash
sudo -v && python3 painel.py
```

Abra **http://127.0.0.1:8765/**, escolha as repeticoes e clique em
**Iniciar experimento**. 

## Resultados

Salvos em `resultados/<data>/`, com CSV, resumo e logs de cada teste.
A parada preserva os testes concluidos. Nao execute duas rodadas ao mesmo tempo.
