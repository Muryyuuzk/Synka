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


def test_partition_isolates_machines(tmp_path: Path):
    base = datetime(2026, 6, 8, 12, 0, 0, tzinfo=timezone.utc)

    # Timestamps de M1 e M2 INTERCALADOS no tempo de proposito:
    # se PARTITION BY tag falhar, o LEAD de M1 pegaria uma leitura de M2.
    # M1: sempre running (100% esperado)
    # M2: alterna running/stopped (50% esperado)
    rows = [
        # t=0
        {"time": base, "tag": "M1", "value": 55.0, "unit": "C"},
        {"time": base + timedelta(seconds=1), "tag": "M2", "value": 55.0, "unit": "C"},
        # t=10
        {"time": base + timedelta(seconds=10), "tag": "M1", "value": 55.0, "unit": "C"},
        {"time": base + timedelta(seconds=11), "tag": "M2", "value": 25.0, "unit": "C"},
        # t=20
        {"time": base + timedelta(seconds=20), "tag": "M1", "value": 55.0, "unit": "C"},
        {"time": base + timedelta(seconds=21), "tag": "M2", "value": 55.0, "unit": "C"},
        # t=30 (fecha as sequencias; ultimas leituras nao contam por LEAD nulo)
        {"time": base + timedelta(seconds=30), "tag": "M1", "value": 55.0, "unit": "C"},
        {"time": base + timedelta(seconds=31), "tag": "M2", "value": 25.0, "unit": "C"},
    ]
    bronze_path = tmp_path / "bronze"
    silver_path = tmp_path / "silver"
    _write_synthetic_bronze(bronze_path, rows)
    write_silver(bronze_path, silver_path, THRESHOLDS)

    metrics = compute_availability(silver_path, THRESHOLDS)

    # duas maquinas, duas linhas de metrica
    assert len(metrics) == 2

    by_tag = {m.tag: m for m in metrics}
    assert "M1" in by_tag
    assert "M2" in by_tag

    # M1: 3 intervalos de 10s, todos running -> 100%
    assert by_tag["M1"].availability_percent == 100.0
    assert by_tag["M1"].gap_seconds == 0.0

    # M2: running(10s) -> stopped(10s) -> running(10s) -> [ultima, nao conta]
    # running total = 20s, stopped = 10s -> 20/30 = 66.66...%
    assert abs(by_tag["M2"].availability_percent - (20.0 / 30.0 * 100)) < 0.001
    assert by_tag["M2"].gap_seconds == 0.0
