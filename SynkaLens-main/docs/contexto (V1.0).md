# Contexto de Desenvolvimento — Synka Lens V1.0

Registra as decisões técnicas, a estrutura e a estratégia de testes da V1.0 do Synka Lens. Existe para que o porquê de cada escolha seja reconstruível sem depender de memória. Para entender o projeto, este documento vem antes do código.

O Synka Lens é a camada analítica que lê séries temporais industriais de um TimescaleDB — alimentado pelo SynkaCore, a fonte dos dados — e as transforma em métricas de chão de fábrica. É uma aplicação read-only: lê, calcula, apresenta; não escreve na fonte.

## Escopo da V1.0

O menor corte vertical completo: o dado sai do TimescaleDB, atravessa três camadas de transformação (bronze, silver, gold), vira a métrica de disponibilidade de uma máquina, e é exibido num dashboard. Escopo estreito de propósito — uma máquina, uma métrica derivada — com fundação profunda: fronteiras corretas e testes nos caminhos que importam.

Princípio que guiou tudo: fino na largura, robusto na profundidade. Pouca funcionalidade, bem-estruturada, de modo que as próximas versões encaixem sem reescrever.

## Linguagem e disciplina

Python foi escolhido por alinhamento com o ecossistema de engenharia de dados — DuckDB, Parquet, pandas — onde as ferramentas e o vocabulário vivem. A análise é batch, periódica, tolerante a atraso: o cenário onde Python é a ferramenta certa.

Python não impõe fronteiras nem tipos em compilação. Essas garantias são compensadas com disciplina: type hints em tudo, imutabilidade onde cabe (`frozen=True`), testes nas regras de decisão, e fronteiras respeitadas conscientemente. A liberdade da linguagem exige rigor do desenvolvedor — o perigo mora no tipo e na fronteira, não na memória.

## Arquitetura: monólito modular

Processo único, deploy único, sem rede entre as partes. Microsserviços seriam custo operacional sem retorno para um sistema que roda na mesma máquina.

Modular significa fronteiras internas: apresentação depende de transformação, que depende de domínio; o domínio não depende de nada externo. A seta aponta para dentro porque o significado do negócio é a parte mais estável e crítica, e não pode depender de detalhes voláteis como ferramenta de exibição ou formato de armazenamento.

Em Python, essa fronteira é mantida por disciplina, não por compilador — nada impede a apresentação de importar a ingestão diretamente; cabe ao desenvolvedor não fazer.

## As três camadas

**Bronze** copia a fonte fielmente, sem interpretar. É o ponto de recuperação: se a lógica do silver tiver defeito, o reprocessamento parte do bronze, sem reextrair do banco. Interpretar o dado no bronze destrói essa função — a interpretação pode estar errada, e o original deixa de existir. A única coluna derivada é `date`, para particionamento físico (`date=AAAA-MM-DD/`, lido nativamente pelo DuckDB), não interpretação.

**Silver** transforma medição solta em medição com contexto. Por leitura, calcula: o intervalo desde a anterior (`LAG`); se foi gap de conexão (intervalo acima do limiar — período de cegueira do sistema, distinto de máquina parada); e o status (rodando/parada conforme o valor cruza o limiar). Usa `PARTITION BY tag` para cada máquina ter sua sequência temporal própria — sem efeito visível com uma tag, mas fundação testada para múltiplas.

**Gold** agrega o status em disponibilidade. A duração de cada leitura é o tempo até a próxima (`LEAD`). O tempo de gap é excluído do cálculo: disponibilidade = rodando / (rodando + parado). Contabilizar o gap como parada puniria a máquina por tempo não medido; como rodando, inflaria a métrica. O gap é reportado à parte, como indicador de qualidade da coleta.

## DuckDB como motor de transformação

As transformações de silver e gold são escritas em SQL sobre DuckDB, não em pandas. SQL mantém a lógica declarativa, na mesma linguagem que consulta a fonte; DuckDB é colunar e processa agregações sobre grande volume sem servidor. As camadas persistem em Parquet — colunar, comprimido, com schema — particionado por data.

Pandas aparece só na fronteira de apresentação (a camada de leitura do dashboard), onde é o formato que o Streamlit consome. Cada ferramenta na camada certa: SQL na transformação em lote, pandas na entrega para a tela.

## Bug de alinhamento temporal

Durante o desenvolvimento, o gold reportou disponibilidade inflada. Causa: o silver marca gap com `LAG` (intervalo para trás) — a leitura *depois* do buraco recebe a marca. O gold mede duração com `LEAD` (intervalo para frente) — a leitura *antes* do buraco carrega os segundos do buraco. As duas perspectivas não coincidem na mesma linha; o gold confiava na marca do silver, ancorada no intervalo errado para seu propósito.

Correção: o gold avalia o gap sobre a própria duração que calcula, com o mesmo limiar, em vez de herdar a marca do silver. Há, portanto, duas noções de gap — silver ("esta leitura veio depois de um buraco?") e gold ("este trecho de tempo foi cego?"). São perguntas diferentes, ambas válidas.

O bug foi detectado porque o teste do gold tinha resultado calculado na mão e não bateu. Princípio reforçado: testes verificam números previstos, não o que sai.

## Regras no domínio

O módulo de domínio contém vocabulário e regras, isolado de tecnologia externa:

