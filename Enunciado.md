Especificação da Tarefa: Agente Inteligente Baseado em LLM/CLI para Gerenciamento de Rede (FCAPS)
Objetivo
Desenvolver e avaliar a atuação de um Agente Inteligente de Execução Operacional (utilizando plataformas no estilo Claude Code, CrewAI ou scripts de automação acoplados a LLMs com execução de código/CLI) para realizar tarefas autônomas de gerenciamento de rede baseadas no modelo FCAPS em um ambiente controlado.

Escopo do Trabalho
Plataforma/Ferramenta do Agente:

Utilizar ou estruturar uma plataforma de agente autônomo com acesso a terminal/CLI (ex.: Claude Code, LangGraph Agent com Tool Calling, ou CrewAI/AutoGPT com acesso a shell execution).

O agente deve ser capaz de:

Interpretar a intenção de gerenciamento (Prompt de Alto Nível).

Inspeccionar o estado do ambiente (executando comandos como ping, traceroute, snmpget, ip route, chamadas REST/RESTCONF ou consultas a APIs de monitoramento).

Decidir a ação corretiva/configuração necessária.

Executar alterações na rede (alterar rotas, criar regras de firewall via iptables, reconfigurar interfaces ou enviar requisições NETCONF).

Escolha da Tarefa FCAPS:

F (Fault): Diagnóstico autônomo de perda de pacotes em um enlace e redirecionamento dinâmico de tráfego.

C (Configuration): Leitura de um requisito em linguagem natural e aplicação automatizada da configuração correta nos dispositivos.

P (Performance): Análise de degradação de desempenho via logs/métricas e ajuste dinâmico de parâmetros de QoS.

S (Security): Identificação de padrões de ataque no tráfego e aplicação automatizada de bloqueio na CLI dos roteadores.

Ambiente Controlado:

Topologia simulada/emulada no Mininet, Containerlab ou ambiente com Docker/VMs.

Script de injeção de eventos (para simular a falha, o ataque ou o congestionamento sobre o qual o agente atuará).

2. Estrutura do Relatório de 4 Páginas (Modelo SBC)
O relatório deve seguir o modelo oficial de artigos da SBC (LaTeX/Word), contendo 4 páginas.

Página 1: Introdução e Contextualização
Título: Uso de Agentes de Execução Baseados em LLMs (Estilo Claude Code) para Gerenciamento Autônomo de Redes no Modelo FCAPS.

Resumo / Abstract: Resumo em português e inglês (máx. 150 palavras) destacando a aplicação de agentes LLM com capacidade de execução em CLI para automação de tarefas FCAPS.

1. Introdução:

Desafios da gerência tradicional de redes e o surgimento de plataformas de agentes com capacidade de execução de código/comandos (Code-Executing AI Agents).

Objetivos do trabalho e contribuições do teste prático.

2. Fundamentação Teórica:

O modelo FCAPS.

Agentes LLM com Tool Use e Execução CLI: Como plataformas como Claude Code funcionam (ciclo Thought $\rightarrow$ Action/Tool $\rightarrow$ Observation).

Página 2: Arquitetura do Agente e Integração com a Rede
3. Arquitetura da Solução:

Diagrama de Integração: Mostrar a comunicação entre o Agente LLM, a ferramenta de execução CLI/API e a topologia de rede controlada.

Capacidades do Agente (Tools/Ferramentas):

Ferramentas de Coleta: Scripts Bash/Python de monitoramento, consultas SNMP, leitura de logs.

Ferramentas de Atuação: Execução de comandos de rede (ip, tc, iptables, chamadas RESTCONF/NETCONF).

Engenharia de Prompt e Políticas de Segurança: Como o agente foi instruído para agir de forma segura no ambiente sem causar danos colaterais na rede.

Página 3: Experimentos em Ambiente Controlado
4. Metodologia do Experimento:

Topologia e Ferramentas: Descrição da rede controlada (Mininet/Docker) e da plataforma do agente (ex.: Claude Code / Custom LLM Agent).

Cenário de Teste FCAPS: Passo a passo da injeção do evento (ex.: injeção de latência ou bloqueio de um enlace).

5. Execução e Resultados:

Log de Raciocínio do Agente: Exemplo da sequência de passos tomada pelo agente (Análise do Prompt $\rightarrow$ Diagnóstico executado via CLI $\rightarrow$ Decisão $\rightarrow$ Comando de correção aplicado).

Métricas de Desempenho:

Tempo total para resolução do problema (Time to Resolution - TTR).

Número de chamadas de ferramentas/comandos necessários.

Assertividade das ações aplicadas (A taxa de sucesso no reparo da rede).

Página 4: Análise Crítica, Conclusão e Referências
5. Execução e Resultados (Análise Crítica):

Avaliação do risco de alucinação do LLM ao executar comandos diretos na infraestrutura de rede.

Comparação entre o agente LLM autônomo e scripts tradicionais de automação (Ansible/Python estático).

6. Conclusão:

Considerações finais sobre a viabilidade e maturidade do uso de agentes estilo Claude Code na gerência operacional de redes.

Propostas de trabalhos futuros (ex.: Human-in-the-loop para aprovação de comandos críticos).

Referências Bibliográficas:

Citações em formato SBC de artigos sobre LLM Agents, automação de redes, FCAPS e documentação das ferramentas utilizadas.