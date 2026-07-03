# Roadmap — Synka Lens

Apenas o escopo marcado como concluído existe. O restante é planejamento e pode mudar conforme a necessidade real.

Filosofia de versionamento: cada versão adiciona uma capacidade encaixando na estrutura existente, sem reescrever o que veio antes. A base é mantida robusta nas fronteiras para sustentar esse crescimento. Cada versão concluída recebe um documento de contexto próprio (`contexto (Vx.y).md`), que registra o raciocínio daquela versão e preserva o histórico de decisões sem depender de memória externa.

## V1.0 — concluída

Menor corte vertical completo: o dado percorre todas as camadas, da fonte ao dashboard, para uma máquina e a métrica de disponibilidade. O objetivo foi provar o fluxo inteiro com fundação sólida, não cobrir muitos casos.

- Ingestão das leituras do TimescaleDB (psycopg)
- Bronze: cópia fiel em Parquet particionado por data
- Silver: limpeza, detecção de gaps de conexão (LAG), classificação de status
- Gold: disponibilidade (LEAD), com exclusão do tempo de gap
- Domínio com regras isoladas e configuráveis, como fonte única
- Dashboard Streamlit: status atual, disponibilidade, gráfico temporal, tabela de leituras
- 18 testes cobrindo caminhos de decisão, integração entre camadas e casos-limite

Raciocínio completo em `contexto (V1.0).md`.

## V1.1 — ingestão incremental

- Extração incremental por marca de progresso (high-water mark): ler apenas leituras novas desde a última execução
- Idempotência: reexecução não duplica dados
- Resolve o principal limite de escalabilidade da V1.0
- Separação de testes unitários e de integração com marcadores do pytest

## V1.2 — múltiplas máquinas

- Suporte a múltiplas tags simultâneas (a estrutura já está preparada e testada)
- Dashboard com seleção de máquina
- Métricas por máquina

## V1.3 — orquestração e infraestrutura

- Orquestração do pipeline com agendamento, retry e observabilidade estruturada
- Healthcheck antes de ler a fonte: não consultar o banco antes de ele estar pronto
- Schema versionado e criado automaticamente na subida do ambiente (docker-compose)

## Além

Não comprometido; ideias sujeitas a validação.

- Métricas adicionais conforme dados disponíveis: MTBF, tendências
- Alertas: detectar disponibilidade caindo e avisar, em vez de só exibir
- OEE completo (disponibilidade × performance × qualidade), que depende de dados operacionais do SynkaStudio — viável quando houver integração por camada de dado compartilhada
- Demonstração da pipeline em ambiente de nuvem
- Melhorias e otimizações do dashboard (formatação, identidade visual)

Capacidades do ecossistema (não novos sistemas): alertas no Lens, integração de dados Studio↔Lens para OEE, e perfis de acesso no Studio (operador, supervisor, gestor — um sistema com papéis, não versões separadas).