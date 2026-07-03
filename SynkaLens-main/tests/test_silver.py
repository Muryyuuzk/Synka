from datetime import datetime, timedelta, timezone
from pathlib import Path

import duckdb
import pyarrow as pa

from synka_lens.domain.machine_state import StatusThresholds
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


def _read_silver_ordered(silver_path: Path) -> list[tuple]:
    connection = duckdb.connect()
    try:
        result = connection.execute(
            f"""
            SELECT value, is_gap, status
            FROM read_parquet('{silver_path}/**/*.parquet', hive_partitioning = true)
            ORDER BY time
            """
        ).fetchall()
    finally:
        connection.close()
    return result


def test_silver_classifies_status_and_detects_gap(tmp_path: Path):
    base = datetime(2026, 6, 8, 12, 0, 0, tzinfo=timezone.utc)
    rows = [
        {"time": base, "tag": "M1", "value": 25.0, "unit": "C"},
        {"time": base + timedelta(seconds=2), "tag": "M1", "value": 55.0, "unit": "C"},
        {"time": base + timedelta(seconds=302), "tag": "M1", "value": 30.0, "unit": "C"},
    ]
    bronze_path = tmp_path / "bronze"
    silver_path = tmp_path / "silver"
    _write_synthetic_bronze(bronze_path, rows)

    count = write_silver(bronze_path, silver_path, THRESHOLDS)

    assert count == 3
    result = _read_silver_ordered(silver_path)

    # linha 1: 25C -> stopped; primeira leitura, sem intervalo -> nao e gap
    assert result[0][1] is False
    assert result[0][2] == "stopped"
    # linha 2: 55C -> running; intervalo 2s -> nao e gap
    assert result[1][1] is False
    assert result[1][2] == "running"
    # linha 3: 30C -> stopped; intervalo 300s -> e gap
    assert result[2][1] is True
    assert result[2][2] == "stopped"
