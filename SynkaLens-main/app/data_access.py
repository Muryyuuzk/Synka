from dataclasses import dataclass
from pathlib import Path

import duckdb
import pandas as pd

from synka_lens.domain.machine_state import StatusThresholds
from synka_lens.transformation.gold import AvailabilityMetrics, compute_availability

DATA_DIR = Path("data")
SILVER_DIR = DATA_DIR / "silver" / "sensor_readings"
SILVER_GLOB = str(SILVER_DIR / "**" / "*.parquet")


@dataclass(frozen=True)
class CurrentStatus:
    tag: str
    value: float
    unit: str
    status: str


def load_availability(thresholds: StatusThresholds) -> list[AvailabilityMetrics]:
    return compute_availability(SILVER_DIR, thresholds)


def load_time_series() -> pd.DataFrame:
    connection = duckdb.connect()
    try:
        return connection.execute(
            """
            SELECT time, tag, value, unit, status
            FROM read_parquet($glob, hive_partitioning = true)
            ORDER BY time
            """,
            {"glob": SILVER_GLOB},
        ).df()
    finally:
        connection.close()


def load_latest_readings(limit: int) -> pd.DataFrame:
    connection = duckdb.connect()
    try:
        return connection.execute(
            """
            SELECT time, tag, value, unit, status, is_gap
            FROM read_parquet($glob, hive_partitioning = true)
            ORDER BY time DESC
            LIMIT $limit
            """,
            {"glob": SILVER_GLOB, "limit": limit},
        ).df()
    finally:
        connection.close()


def load_current_status() -> CurrentStatus | None:
    connection = duckdb.connect()
    try:
        row = connection.execute(
            """
            SELECT tag, value, unit, status
            FROM read_parquet($glob, hive_partitioning = true)
            ORDER BY time DESC
            LIMIT 1
            """,
            {"glob": SILVER_GLOB},
        ).fetchone()
    finally:
        connection.close()

    if row is None:
        return None

    return CurrentStatus(tag=row[0], value=float(row[1]), unit=row[2], status=row[3])


def load_time_series_by_minute() -> pd.DataFrame:
    connection = duckdb.connect()
    try:
        return connection.execute(
            """
            SELECT
                time_bucket(INTERVAL '1 minute', time) AS minute,
                avg(value) AS avg_value
            FROM read_parquet($glob, hive_partitioning = true)
            GROUP BY minute
            ORDER BY minute
            """,
            {"glob": SILVER_GLOB},
        ).df()
    finally:
        connection.close()
