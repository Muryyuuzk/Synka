import pandas as pd

from synka_lens.domain.machine_state import StatusThresholds
from app.data_access import (
    CurrentStatus,
    load_availability,
    load_current_status,
    load_latest_readings,
    load_time_series_by_minute,
)

THRESHOLDS = StatusThresholds(running_above_value=40.0, gap_seconds=30.0)


def test_load_current_status_returns_valid_status():
    status = load_current_status()
    assert status is not None
    assert isinstance(status, CurrentStatus)
    assert status.status in ("running", "stopped")
    assert status.tag != ""


def test_load_availability_returns_metrics():
    metrics = load_availability(THRESHOLDS)
    assert len(metrics) >= 1
    m = metrics[0]
    assert 0.0 <= m.availability_percent <= 100.0
    assert m.running_seconds >= 0
    assert m.gap_seconds >= 0


def test_load_latest_readings_respects_limit():
    df = load_latest_readings(5)
    assert isinstance(df, pd.DataFrame)
    assert len(df) <= 5
    assert "status" in df.columns
    assert "is_gap" in df.columns


def test_time_series_by_minute_is_aggregated():
    df = load_time_series_by_minute()
    assert isinstance(df, pd.DataFrame)
    assert "minute" in df.columns
    assert "avg_value" in df.columns
    # agregacao por minuto deve ter MENOS linhas que leituras brutas (488)
    assert len(df) < 488
    assert len(df) > 0
