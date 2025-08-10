from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from pymodbus.client import ModbusTcpClient, ModbusSerialClient
from pymodbus.exceptions import ModbusException


@dataclass
class TcpSettings:
    host: str
    port: int


@dataclass
class RtuSettings:
    port: str
    baudrate: int = 9600
    parity: str = "N"  # 'N', 'E', 'O'
    stopbits: int = 1
    bytesize: int = 8


class ModbusConnection:
    def __init__(self, unit_id: int) -> None:
        self.unit_id = unit_id
        self._tcp_client: Optional[ModbusTcpClient] = None
        self._rtu_client: Optional[ModbusSerialClient] = None

    def connect_tcp(self, settings: TcpSettings) -> bool:
        self.close()
        self._tcp_client = ModbusTcpClient(host=settings.host, port=settings.port, timeout=2.0)
        return bool(self._tcp_client.connect())

    def connect_rtu(self, settings: RtuSettings) -> bool:
        self.close()
        self._rtu_client = ModbusSerialClient(
            method="rtu",
            port=settings.port,
            baudrate=settings.baudrate,
            parity=settings.parity,
            stopbits=settings.stopbits,
            bytesize=settings.bytesize,
            timeout=2.0,
        )
        return bool(self._rtu_client.connect())

    def is_connected(self) -> bool:
        if self._tcp_client is not None:
            return bool(self._tcp_client.connected)
        if self._rtu_client is not None:
            return bool(self._rtu_client.connected)
        return False

    def close(self) -> None:
        try:
            if self._tcp_client is not None:
                self._tcp_client.close()
        finally:
            self._tcp_client = None
        try:
            if self._rtu_client is not None:
                self._rtu_client.close()
        finally:
            self._rtu_client = None

    def read_holding_registers(self, address: int, count: int) -> Tuple[bool, List[int] | str]:
        client = self._get_client_or_raise()
        try:
            response = client.read_holding_registers(address=address, count=count, unit=self.unit_id)
            if response.isError():
                return False, str(response)
            return True, list(response.registers)
        except ModbusException as exc:
            return False, f"Modbus error: {exc}"
        except Exception as exc:  # noqa: BLE001
            return False, f"Unexpected error: {exc}"

    def read_input_registers(self, address: int, count: int) -> Tuple[bool, List[int] | str]:
        client = self._get_client_or_raise()
        try:
            response = client.read_input_registers(address=address, count=count, unit=self.unit_id)
            if response.isError():
                return False, str(response)
            return True, list(response.registers)
        except ModbusException as exc:
            return False, f"Modbus error: {exc}"
        except Exception as exc:  # noqa: BLE001
            return False, f"Unexpected error: {exc}"

    def write_single_register(self, address: int, value: int) -> Tuple[bool, str]:
        client = self._get_client_or_raise()
        try:
            response = client.write_register(address=address, value=value, unit=self.unit_id)
            if response.isError():
                return False, str(response)
            return True, "OK"
        except ModbusException as exc:
            return False, f"Modbus error: {exc}"
        except Exception as exc:  # noqa: BLE001
            return False, f"Unexpected error: {exc}"

    def _get_client_or_raise(self):
        client = self._tcp_client or self._rtu_client
        if client is None:
            raise RuntimeError("Not connected")
        return client