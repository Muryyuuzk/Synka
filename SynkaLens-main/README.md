# Synka Lens

Camada analítica do ecossistema Synka. Lê séries temporais industriais do TimescaleDB, calcula métricas de chão de fábrica e as expõe num dashboard. É uma aplicação read-only: observa e mede, não controla.

## Problema

Indústrias de pequeno e médio porte geram dados de chão de fábrica continuamente — temperatura, estados de máquina, ciclos — mas esses dados raramente viram informação para decisão. O SynkaCore resolve a coleta: lê sensores e persiste no TimescaleDB com resiliência. O dado persistido, porém, não responde às perguntas da gestão: a máquina está produzindo agora? Quanto do tempo ela rodou? Houve interrupções, quando, por quanto tempo?

Synka Lens preenche essa lacuna. Lê o que o Core gravou, aplica regras de domínio e transformação, e entrega métricas legíveis num dashboard que dispensa conhecimento técnico para interpretar.

## Posição no ecossistema

O ecossistema separa três responsabilidades em três sistemas independentes:

- **SynkaCore** — middleware OT/TI. Coleta de sensores e CLPs, persistência no TimescaleDB. Fonte de dados.
- **SynkaStudio** — operação (MES). Ferramenta do operador: ordens, apontamentos. Produz dados operacionais.
- **Synka Lens** — análise. Lê das fontes, calcula, apresenta. Consome dados; não produz.

Os três são independentes em tempo de execução: nenhum chama o outro diretamente. Comunicam-se por dado compartilhado, lendo das fontes. Se o Lens cai, coleta e operação seguem. A parte crítica (coleta) nunca depende da parte adiável (análise).

## Arquitetura

Monólito modular: processo único, fronteiras internas claras. A dependência aponta para dentro — apresentação depende de transformação, que depende de domínio. O domínio não conhece tecnologia externa.

O dado percorre três camadas:

```
TimescaleDB (fonte, read-only)
      │  extração
      ▼
  bronze    cópia fiel dos dados brutos — ponto de recuperação
      │  limpeza, detecção de gaps, classificação de status
      ▼
  silver    dados confiáveis e enriquecidos
      │  agregação
      ▼
  gold      métricas prontas para consumo
      │  leitura
      ▼
  dashboard apresentação (Streamlit) — exibe, não calcula
```

Detalhes em [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). Decisões e seus custos em [`docs/TRADE-OFFS.md`](docs/TRADE-OFFS.md).

## Stack

| Componente | Tecnologia | Papel |
|---|---|---|
| Linguagem | Python | Orquestração do fluxo |
| Fonte | TimescaleDB (PostgreSQL) | Origem das séries temporais |
| Driver | psycopg 3 | Conexão com a fonte |
| Transformação | DuckDB | Motor SQL das camadas silver e gold |
| Formato intermediário | Parquet | Persistência colunar particionada |
| Apresentação | Streamlit | Dashboard web read-only |
| Pacotes | uv | Ambiente e dependências |

## Execução

Pré-requisitos: Python 3.14, uv, e um TimescaleDB acessível com a tabela `sensor_readings` populada (alimentada pelo SynkaCore).

Instalar dependências:

```bash
uv sync
uv pip install -e .
```

Configurar acesso ao banco em `.env` (ver `src/synka_lens/.env.example`).

Rodar o pipeline (extrai, transforma, calcula):

```bash
uv run python run_pipeline.py
```

Abrir o dashboard:

```bash
./run_dashboard.sh
```

O dashboard sobe um servidor local (porta 8501) acessível pelo navegador, inclusive de outras máquinas na mesma rede.

## Testes

```bash
uv run pytest -v
```

A suíte cobre as regras de domínio, cada camada de transformação, a integração entre camadas (end-to-end) e casos-limite (gaps, múltiplas máquinas, disponibilidade nos extremos, leitura única).

## Estado atual

V1.0: pipeline completo (bronze, silver, gold) e dashboard, para uma máquina e a métrica de disponibilidade. Roadmap das próximas versões em [`docs/ROADMAP.md`](docs/ROADMAP.md). O raciocínio completo da V1.0 está em `docs/contexto (V1.0).md`.

## Autor

Vitor Hugo da Silva