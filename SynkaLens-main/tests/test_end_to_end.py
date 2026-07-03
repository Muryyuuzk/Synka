from datetime import datetime, timedelta, timezone
from pathlib import Path

import duckdb
import pyarrow as pa

from synka_lens.domain.machine_state import StatusThresholds
from synka_lens.transformation.bronze import write_bronze
from synka_lens.transformation.silver import write_silver
from synka_lens.transformation.gold import compute_availability

THRESHOLDS = StatusThresholds(running_above_value=40.0, gap_seconds=30.0)


class _FakeConfig:
    """Config falsa: o e2e nao toca o Timescale real.

    write_bronze chama fetch_all_readings(config), que conecta no banco.
    Para um e2e deterministico, substituimos a fonte por dados sinteticos
    escritos diretamente, contornando a ingestao real (validada a parte).
    """


def _seed_bronze_directly(bronze_path: Path, rows: list[dict]) -> int:
    """Escreve o bronze a partir de dados sinteticos, no mesmo formato
    que write_bronze produziria. Substitui a etapa de ingestao."""
    table = pa.Table.from_pylist(rows)
    connection = duckdb.connect()
    try:
        connection.register("input", table)
        connection.execute(
            f"""
            COPY (SELECT *, CAST(time AS DATE) AS date FROM input)
            TO '{bronze_path}'
            (FORMAT PARQUET, PARTITION_BY (date), OVERWRITE_OR_IGNORE)
            """
        )
    finally:
        connection.close()
    return len(rows)


def test_end_to_end_bronze_silver_gold(tmp_path: Path):
    base = datetime(2026, 6, 8, 12, 0, 0, tzinfo=timezone.utc)
    rows = [
        {"time": base, "tag": "M1", "value": 55.0, "unit": "C"},                       # running, 10s
        {"time": base + timedelta(seconds=10), "tag": "M1", "value": 55.0, "unit": "C"},  # running, 10s
        {"time": base + timedelta(seconds=20), "tag": "M1", "value": 25.0, "unit": "C"},  # stopped, 10s
        {"time": base + timedelta(seconds=30), "tag": "M1", "value": 55.0, "unit": "C"},  # running, 300s (gap)
        {"time": base + timedelta(seconds=330), "tag": "M1", "value": 55.0, "unit": "C"}, # running, 10s
        {"time": base + timedelta(seconds=340), "tag": "M1", "value": 25.0, "unit": "C"}, # ultima, nao conta
    ]

    bronze_path = tmp_path / "bronze" / "sensor_readings"
    silver_path = tmp_path / "silver" / "sensor_readings"
    bronze_path.mkdir(parents=True, exist_ok=True)
    silver_path.mkdir(parents=True, exist_ok=True)

    # Camada bronze (semeada com dados sinteticos, contornando ingestao real)
    bronze_count = _seed_bronze_directly(bronze_path, rows)
    assert bronze_count == 6

    # Camada silver: invariante de preservacao de contagem
    silver_count = write_silver(bronze_path, silver_path, THRESHOLDS)
    assert silver_count == bronze_count  # silver nao perde nem inventa leituras

    # Camada gold: metrica calculada sobre o fluxo completo
    metrics = compute_availability(silver_path, THRESHOLDS)
    assert len(metrics) == 1

    m = metrics[0]
    # running: 10+10+10 = 30s; stopped: 10s; gap: 300s; observed: 40s
    assert m.running_seconds == 30.0
    assert m.stopped_seconds == 10.0
    assert m.gap_seconds == 300.0
    # disponibilidade = 30 / (30+10) = 75%, gap excluido
    assert m.availability_percent == 75.0

    # invariante de coerencia: disponibilidade sempre em [0, 100]
    assert 0.0 <= m.availability_percent <= 100.0
