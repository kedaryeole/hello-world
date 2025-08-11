from __future__ import annotations

import time
from typing import Dict, List

from PySide6.QtCore import QObject, QThread, Signal

from .modbus_client import ModbusClientRTU


class PollResult(QObject):
    registers: Dict[int, int]


class ModbusPoller(QThread):
    poll_update = Signal(dict)  # {address: value}
    poll_error = Signal(str)

    def __init__(
        self,
        client: ModbusClientRTU,
        start_address: int,
        count: int,
        interval_ms: int = 250,
    ) -> None:
        super().__init__()
        self._client = client
        self._start = start_address
        self._count = count
        self._interval_ms = max(50, interval_ms)
        self._running = True

    def update_range(self, start_address: int, count: int) -> None:
        self._start = start_address
        self._count = count

    def stop(self) -> None:
        self._running = False

    def run(self) -> None:  # noqa: D401
        while self._running:
            try:
                if self._client.is_connected:
                    values: List[int] = self._client.read_holding_registers(self._start, self._count)
                    payload = {self._start + i: v for i, v in enumerate(values)}
                    self.poll_update.emit(payload)
                else:
                    self.poll_error.emit("Not connected")
            except Exception as exc:  # noqa: BLE001
                self.poll_error.emit(str(exc))
            time.sleep(self._interval_ms / 1000.0)