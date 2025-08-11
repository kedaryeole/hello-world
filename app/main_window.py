from __future__ import annotations

import datetime as _dt
from typing import Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import pyqtgraph as pg
from serial.tools import list_ports

from .modbus_client import ModbusClientRTU
from .poller import ModbusPoller


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Modbus RTU GUI")
        self._client = ModbusClientRTU()
        self._poller: Optional[ModbusPoller] = None

        self._create_actions()
        self._create_ui()
        self._wire_events()
        self._refresh_ports()

    # UI construction
    def _create_actions(self) -> None:
        self.action_quit = QAction("Quit", self)
        self.action_quit.triggered.connect(QApplication.instance().quit)

    def _create_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)

        # Connection group
        conn_group = QGroupBox("Connection")
        conn_layout = QGridLayout(conn_group)
        self.port_combo = QComboBox()
        self.refresh_ports_button = QPushButton("Refresh")
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(["9600", "19200", "38400", "57600", "115200"])
        self.baud_combo.setCurrentText("38400")
        self.unit_spin = QSpinBox()
        self.unit_spin.setRange(1, 247)
        self.unit_spin.setValue(1)
        self.connect_button = QPushButton("Connect")
        self.status_label = QLabel("Disconnected")
        self.status_label.setStyleSheet("color: red;")

        conn_layout.addWidget(QLabel("Port"), 0, 0)
        conn_layout.addWidget(self.port_combo, 0, 1)
        conn_layout.addWidget(self.refresh_ports_button, 0, 2)
        conn_layout.addWidget(QLabel("Baudrate"), 1, 0)
        conn_layout.addWidget(self.baud_combo, 1, 1)
        conn_layout.addWidget(QLabel("Device ID"), 2, 0)
        conn_layout.addWidget(self.unit_spin, 2, 1)
        conn_layout.addWidget(self.connect_button, 3, 0, 1, 2)
        conn_layout.addWidget(self.status_label, 3, 2)

        # Polling group
        poll_group = QGroupBox("Polling")
        poll_layout = QGridLayout(poll_group)
        self.start_spin = QSpinBox()
        self.start_spin.setRange(0, 65535)
        self.start_spin.setValue(0)
        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, 200)
        self.count_spin.setValue(16)
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(50, 5000)
        self.interval_spin.setValue(250)
        self.start_poll_button = QPushButton("Start Polling")
        self.stop_poll_button = QPushButton("Stop")
        self.stop_poll_button.setEnabled(False)

        poll_layout.addWidget(QLabel("Start Addr"), 0, 0)
        poll_layout.addWidget(self.start_spin, 0, 1)
        poll_layout.addWidget(QLabel("Count"), 0, 2)
        poll_layout.addWidget(self.count_spin, 0, 3)
        poll_layout.addWidget(QLabel("Interval ms"), 0, 4)
        poll_layout.addWidget(self.interval_spin, 0, 5)
        poll_layout.addWidget(self.start_poll_button, 1, 0, 1, 3)
        poll_layout.addWidget(self.stop_poll_button, 1, 3, 1, 3)

        # Table
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Address", "Value", "Hex"])
        self.table.horizontalHeader().setStretchLastSection(True)

        # Write group
        write_group = QGroupBox("Write Single Register")
        write_layout = QFormLayout(write_group)
        self.write_addr = QSpinBox()
        self.write_addr.setRange(0, 65535)
        self.write_value = QSpinBox()
        self.write_value.setRange(0, 65535)
        self.write_button = QPushButton("Write")
        write_layout.addRow("Address", self.write_addr)
        write_layout.addRow("Value", self.write_value)
        write_layout.addRow(self.write_button)

        # Log and plot
        bottom = QHBoxLayout()
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.plot = pg.PlotWidget(title="Register Trend")
        self.plot_line = self.plot.plot([], [], pen=pg.mkPen('y', width=2))
        self.sample_count_spin = QSpinBox()
        self.sample_count_spin.setRange(100, 10000)
        self.sample_count_spin.setValue(1000)
        self.plot_addr_spin = QSpinBox()
        self.plot_addr_spin.setRange(0, 65535)
        self.plot_addr_spin.setValue(0)
        plot_ctrl = QGroupBox("Plot Controls")
        plot_ctrl_layout = QFormLayout(plot_ctrl)
        plot_ctrl_layout.addRow("Address", self.plot_addr_spin)
        plot_ctrl_layout.addRow("Samples", self.sample_count_spin)
        plot_layout = QVBoxLayout()
        plot_layout.addWidget(self.plot)
        plot_layout.addWidget(plot_ctrl)
        plot_container = QWidget()
        plot_container.setLayout(plot_layout)

        bottom.addWidget(plot_container, 2)
        bottom.addWidget(self.log, 1)

        layout.addWidget(conn_group)
        layout.addWidget(poll_group)
        layout.addWidget(self.table)
        layout.addWidget(write_group)
        layout.addLayout(bottom)

        self.setCentralWidget(root)

        # Menu
        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction(self.action_quit)

        self._xdata: List[float] = []
        self._ydata: List[float] = []

    def _wire_events(self) -> None:
        self.refresh_ports_button.clicked.connect(self._refresh_ports)
        self.connect_button.clicked.connect(self._toggle_connection)
        self.start_poll_button.clicked.connect(self._start_polling)
        self.stop_poll_button.clicked.connect(self._stop_polling)
        self.write_button.clicked.connect(self._write_register)

    def _refresh_ports(self) -> None:
        self.port_combo.clear()
        ports = [p.device for p in list_ports.comports()]
        if not ports:
            ports = ["/dev/ttyUSB0", "/dev/ttyS0"]
        self.port_combo.addItems(ports)

    # Connection handling
    def _toggle_connection(self) -> None:
        if self._client.is_connected:
            self._client.close()
            self._set_status(False)
            self._log("Disconnected")
        else:
            port = self.port_combo.currentText()
            baud = int(self.baud_combo.currentText())
            unit = int(self.unit_spin.value())
            ok = self._client.connect(port, baud, unit)
            self._set_status(ok)
            self._log(f"Connect to {port} @ {baud}, id={unit}: {'OK' if ok else 'FAIL'}")

    def _set_status(self, connected: bool) -> None:
        if connected:
            self.status_label.setText("Connected")
            self.status_label.setStyleSheet("color: green;")
            self.connect_button.setText("Disconnect")
        else:
            self.status_label.setText("Disconnected")
            self.status_label.setStyleSheet("color: red;")
            self.connect_button.setText("Connect")

    # Polling
    def _start_polling(self) -> None:
        if not self._client.is_connected:
            self._log("Cannot start polling: not connected")
            return
        self._stop_polling()
        start = int(self.start_spin.value())
        count = int(self.count_spin.value())
        interval = int(self.interval_spin.value())
        self._poller = ModbusPoller(self._client, start, count, interval)
        self._poller.poll_update.connect(self._on_poll_update)
        self._poller.poll_error.connect(self._on_poll_error)
        self._poller.start()
        self.start_poll_button.setEnabled(False)
        self.stop_poll_button.setEnabled(True)
        self._log(f"Polling started: start={start}, count={count}, interval={interval}ms")

    def _stop_polling(self) -> None:
        if self._poller:
            self._poller.stop()
            self._poller.wait(1000)
            self._poller = None
        self.start_poll_button.setEnabled(True)
        self.stop_poll_button.setEnabled(False)

    def _ensure_table_rows(self, count: int) -> None:
        if self.table.rowCount() != count:
            self.table.setRowCount(count)

    def _on_poll_update(self, data: Dict[int, int]) -> None:
        addresses = sorted(data.keys())
        self._ensure_table_rows(len(addresses))
        for row, addr in enumerate(addresses):
            val = data[addr]
            self.table.setItem(row, 0, QTableWidgetItem(str(addr)))
            self.table.setItem(row, 1, QTableWidgetItem(str(val)))
            self.table.setItem(row, 2, QTableWidgetItem(hex(val)))
        # Plotting
        plot_addr = int(self.plot_addr_spin.value())
        if plot_addr in data:
            now = _dt.datetime.now().timestamp()
            self._xdata.append(now)
            self._ydata.append(float(data[plot_addr]))
            max_samples = int(self.sample_count_spin.value())
            if len(self._xdata) > max_samples:
                self._xdata = self._xdata[-max_samples:]
                self._ydata = self._ydata[-max_samples:]
            # Normalize x for nicer view
            if self._xdata:
                x0 = self._xdata[0]
                xs = [x - x0 for x in self._xdata]
                self.plot_line.setData(xs, self._ydata)

    def _on_poll_error(self, message: str) -> None:
        self._log(f"Poll error: {message}")

    # Write single register
    def _write_register(self) -> None:
        if not self._client.is_connected:
            self._log("Cannot write: not connected")
            return
        addr = int(self.write_addr.value())
        value = int(self.write_value.value())
        try:
            self._client.write_single_register(addr, value)
            self._log(f"Wrote {value} -> [{addr}]")
        except Exception as exc:  # noqa: BLE001
            self._log(f"Write failed: {exc}")

    def _log(self, message: str) -> None:
        self.log.append(f"[{_dt.datetime.now().strftime('%H:%M:%S')}] {message}")
        self.log.moveCursor(self.log.textCursor().End)