- `MachineStatus` — `Enum` com três estados: `RUNNING`, `STOPPED`, `NO_DATA`. Três porque o gap (cegueira) é categoria distinta de parada.
- `StatusThresholds` — `dataclass` imutável com os dois limiares (valor de rodando, segundos de gap), como fonte única.
- `classify_status` e `is_connection_gap` — funções puras: entrada e saída, sem estado nem I/O, trivialmente testáveis.

Limiares nunca são números mágicos espalhados pelo código; vêm do `StatusThresholds`, passados ao SQL como parâmetros nomeados. Mudança ocorre num só lugar.

Classes modelam dados (`Enum`, `dataclass`); funções operam sobre dados. Classe-com-comportamento fica reservada a estado mutável real, que no pipeline é exceção. Função pura é frequentemente mais explícita que método de objeto — não esconde entradas no `self`.

## Limiares calibrados sobre dados reais

Os limiares saíram da inspeção dos dados reais, não de suposição. As leituras (uma esteira, temperatura) mostraram intervalo normal de 2 a ~13s entre leituras, um gap de ~300s, e valores de ~24°C (ociosa) a ~66°C (operando).

- **Limiar de gap: 30 segundos.** Na zona morta entre o maior intervalo normal (~13s) e o menor gap real (~300s). Margem dos dois lados: não dispara em variação natural, não deixa passar gap real.
- **Limiar de status: 40°C.** Abaixo da média, separando o vale ocioso do ciclo de operação.

Calibrados sobre amostra pequena (uma sessão de coleta). Por isso são configuráveis, não fixos: dados futuros com intervalos maiores se ajustam num só lugar. Calibração baseada em fato; configurabilidade protege contra a amostra ter sido limitada.

## Estratégia de testes

18 testes, cada um atacando um caminho de decisão ou um limite, não o caminho feliz. Dois ou três testes que atacam fronteiras valem mais que dez que repetem o meio.

- **Domínio:** valor acima, abaixo e exatamente no limiar (dos dois lados), porque o limite exato é onde `>` vs `>=` mente.
- **Silver:** detecção de gap com cenário forçado (intervalo grande entre duas leituras).
- **Gold:** disponibilidade com exclusão de gap, com resultado calculado na mão (50%).
- **Múltiplas máquinas:** duas tags com timestamps intercalados de propósito, para que, se o `PARTITION BY tag` vazar, o `LEAD` de uma pegue a leitura da outra e o número quebre. Valida o isolamento das sequências temporais.
- **Casos-limite:** disponibilidade 0% por dois caminhos distintos — só-gaps (cai no ramo de divisão evitada, observed=0) e sempre-parada (faz a divisão real 0/observed); e leitura única, a fronteira mínima de dados, que não deve quebrar o pipeline.
- **End-to-end:** bronze→silver→gold encadeados sobre um fluxo que mistura todos os comportamentos (rodando, parado, gap), com resultado calculado na mão (75%) e a invariante de que o silver não perde nem inventa leituras — a contagem de entrada e saída é igual. É o único teste que valida a integração entre as camadas, onde bugs de junção (como o de alinhamento temporal) se escondem.

Não testado de propósito: sequência vazia (tratamento de apresentação, resolvido no dashboard com aviso de ausência de dados); dados malformados (a fonte garante o schema via `NOT NULL`; defender contra o que a fonte não produz adiciona código sem cobrir risco). O orquestrador também não tem teste — sua lógica própria é mínima (cria diretórios, chama funções já testadas em sequência), e validá-lo seria testar orquestração de baixo valor.

A maioria dos testes é de integração: escrevem Parquet em disco e leem de volta, alguns dependem do banco no ar. São rápidos hoje, mas a separação entre unitários (rápidos, sempre) e integração (sob demanda), com marcadores do pytest, está planejada para a V1.1.

## Dívidas conscientes

- **Extração completa, sem incremental.** Correto para o volume atual; gargalo de memória quando a tabela crescer. V1.1 traz extração incremental por marca de progresso (high-water mark).
- **Lógica de status replicada em SQL.** A comparação valor-acima-do-limiar existe no domínio (testada) e no SQL do silver, porque a transformação roda em lote no DuckDB e chamar a função Python linha a linha seria lento. O limiar é fonte única (parâmetro); só a comparação (`>`) está replicada. Aceitável enquanto a regra é trivial.
- **`tzdata` como dependência.** O DuckDB precisa de dados de fuso para materializar `TIMESTAMPTZ`. Só se manifesta em ambiente limpo — declarado no `pyproject.toml` para não quebrar em produção.
- **Schema do banco não versionado.** Criado manualmente fora do projeto na V1.0; automação na subida do ambiente fica para a versão de orquestração.

## Apresentação

O dashboard Streamlit consome a camada gold e exibe; não calcula. A inteligência está no backend testado. A camada de leitura (`data_access.py`) é separada do dashboard (`dashboard.py`): a primeira lê os Parquets e serve em pandas, materializando `TIMESTAMPTZ` via `.df()` (caminho que não depende do módulo legado de timezone); o segundo desenha. Agregação para exibição — média por minuto no gráfico, para não plotar centenas de pontos brutos — fica na camada de leitura, não no dashboard.

O pipeline (bronze→silver→gold) e o dashboard são momentos separados: o pipeline processa e grava os Parquets; o dashboard lê o resultado. Não rodam juntos — o dashboard lê o estado mais recente gerado pelo pipeline, que executa à parte.