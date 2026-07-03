# Trade-offs — Synka Lens

Decisões que abrem mão de algo para priorizar outra coisa. Cada escolha tem custo; este documento o torna explícito e dá contexto a decisões futuras de evolução.

## Python para a camada de dados

**Escolha:** Python, não C#/.NET (stack do SynkaCore e SynkaStudio).

**Prioriza:** alinhamento com o ecossistema de engenharia de dados. As ferramentas e o vocabulário de dados — DuckDB, pandas, Parquet — vivem em Python. É o que o mercado de dados espera encontrar no código.

**Abre mão de:** coesão de stack (o ecossistema passa a ter duas linguagens) e garantias de compilação (Python não impõe fronteiras nem tipos em tempo de compilação; erros que um compilador pegaria aparecem em execução). Exige mais disciplina de design e cobertura de testes.

**Reconsiderar:** a divisão por linguagem segue a natureza de cada camada — coleta resiliente em C#, análise batch em Python. Não há motivo previsto para unificar.

## DuckDB como motor de transformação

**Escolha:** DuckDB para as transformações de silver e gold, não pandas puro.

**Prioriza:** expressividade e desempenho. As transformações são escritas em SQL — mesma linguagem que consulta a fonte — mantendo a lógica declarativa. DuckDB é colunar e processa agregações sobre grande volume sem servidor.

**Abre mão de:** uma dependência a mais (para volume trivial, pandas bastaria) e a curva de conhecer a API do DuckDB além do SQL.

**Reconsiderar:** se o volume exigir processamento distribuído, reavaliar Spark/PySpark — com a consciência de que processamento distribuído tem custo operacional real e raramente se justifica para volumes de PME.

## Streamlit para a apresentação

**Escolha:** Streamlit, não uma plataforma web tradicional (HTML/CSS/JS + API).

**Prioriza:** foco em dados e lógica. Streamlit elimina o front-end tradicional, permitindo construir a apresentação em Python e concentrar esforço na arquitetura de dados. Serve no navegador, acessível de qualquer dispositivo na rede sem instalação.

**Abre mão de:** controle fino de interface (Streamlit é opinativo; layouts muito customizados são limitados) e eficiência do modelo de execução (reexecuta o script a cada interação — irrelevante para dashboards sobre dados já agregados, mitigável com cache em volume alto). Não serve para operação transacional; entrada de dados é responsabilidade do SynkaStudio.

**Reconsiderar:** enquanto o Lens for analítico e read-only, Streamlit é adequado. Fidelidade visual total ou interação transacional apontariam para um front-end dedicado em versão futura.

## Extração completa, sem leitura incremental

**Escolha:** a V1.0 lê todas as leituras da fonte a cada execução.

**Prioriza:** simplicidade. Para o volume atual, extrair tudo é direto e correto.

**Abre mão de:** escalabilidade. Quando a tabela tiver grande volume, carregar tudo na memória é gargalo de tempo e memória.

**Reconsiderar:** na V1.1, extração incremental por marca de progresso (high-water mark): ler apenas o que chegou desde a última execução, de forma idempotente. É o primeiro limite conhecido da V1.0.

## Lógica de status replicada em SQL

**Escolha:** a comparação valor-acima-do-limiar existe no domínio (Python, testada) e no SQL do silver.

**Prioriza:** desempenho. A transformação roda em lote no DuckDB; chamar a função Python linha a linha seria ordens de magnitude mais lento.

**Abre mão de:** fonte única absoluta da lógica — a comparação está em dois lugares. O limiar (o número) continua de fonte única, passado como parâmetro; apenas a comparação (`>`) está replicada.

**Reconsiderar:** aceitável enquanto a regra de status é trivial. Se a lógica ficar complexa (múltiplas condições), avaliar processar em Python via Arrow, pesando o custo de desempenho.

## Conversão de NUMERIC para float

**Escolha:** o campo `value` (`NUMERIC` no PostgreSQL, `Decimal` em Python) é convertido para `float` na ingestão.

**Prioriza:** praticidade analítica. `float` é o tipo esperado pelas ferramentas numéricas, mais leve de processar.

**Abre mão de:** exatidão decimal. Para dados financeiros, a troca seria incorreta.

**Reconsiderar:** adequado para telemetria de sensor, que já contém ruído físico e não exige exatidão decimal. Não se aplica a dados que exijam precisão exata.

## Dependência de dados de timezone (tzdata)

**Escolha:** `tzdata` declarado como dependência de runtime.

**Prioriza:** correção. O DuckDB precisa de dados de fuso para materializar `TIMESTAMPTZ`; os dados do SynkaCore são timezone-aware (a escolha correta para dados industriais).

**Abre mão de:** nada substancial. O custo é uma dependência que só se manifesta em ambiente limpo — o tipo de dependência implícita que quebra em produção se não declarada. Por isso está no `pyproject.toml`.

**Reconsiderar:** não aplicável; é requisito do ambiente.

## Schema do banco não versionado

**Escolha:** na V1.0, o schema do TimescaleDB é criado manualmente, fora do projeto.

**Prioriza:** velocidade inicial. O foco da V1.0 é o fluxo de dados, não automação de infraestrutura.

**Abre mão de:** reprodutibilidade. Criar o ambiente do zero exige executar comandos de schema manualmente, com risco de erro por omissão.

**Reconsiderar:** ao introduzir orquestração com docker-compose, incluir script de inicialização que cria o schema na primeira subida do banco.

## Testes majoritariamente de integração

**Escolha:** exceto os de domínio, os testes escrevem Parquet em disco e leem de volta.

**Prioriza:** validação realista do comportamento das camadas sobre dados em formato real.

**Abre mão de:** velocidade e isolamento puro. São rápidos hoje, mas dependem de I/O; alguns dependem do banco no ar.

**Reconsiderar:** quando a suíte crescer, separar unitários (rápidos, sempre) de integração (sob demanda) com marcadores do pytest. Planejado para a V1.1.