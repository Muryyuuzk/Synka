from dataclasses import dataclass
from datetime import datetime

import psycopg

from synka_lens.config import DatabaseConfig


@dataclass(frozen=True)
class SensorReading:
    time: datetime
    tag: str
    value: float
    unit: str


def check_connection(config: DatabaseConfig) -> bool:
    with psycopg.connect(config.connection_string()) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            return cursor.fetchone() == (1,)


def fetch_all_readings(config: DatabaseConfig) -> list[SensorReading]:
    query = """
        SELECT time, tag, value, unit
        FROM sensor_readings
        ORDER BY time ASC
    """
    with psycopg.connect(config.connection_string()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()

    return [
        SensorReading(time=row[0], tag=row[1], value=float(row[2]), unit=row[3])
        for row in rows
    ]