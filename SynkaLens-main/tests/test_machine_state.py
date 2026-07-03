from synka_lens.domain.machine_state import (
    MachineStatus,
    StatusThresholds,
    classify_status,
    is_connection_gap,
)

THRESHOLDS = StatusThresholds(running_above_value=40.0, gap_seconds=30.0)


def test_value_above_threshold_is_running():
    assert classify_status(55.0, THRESHOLDS) == MachineStatus.RUNNING


def test_value_below_threshold_is_stopped():
    assert classify_status(24.0, THRESHOLDS) == MachineStatus.STOPPED


def test_value_exactly_at_threshold_is_stopped():
    assert classify_status(40.0, THRESHOLDS) == MachineStatus.STOPPED


def test_interval_above_gap_threshold_is_gap():
    assert is_connection_gap(299.0, THRESHOLDS) is True


def test_interval_below_gap_threshold_is_not_gap():
    assert is_connection_gap(13.0, THRESHOLDS) is False


def test_interval_exactly_at_gap_threshold_is_not_gap():
    assert is_connection_gap(30.0, THRESHOLDS) is False
