# Arquitetura — Synka Lens

Descreve a estrutura de software do Synka Lens: as fronteiras entre módulos, a regra de dependência, e o porquê de cada decisão estrutural.

## Princípio organizador: separação por taxa de mudança

Os módulos são separados por responsabilidade que muda por razão independente, não por tipo de tecnologia. Três responsabilidades mudam por motivos distintos:

- **Ingestão** muda quando a fonte muda — schema do TimescaleDB, nova tag, nova máquina. Não muda quando uma fórmula de métrica é ajustada.
- **Transformação** muda quando uma regra de negócio muda — a definição de máquina parada, a fórmula de disponibilidade. Não muda quando o dashboard ganha um gráfico.
- **Apresentação** muda quando uma pergunta visual muda — novo gráfico, novo filtro. Não muda quando a query de ingestão é corrigida.

Separar essas responsabilidades em módulos distintos evita que uma mudança em uma force a abertura do código das outras.

## Monólito modular

Processo único, deploy único, sem rede entre as partes. Microsserviços adicionariam latência, falhas parciais e complexidade de orquestração para separar componentes que rodam na mesma máquina — custo sem retorno para este problema.

Modular significa fronteiras internas: cada camada tem uma responsabilidade e depende apenas da camada imediatamente interna.

### Fronteira por disciplina

Em linguagens compiladas com referências de projeto explícitas, o compilador impede um módulo de domínio de importar a infraestrutura. Python não tem essa imposição: nada impede a apresentação de importar a ingestão diretamente, furando a transformação.

Aqui a regra de dependência é mantida por disciplina consciente, não por verificação automática. A linguagem permite a violação; cabe ao desenvolvedor não cometê-la. Menos cerimônia de código, mais responsabilidade de design.

## Regra de dependência

As dependências apontam para dentro:

```
apresentação  →  transformação  →  domínio
```

O domínio não importa nada externo — nem DuckDB, nem Streamlit, nem driver de banco. Contém apenas vocabulário e regras de negócio. A razão: o significado do negócio (o que é máquina rodando, como se calcula disponibilidade) é a parte mais estável e crítica, e não pode depender de detalhes voláteis como ferramenta de exibição ou formato de armazenamento.

## Camadas de dados

### Bronze

Cópia fiel da fonte, sem transformação, em Parquet. Serve de ponto de recuperação: se a lógica do silver tiver defeito, o reprocessamento parte do bronze, sem reextrair da fonte. No momento em que o bronze interpreta ou limpa o dado, perde essa função — a interpretação pode estar errada, e o original deixa de existir.

A única coluna derivada é `date`, usada para particionamento físico (`date=AAAA-MM-DD/`), não como interpretação do dado. O DuckDB lê partições nesse formato nativamente, o que permite pular partições irrelevantes na leitura.

### Silver

Onde residem qualidade e enriquecimento. Para cada leitura, calcula:

- O **intervalo desde a leitura anterior**, via `LAG(time)`.
- Se o intervalo é um **gap de conexão** — período em que o coletor esteve cego (queda de rede, de banco, reinício). Gap não é máquina parada; é ausência de medição. Confundir os dois corrompe a métrica. O critério é o intervalo exceder o limiar de gap.
- O **status** — rodando ou parada, conforme o valor exceda ou não o limiar de valor.

A window function usa `PARTITION BY tag`: cada máquina tem sua própria sequência temporal. Com uma tag, não há diferença visível; com várias, impede que o cálculo de intervalo de uma máquina use a leitura de outra.

A separação entre bronze e silver existe porque a limpeza é interpretação que pode mudar, enquanto o dado bruto é fato que não muda.

### Gold

Agrega o status do silver em disponibilidade — percentual do tempo rodando. A duração de cada leitura é o tempo até a próxima, via `LEAD(time)`.

O tempo de gap é excluído do cálculo: disponibilidade = tempo rodando / (rodando + parado), sem o tempo cego no denominador. Contabilizar o gap como parada puniria a máquina por um período que ninguém mediu; como rodando, inflaria a métrica com tempo não observado. O tempo de gap é reportado à parte, como indicador de qualidade da coleta.

## Duas noções de gap

Há dois conceitos de gap no projeto, e são respostas a perguntas diferentes:

- No **silver**, gap é calculado com `LAG` (intervalo para trás): a leitura recebe a marca se o intervalo *desde a anterior* excede o limiar. Responde "esta leitura veio depois de um buraco?".
- No **gold**, gap é avaliado sobre a duração calculada com `LEAD` (intervalo para frente): o trecho de tempo é cego se o intervalo *até a próxima* excede o limiar. Responde "este trecho de tempo foi cego?".

As duas perspectivas não coincidem na mesma linha. O gold avalia o gap sobre a própria duração que soma, em vez de herdar a marca do silver — caso contrário, a marca (ancorada no intervalo para trás) não alinharia com a duração (intervalo para frente), e o cálculo erraria.

## Fronteira da apresentação

O dashboard não calcula métrica. Lê a camada gold já calculada e exibe. Uma fórmula calculada dentro do dashboard ficaria presa na apresentação — não testável isoladamente, e reexecutada a cada interação do usuário (o Streamlit reexecuta o script a cada evento). Calcular é responsabilidade da camada gold, testada. A apresentação é vidro.

A camada de leitura (`app/data_access.py`) é separada do dashboard (`app/dashboard.py`): a primeira lê os Parquets e serve em pandas; o segundo só desenha. Agregações para exibição (como média por minuto no gráfico) ficam na camada de leitura, não no dashboard.

## Domínio como fonte única de regra

Regras críticas — como o limiar que distingue rodando de parada — não são valores espalhados pelo código. Vivem no módulo de domínio, configuráveis, a partir de fonte única, e são passadas ao SQL como parâmetros nomeados. Um limiar repetido dentro de uma query acopla regra de negócio a detalhe de implementação; quando muda (máquina diferente, recalibração), a mudança deve ocorrer num único lugar.

O domínio usa classes para modelar dados (`Enum` para o conjunto fechado de status, `dataclass` imutável para os limiares) e funções puras para operar sobre dados (classificação, detecção de gap). Funções puras — entrada e saída, sem estado nem I/O — são trivialmente testáveis.

## Estrutura de diretórios

A estrutura materializa conforme o código de cada camada passa a existir; não se criam pastas vazias antecipando o que não foi construído.

```
SynkaLens/
├── pyproject.toml
├── run_pipeline.py        orquestrador: encadeia as camadas sobre dados reais
├── run_dashboard.sh       executa o dashboard a partir da raiz do projeto
├── README.md
├── docs/
├── src/
│   └── synka_lens/
│       ├── config.py              configuração validada na inicialização
│       ├── ingestion/             fronteira com a fonte (TimescaleDB)
│       ├── transformation/        bronze, silver, gold
│       └── domain/                regras e vocabulário do negócio
├── app/
│   ├── data_access.py             leitura dos Parquets, serve em pandas
│   └── dashboard.py               apresentação (Streamlit)
├── data/                          artefatos locais (não versionado)
└── tests/
```

O pacote `synka_lens` é instalado em modo editável, o que torna os imports consistentes entre execução de testes (pytest, a partir da raiz) e execução do dashboard (Streamlit, com a raiz no `PYTHONPATH` via `run_dashboard.sh`).