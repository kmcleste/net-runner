"""ML risk scorer using numpy rolling Z-score anomaly detection.

Operates on DeviceSnapshot metric history — no dependency on any IT source.
"""
from __future__ import annotations

import logging
from collections import defaultdict, deque

import numpy as np

from .schema import DeviceSnapshot, NetworkState

logger = logging.getLogger(__name__)

WINDOW = 40          # rolling buffer size (ticks)
BROADCAST_EVERY = 8  # broadcast scores every N ticks


class MLRiskScorer:
    def __init__(self) -> None:
        # device_id → deque of (cpu, memory, error_rate) tuples
        self._history: dict[str, deque[tuple[float, float, float]]] = defaultdict(
            lambda: deque(maxlen=WINDOW)
        )

    def update(self, state: NetworkState) -> None:
        for device in state.devices.values():
            m = device.metrics
            self._history[device.id].append(
                (m.cpu_utilization, m.memory_utilization, m.error_rate)
            )

    def score_all(self, state: NetworkState) -> dict[str, int]:
        return {device.id: self._score(device) for device in state.devices.values()}

    def _score(self, device: DeviceSnapshot) -> int:
        score = 0.0

        state_pts = {
            "healthy": 0, "recovering": 15, "maintenance": 5,
            "rebooting": 20, "degraded": 35, "unreachable": 55, "failed": 70,
        }
        score += state_pts.get(device.state, 0)
        score += min(15.0, device.age_years * 1.5)
        score += min(25.0, device.failure_count_24h * 8.0)
        if device.is_consumer_grade:
            score += 10

        history = self._history.get(device.id)
        if history and len(history) >= 5:
            arr = np.array(history, dtype=float)
            means = arr.mean(axis=0)
            stds = arr.std(axis=0) + 1e-6
            z = np.abs((arr[-1] - means) / stds)
            score += float(min(15.0, z.max() * 5.0))

        return min(100, int(round(score)))
