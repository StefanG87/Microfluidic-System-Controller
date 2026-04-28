"""Qt-free time base used by the v3 measurement sampler."""

from __future__ import annotations

import time


class V3Timebase:
    """Provide absolute and relative timestamps for one measurement run."""

    def __init__(self):
        self.sampling_interval_ms = 250
        self.start_timestamp = None
        self._t0_epoch = None
        self._t0_mono = None

    def set_sampling_interval_ms(self, interval_ms: int) -> None:
        """Store the active sampling interval in milliseconds."""
        self.sampling_interval_ms = max(1, int(interval_ms))

    def reset_time(self) -> None:
        """Reset the shared time base for a new measurement run."""
        self._t0_epoch = time.time()
        self._t0_mono = time.monotonic()
        self.start_timestamp = self._t0_epoch

    def get_timestamps(self):
        """Return `(absolute_epoch_seconds, relative_seconds)` from one monotonic delta."""
        if self._t0_epoch is None or self._t0_mono is None:
            self.reset_time()
        rel = time.monotonic() - self._t0_mono
        return self._t0_epoch + rel, rel
