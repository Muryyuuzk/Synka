from dataclasses import dataclass
from enum import Enum


class MachineStatus(Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    NO_DATA = "no_data"


@dataclass(frozen=True)
class StatusThresholds:
    running_above_value: float
    gap_seconds: float


def classify_status(value: float, thresholds: StatusThresholds) -> MachineStatus:
    if value > thresholds.running_above_value:
        return MachineStatus.RUNNING
    return MachineStatus.STOPPED


def is_connection_gap(interval_seconds: float, thresholds: StatusThresholds) -> bool:
    return interval_seconds > thresholds.gap_seconds
