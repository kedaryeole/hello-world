from __future__ import annotations

from typing import List, Optional

from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException


class ModbusClientRTU:
    """Thin wrapper around pymodbus ModbusSerialClient for RTU.

    Keeps connection state and exposes typed methods for common ops used by the GUI.
    """

    def __init__(self) -> None:
        self._client: Optional[ModbusSerialClient] = None
        self._unit_id: int = 1

    @property
    def is_connected(self) -> bool:
        return bool(self._client and self._client.connected)

    def connect(self, port: str, baudrate: int, unit_id: int) -> bool:
        self.close()
        self._unit_id = unit_id
        self._client = ModbusSerialClient(
            method="rtu",
            port=port,
            baudrate=baudrate,
            timeout=1.0,
            parity="N",
            stopbits=1,
            bytesize=8,
        )
        return bool(self._client.connect())

    def close(self) -> None:
        if self._client:
            try:
                self._client.close()
            finally:
                self._client = None

    def read_holding_registers(self, address: int, count: int) -> List[int]:
        if not self._client:
            raise RuntimeError("Client is not connected")
        try:
            response = self._client.read_holding_registers(address=address, count=count, unit=self._unit_id)
            if response.isError():  # type: ignore[attr-defined]
                raise ModbusException(str(response))
            return list(response.registers)
        except Exception as exc:  # noqa: BLE001
            raise ModbusException(str(exc))

    def write_single_register(self, address: int, value: int) -> None:
        if not self._client:
            raise RuntimeError("Client is not connected")
        try:
            response = self._client.write_register(address=address, value=value, unit=self._unit_id)
            if response.isError():  # type: ignore[attr-defined]
                raise ModbusException(str(response))
        except Exception as exc:  # noqa: BLE001
            raise ModbusException(str(exc))