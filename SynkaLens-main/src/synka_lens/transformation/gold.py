from dataclasses import dataclass
from pathlib import Path

import duckdb

from synka_lens.domain.machine_state import StatusThresholds


@dataclass(frozen=True)
class AvailabilityMetrics:
    tag: str
    running_seconds: float
    stopped_seconds: float
    gap_seconds: float
    availability_percent: float


def compute_availability(
    silver_path: Path,
    thresholds: StatusThresholds,
) -> list[AvailabilityMetrics]:
    connection = duckdb.connect()
    try:
        rows = connection.execute(
            """
            WITH with_duration AS (
                SELECT
                    tag,
                    status,
                    EXTRACT(
                        EPOCH FROM (
                            LEAD(time) OVER (PARTITION BY tag ORDER BY time) - time
                        )
                    ) AS duration_seconds
                FROM read_parquet($silver_glob, hive_partitioning = true)
            ),
            classified_duration AS (
                SELECT
                    tag,
                    CASE
                        WHEN duration_seconds > $gap_seconds THEN duration_seconds
                        ELSE 0
                    END AS gap_seconds,
                    CASE
                        WHEN duration_seconds <= $gap_seconds AND status = 'running' THEN duration_seconds
                        ELSE 0
                    END AS running_seconds,
                    CASE
                        WHEN duration_seconds <= $gap_seconds AND status = 'stopped' THEN duration_seconds
                        ELSE 0
                    END AS stopped_seconds
                FROM with_duration
                WHERE duration_seconds IS NOT NULL
            )
            SELECT
                tag,
                SUM(running_seconds) AS total_running,
                SUM(stopped_seconds) AS total_stopped,
                SUM(gap_seconds) AS total_gap
            FROM classified_duration
            GROUP BY tag
            """,
            {
                "silver_glob": f"{silver_path}/**/*.parquet",
                "gap_seconds": thresholds.gap_seconds,
            },
        ).fetchall()
    finally:
        connection.close()

    metrics = []
    for tag, total_running, total_stopped, total_gap in rows:
        observed = total_running + total_stopped
        availability = (total_running / observed * 100) if observed > 0 else 0.0
        metrics.append(
            AvailabilityMetrics(
                tag=tag,
                running_seconds=total_running,
                stopped_seconds=total_stopped,
                gap_seconds=total_gap,
                availability_percent=availability,
            )
        )

    return metrics
