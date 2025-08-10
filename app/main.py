from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from typing import List, Optional

from PySide6 import QtCore, QtGui, QtWidgets
from serial.tools import list_ports

from .modbus_client import ModbusConnection, RtuSettings, TcpSettings
from .waveform_plot import WaveformPlot


@dataclass
class PollConfig:
    function: str  # 'holding' or 'input'
    start_address: int
    count: int
    interval_ms: int


class PollWorker(QtCore.QObject):
    data_ready = QtCore.Signal(list)
    error = QtCore.Signal(str)

    def __init__(self, connection: ModbusConnection, config: PollConfig) -> None:
        super().__init__()
        self._connection = connection
        self._config = config
        self._running = False

    @QtCore.Slot()
    def start(self) -> None:
        self._running = True
        next_time = time.monotonic()
        while self._running:
            if not self._connection.is_connected():
                self.error.emit("Disconnected")
                break
            ok: bool
            result: List[int] | str
            if self._config.function == "holding":
                ok, result = self._connection.read_holding_registers(
                    address=self._config.start_address, count=self._config.count
                )
            else:
                ok, result = self._connection.read_input_registers(
                    address=self._config.start_address, count=self._config.count
                )
            if ok:
                values = result  # type: ignore[assignment]
                self.data_ready.emit([float(v) for v in values])
            else:
                self.error.emit(str(result))

            next_time += self._config.interval_ms / 1000.0
            sleep_for = max(0.0, next_time - time.monotonic())
            if sleep_for > 0:
                time.sleep(sleep_for)

    @QtCore.Slot()
    def stop(self) -> None:
        self._running = False


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Modbus GUI with Waveform Display")
        self.resize(1100, 700)

        self._connection: Optional[ModbusConnection] = None

        self._create_ui()
        self._connect_signals()
        self._refresh_serial_ports()

        self._poll_thread: Optional[QtCore.QThread] = None
        self._poll_worker: Optional[PollWorker] = None

    def _create_ui(self) -> None:
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)

        # Connection group
        conn_group = QtWidgets.QGroupBox("Connection")
        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItems(["TCP", "RTU"])

        self.unit_spin = QtWidgets.QSpinBox()
        self.unit_spin.setRange(0, 247)
        self.unit_spin.setValue(1)

        # TCP controls
        self.tcp_host = QtWidgets.QLineEdit("127.0.0.1")
        self.tcp_port = QtWidgets.QSpinBox()
        self.tcp_port.setRange(1, 65535)
        self.tcp_port.setValue(502)

        # RTU controls
        self.rtu_port = QtWidgets.QComboBox()
        self.rtu_baud = QtWidgets.QComboBox()
        self.rtu_baud.addItems(["9600", "19200", "38400", "57600", "115200"])
        self.rtu_parity = QtWidgets.QComboBox()
        self.rtu_parity.addItems(["N", "E", "O"])  # None, Even, Odd
        self.rtu_stopbits = QtWidgets.QComboBox()
        self.rtu_stopbits.addItems(["1", "2"])
        self.rtu_bytesize = QtWidgets.QComboBox()
        self.rtu_bytesize.addItems(["7", "8"])

        self.connect_btn = QtWidgets.QPushButton("Connect")
        self.disconnect_btn = QtWidgets.QPushButton("Disconnect")
        self.disconnect_btn.setEnabled(False)

        conn_form = QtWidgets.QFormLayout()
        conn_form.addRow("Mode", self.mode_combo)
        conn_form.addRow("Unit ID", self.unit_spin)
        conn_form.addRow("TCP Host", self.tcp_host)
        conn_form.addRow("TCP Port", self.tcp_port)
        conn_form.addRow("RTU Port", self.rtu_port)
        conn_form.addRow("RTU Baud", self.rtu_baud)
        conn_form.addRow("RTU Parity", self.rtu_parity)
        conn_form.addRow("RTU Stop Bits", self.rtu_stopbits)
        conn_form.addRow("RTU Byte Size", self.rtu_bytesize)

        conn_btns = QtWidgets.QHBoxLayout()
        conn_btns.addWidget(self.connect_btn)
        conn_btns.addWidget(self.disconnect_btn)

        conn_v = QtWidgets.QVBoxLayout()
        conn_v.addLayout(conn_form)
        conn_v.addLayout(conn_btns)
        conn_group.setLayout(conn_v)

        # Polling group
        poll_group = QtWidgets.QGroupBox("Polling")
        self.function_combo = QtWidgets.QComboBox()
        self.function_combo.addItems(["Holding Registers", "Input Registers"])  # FC3, FC4

        self.start_address = QtWidgets.QSpinBox()
        self.start_address.setRange(0, 65535)
        self.start_address.setValue(0)

        self.count_spin = QtWidgets.QSpinBox()
        self.count_spin.setRange(1, 32)
        self.count_spin.setValue(4)

        self.interval_spin = QtWidgets.QSpinBox()
        self.interval_spin.setRange(10, 10000)
        self.interval_spin.setValue(200)
        self.interval_spin.setSuffix(" ms")

        self.start_poll_btn = QtWidgets.QPushButton("Start Polling")
        self.stop_poll_btn = QtWidgets.QPushButton("Stop Polling")
        self.stop_poll_btn.setEnabled(False)

        poll_form = QtWidgets.QFormLayout()
        poll_form.addRow("Function", self.function_combo)
        poll_form.addRow("Start Address", self.start_address)
        poll_form.addRow("Count", self.count_spin)
        poll_form.addRow("Interval", self.interval_spin)

        poll_btns = QtWidgets.QHBoxLayout()
        poll_btns.addWidget(self.start_poll_btn)
        poll_btns.addWidget(self.stop_poll_btn)

        poll_v = QtWidgets.QVBoxLayout()
        poll_v.addLayout(poll_form)
        poll_v.addLayout(poll_btns)
        poll_group.setLayout(poll_v)

        # Write group
        write_group = QtWidgets.QGroupBox("Write Single Register (FC 6)")
        self.write_address = QtWidgets.QSpinBox()
        self.write_address.setRange(0, 65535)
        self.write_value = QtWidgets.QSpinBox()
        self.write_value.setRange(0, 65535)
        self.write_btn = QtWidgets.QPushButton("Write")
        write_form = QtWidgets.QFormLayout()
        write_form.addRow("Address", self.write_address)
        write_form.addRow("Value", self.write_value)
        write_form.addRow(self.write_btn)
        write_group.setLayout(write_form)

        # Plot
        self.plot = WaveformPlot(max_points=2000)

        # Layout composition
        left_v = QtWidgets.QVBoxLayout()
        left_v.addWidget(conn_group)
        left_v.addWidget(poll_group)
        left_v.addWidget(write_group)
        left_v.addStretch()

        left = QtWidgets.QWidget()
        left.setLayout(left_v)

        splitter = QtWidgets.QSplitter()
        splitter.setOrientation(QtCore.Qt.Orientation.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(self.plot)
        splitter.setStretchFactor(1, 1)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(splitter)
        central.setLayout(layout)

        self._update_conn_controls()

    def _connect_signals(self) -> None:
        self.mode_combo.currentIndexChanged.connect(self._update_conn_controls)
        self.connect_btn.clicked.connect(self._on_connect)
        self.disconnect_btn.clicked.connect(self._on_disconnect)
        self.start_poll_btn.clicked.connect(self._on_start_polling)
        self.stop_poll_btn.clicked.connect(self._on_stop_polling)
        self.write_btn.clicked.connect(self._on_write)

    def _refresh_serial_ports(self) -> None:
        self.rtu_port.clear()
        ports = list_ports.comports()
        if ports:
            for p in ports:
                self.rtu_port.addItem(p.device)
        else:
            # Fallback placeholder
            self.rtu_port.addItem("COM1")

    def _update_conn_controls(self) -> None:
        is_tcp = self.mode_combo.currentText() == "TCP"
        self.tcp_host.setEnabled(is_tcp)
        self.tcp_port.setEnabled(is_tcp)
        self.rtu_port.setEnabled(not is_tcp)
        self.rtu_baud.setEnabled(not is_tcp)
        self.rtu_parity.setEnabled(not is_tcp)
        self.rtu_stopbits.setEnabled(not is_tcp)
        self.rtu_bytesize.setEnabled(not is_tcp)

    def _on_connect(self) -> None:
        unit_id = int(self.unit_spin.value())
        self._connection = ModbusConnection(unit_id=unit_id)
        if self.mode_combo.currentText() == "TCP":
            ok = self._connection.connect_tcp(
                TcpSettings(host=self.tcp_host.text().strip(), port=int(self.tcp_port.value()))
            )
        else:
            ok = self._connection.connect_rtu(
                RtuSettings(
                    port=self.rtu_port.currentText(),
                    baudrate=int(self.rtu_baud.currentText()),
                    parity=self.rtu_parity.currentText(),
                    stopbits=int(self.rtu_stopbits.currentText()),
                    bytesize=int(self.rtu_bytesize.currentText()),
                )
            )
        if ok:
            self.statusBar().showMessage("Connected")
            self.connect_btn.setEnabled(False)
            self.disconnect_btn.setEnabled(True)
        else:
            self._connection = None
            QtWidgets.QMessageBox.critical(self, "Connection Failed", "Unable to establish connection.")

    def _on_disconnect(self) -> None:
        self._stop_polling_if_running()
        if self._connection is not None:
            self._connection.close()
            self._connection = None
        self.connect_btn.setEnabled(True)
        self.disconnect_btn.setEnabled(False)
        self.statusBar().showMessage("Disconnected")

    def _on_start_polling(self) -> None:
        if self._connection is None or not self._connection.is_connected():
            QtWidgets.QMessageBox.warning(self, "Not Connected", "Please connect first.")
            return
        function = "holding" if self.function_combo.currentIndex() == 0 else "input"
        config = PollConfig(
            function=function,
            start_address=int(self.start_address.value()),
            count=int(self.count_spin.value()),
            interval_ms=int(self.interval_spin.value()),
        )
        self.plot.clear_all()

        self._poll_thread = QtCore.QThread(self)
        self._poll_worker = PollWorker(self._connection, config)
        self._poll_worker.moveToThread(self._poll_thread)
        self._poll_thread.started.connect(self._poll_worker.start)
        self._poll_worker.data_ready.connect(self._on_data_ready)
        self._poll_worker.error.connect(self._on_poll_error)
        self._poll_thread.start()

        self.start_poll_btn.setEnabled(False)
        self.stop_poll_btn.setEnabled(True)

    def _on_stop_polling(self) -> None:
        self._stop_polling_if_running()

    def _stop_polling_if_running(self) -> None:
        if self._poll_worker is not None:
            self._poll_worker.stop()
        if self._poll_thread is not None:
            self._poll_thread.quit()
            self._poll_thread.wait(2000)
        self._poll_thread = None
        self._poll_worker = None
        self.start_poll_btn.setEnabled(True)
        self.stop_poll_btn.setEnabled(False)

    @QtCore.Slot(list)
    def _on_data_ready(self, values: List[float]) -> None:
        self.plot.add_sample(values)

    @QtCore.Slot(str)
    def _on_poll_error(self, message: str) -> None:
        self.statusBar().showMessage(f"Poll error: {message}")

    def _on_write(self) -> None:
        if self._connection is None or not self._connection.is_connected():
            QtWidgets.QMessageBox.warning(self, "Not Connected", "Please connect first.")
            return
        address = int(self.write_address.value())
        value = int(self.write_value.value())
        ok, msg = self._connection.write_single_register(address=address, value=value)
        if ok:
            self.statusBar().showMessage("Write OK")
        else:
            QtWidgets.QMessageBox.critical(self, "Write Failed", msg)


def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()