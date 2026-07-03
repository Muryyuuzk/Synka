from pathlib import Path

import duckdb

from synka_lens.config import load_database_config
from synka_lens.transformation.bronze import write_bronze


def test_bronze_writes_parquet_with_all_readings(tmp_path: Path):
    config = load_database_config()
    bronze_path = tmp_path / "sensor_readings"

    count = write_bronze(config, bronze_path)

    files = list(bronze_path.glob("**/*.parquet"))
    assert len(files) > 0

    result = duckdb.sql(
        f"SELECT count(*) FROM read_parquet('{bronze_path}/**/*.parquet', hive_partitioning=true)"
    ).fetchone()
    assert result[0] == count
