# Instruções de Execução — Synka Lens V1.0

Passo a passo para rodar o Synka Lens V1.0 do zero, do ambiente ao dashboard. Cada versão tem seu próprio arquivo de instruções, pois os passos mudam entre versões.

## Pré-requisitos

- Python 3.14
- uv (gerenciador de pacotes)
- Docker (para o TimescaleDB)
- O SynkaCore disponível para popular o banco com leituras reais (ou dados já presentes no TimescaleDB)

## 1. Subir o TimescaleDB

O Synka Lens lê de um TimescaleDB. Suba o banco com um volume nomeado para que os dados persistam entre reinicializações do container:

```bash
docker run -d \
  --name synkacore-timescaledb \
  -e POSTGRES_PASSWORD=synkacore \
  -e POSTGRES_DB=synkacore \
  -p 5432:5432 \
  -v synkacore_pgdata:/var/lib/postgresql/data \
  timescale/timescaledb:latest-pg17
```

Confirmar que subiu:

```bash
docker ps
```

Se o container já existe de uma execução anterior, basta iniciá-lo:

```bash
docker start synkacore-timescaledb
```

## 2. Criar o schema

Criar a extensão, a tabela de leituras e o hypertable:

```bash
docker exec synkacore-timescaledb psql -U postgres -d synkacore \
  -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"

docker exec synkacore-timescaledb psql -U postgres -d synkacore -c "
CREATE TABLE IF NOT EXISTS sensor_readings (
    time  TIMESTAMPTZ  NOT NULL,
    tag   TEXT         NOT NULL,
    value NUMERIC      NOT NULL,
    unit  TEXT         NOT NULL
);"

docker exec synkacore-timescaledb psql -U postgres -d synkacore \
  -c "SELECT create_hypertable('sensor_readings', by_range('time'));"
```

## 3. Popular o banco

Rodar o SynkaCore Collector (a partir do diretório do SynkaCore) para gerar leituras:

```bash
cd ~/SynkaCore
dotnet run --project SynkaCore.Collector
```

Deixar rodar por alguns minutos. Para gerar gaps de conexão (úteis para ver a detecção de gap no Lens), parar e religar o banco durante a coleta:

```bash
docker stop synkacore-timescaledb    # interrompe a coleta
docker start synkacore-timescaledb   # retoma
```

Confirmar que há dados:

```bash
docker exec synkacore-timescaledb psql -U postgres -d synkacore \
  -c "SELECT count(*) FROM sensor_readings;"
```

## 4. Preparar o Synka Lens

A partir do diretório do projeto:

```bash
cd ~/SynkaLens
uv sync
uv pip install -e .
```

Criar o `.env` com o acesso ao banco (a partir do exemplo):

```bash
cp src/synka_lens/.env.example .env
```

O `.env.example` já vem com os valores que correspondem ao container acima (`localhost:5432`, banco `synkacore`, usuário `postgres`).

## 5. Rodar o pipeline

Executa as três camadas (bronze → silver → gold) sobre os dados reais e grava os Parquets em `data/`:

```bash
uv run python run_pipeline.py
```

A saída mostra a contagem de cada camada e a disponibilidade calculada por máquina.

## 6. Abrir o dashboard

```bash
./run_dashboard.sh
```

O Streamlit sobe um servidor local na porta 8501 e abre no navegador. O endereço também é acessível de outras máquinas na mesma rede (mostrado no terminal como `Network URL`).

O dashboard lê o resultado mais recente gerado pelo pipeline. Para atualizar os dados exibidos, rodar o pipeline novamente (passo 5) e recarregar a página.

## Rodar os testes

```bash
uv run pytest -v
```

## Ordem resumida

```bash
docker start synkacore-timescaledb     # 1. banco no ar
uv run python run_pipeline.py          # 2. processa os dados
./run_dashboard.sh                     # 3. abre o dashboard
```

(Assumindo schema já criado e banco já populado de uma execução anterior.)