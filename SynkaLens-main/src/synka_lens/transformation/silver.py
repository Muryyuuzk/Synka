from pathlib import Path

import duckdb

from synka_lens.domain.machine_state import StatusThresholds


def write_silver(
    bronze_path: Path,
    silver_path: Path,
    thresholds: StatusThresholds,
) -> int:
    connection = duckdb.connect()
    try:
        connection.execute(
            """
            COPY (
                WITH ordered_readings AS (
                    SELECT
                        time,
                        tag,
                        value,
                        unit,
                        LAG(time) OVER (PARTITION BY tag ORDER BY time) AS previous_time
                    FROM read_parquet($bronze_glob, hive_partitioning = true)
                ),
                with_interval AS (
                    SELECT
                        time,
                        tag,
                        value,
                        unit,
                        EXTRACT(EPOCH FROM (time - previous_time)) AS interval_seconds
                    FROM ordered_readings
                )
                SELECT
                    time,
                    tag,
                    value,
                    unit,
                    interval_seconds,
                    COALESCE(interval_seconds > $gap_seconds, FALSE) AS is_gap,
                    CASE
                        WHEN value > $running_above THEN 'running'
                        ELSE 'stopped'
                    END AS status,
                    CAST(time AS DATE) AS date
                FROM with_interval
            )
            TO $silver_dest
            (FORMAT PARQUET, PARTITION_BY (date), OVERWRITE_OR_IGNORE)
            """,
            {
                "bronze_glob": f"{bronze_path}/**/*.parquet",
                "gap_seconds": thresholds.gap_seconds,
                "running_above": thresholds.running_above_value,
                "silver_dest": str(silver_path),
            },
        )

        count = connection.execute(
            "SELECT count(*) FROM read_parquet($glob, hive_partitioning = true)",
            {"glob": f"{silver_path}/**/*.parquet"},
        ).fetchone()[0]
    finally:
        connection.close()

    return count
