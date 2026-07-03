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


def test_availability_excludes_gap_time(tmp_path: Path):
    base = datetime(2026, 6, 8, 12, 0, 0, tzinfo=timezone.utc)
    # leitura 1 (running) dura 10s ate a leitura 2
    # leitura 2 (stopped) dura 10s ate a leitura 3
    # leitura 3 (running) dura 300s (gap) ate a leitura 4
    # leitura 4 (running) -> ultima, LEAD nulo, nao conta
    rows = [
        {"time": base, "tag": "M1", "value": 55.0, "unit": "C"},
        {"time": base + timedelta(seconds=10), "tag": "M1", "value": 25.0, "unit": "C"},
        {"time": base + timedelta(seconds=20), "tag": "M1", "value": 55.0, "unit": "C"},
        {"time": base + timedelta(seconds=320), "tag": "M1", "value": 55.0, "unit": "C"},
    ]
    bronze_path = tmp_path / "bronze"
    silver_path = tmp_path / "silver"
    _write_synthetic_bronze(bronze_path, rows)
    write_silver(bronze_path, silver_path, THRESHOLDS)

    metrics = compute_availability(silver_path, THRESHOLDS)

    assert len(metrics) == 1
    m = metrics[0]
    assert m.tag == "M1"
    # running: 10s (leitura 1). stopped: 10s (leitura 2).
    # leitura 3 dura 300s mas e gap -> vai para gap, nao para running
    assert m.running_seconds == 10.0
    assert m.stopped_seconds == 10.0
    assert m.gap_seconds == 300.0
    # disponibilidade = 10 / (10+10) = 50%, gap excluido
    assert m.availability_percent == 50.0
