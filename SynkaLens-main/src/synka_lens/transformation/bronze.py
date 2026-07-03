from pathlib import Path

import duckdb
import pyarrow as pa

from synka_lens.config import DatabaseConfig
from synka_lens.ingestion.timescale_source import fetch_all_readings


def write_bronze(config: DatabaseConfig, bronze_path: Path) -> int:
    readings = fetch_all_readings(config)

    if not readings:
        return 0

    table = pa.Table.from_pylist(
        [
            {
                "time": reading.time,
                "tag": reading.tag,
                "value": reading.value,
                "unit": reading.unit,
            }
            for reading in readings
        ]
    )

    connection = duckdb.connect()
    try:
        connection.register("readings_input", table)
        connection.execute(
            """
            COPY (
                SELECT
                    time,
                    tag,
                    value,
                    unit,
                    CAST(time AS DATE) AS date
                FROM readings_input
            )
            TO ?
            (FORMAT PARQUET, PARTITION_BY (date), OVERWRITE_OR_IGNORE)
            """,
            [str(bronze_path)],
        )
    finally:
        connection.close()

    return len(readings)
