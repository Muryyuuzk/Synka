from datetime import datetime, timedelta, timezone
from pathlib import Path

import duckdb
import pyarrow as pa

from synka_lens.domain.machine_state import StatusThresholds
from synka_lens.transformation.gold import compute_availability
from synka_lens.transformation.silver import write_silver

THRESHOLDS = StatusThresholds(running_above_value=40.0, gap_seconds=30.0)


def _write_synthetic_bronze(bronze_path: Path, rows: list[dict]) -> None:
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


def test_only_gaps_results_in_zero_observed_no_crash(tmp_path: Path):
    # Duas leituras separadas por 300s (> limiar de gap 30s).
    # O unico intervalo e gap -> observed = 0 -> exercita o ramo `else 0.0`
    # (divisao por zero evitada). Disponibilidade honesta: 0%.
    base = datetime(2026, 6, 8, 12, 0, 0, tzinfo=timezone.utc)
    rows = [
        {"time": base, "tag": "M1", "value": 55.0, "unit": "C"},
        {"time": base + timedelta(seconds=300), "tag": "M1", "value": 55.0, "unit": "C"},
    ]
    bronze_path = tmp_path / "bronze"
    silver_path = tmp_path / "silver"
    _write_synthetic_bronze(bronze_path, rows)
    write_silver(bronze_path, silver_path, THRESHOLDS)

    metrics = compute_availability(silver_path, THRESHOLDS)

    assert len(metrics) == 1
    m = metrics[0]
    assert m.running_seconds == 0.0
    assert m.stopped_seconds == 0.0
    assert m.gap_seconds == 300.0
    assert m.availability_percent == 0.0  # ramo else, sem divisao por zero


def test_always_stopped_gives_zero_percent_through_division(tmp_path: Path):
    # Maquina sempre parada, mas observada (intervalos curtos, sem gap).
    # observed > 0 (stopped), running = 0 -> 0/observed = 0% via DIVISAO real.
    # Caminho diferente do teste acima (que cai no else).
    base = datetime(2026, 6, 8, 12, 0, 0, tzinfo=timezone.utc)
    rows = [
        {"time": base, "tag": "M1", "value": 25.0, "unit": "C"},
        {"time": base + timedelta(seconds=10), "tag": "M1", "value": 25.0, "unit": "C"},
        {"time": base + timedelta(seconds=20), "tag": "M1", "value": 25.0, "unit": "C"},
    ]
    bronze_path = tmp_path / "bronze"
    silver_path = tmp_path / "silver"
    _write_synthetic_bronze(bronze_path, rows)
    write_silver(bronze_path, silver_path, THRESHOLDS)

    metrics = compute_availability(silver_path, THRESHOLDS)

    assert len(metrics) == 1
    m = metrics[0]
    assert m.running_seconds == 0.0
    assert m.stopped_seconds == 20.0  # 2 intervalos de 10s
    assert m.gap_seconds == 0.0
    assert m.availability_percent == 0.0  # divisao 0/20 = 0%


def test_single_reading_produces_no_interval(tmp_path: Path):
    # Uma unica leitura: LAG e LEAD nulos, nenhum intervalo gerado.
    # Fronteira minima de dados. Nao deve quebrar; observed = 0.
    base = datetime(2026, 6, 8, 12, 0, 0, tzinfo=timezone.utc)
    rows = [
        {"time": base, "tag": "M1", "value": 55.0, "unit": "C"},
    ]
    bronze_path = tmp_path / "bronze"
    silver_path = tmp_path / "silver"
    _write_synthetic_bronze(bronze_path, rows)
    write_silver(bronze_path, silver_path, THRESHOLDS)

    metrics = compute_availability(silver_path, THRESHOLDS)

    # Sem intervalo nenhum: ou nao ha linha de metrica, ou ha uma com tudo zero.
    if metrics:
        m = metrics[0]
        assert m.running_seconds == 0.0
        assert m.stopped_seconds == 0.0
        assert m.availability_percent == 0.0
