# Modbus GUI with Waveform Display

A cross-platform Modbus GUI for Windows (also works on Linux/macOS) built with PySide6. Supports Modbus TCP and Modbus RTU, with real-time waveform display using pyqtgraph.

## Features
- TCP and RTU (serial) connections
- Read Holding/Input Registers (FC 3/4) and display as real-time waveforms
- Configurable poll rate, start address, and number of channels
- Optional write single register (FC 6)

## Quickstart

1. Install Python 3.10+.
2. Install dependencies:
   ```bash
   python -m pip install -r requirements.txt
   ```
3. Run the app:
   ```bash
   python app/main.py
   ```

## Windows notes
- For RTU, select the COM port (e.g., `COM3`). You may need drivers for your USB-to-serial adapter.
- To create a standalone EXE:
  ```bash
  python -m pip install pyinstaller
  pyinstaller --noconfirm --name ModbusGUI --windowed --add-data "app;app" app/main.py
  ```
  The executable will be in `dist/ModbusGUI/ModbusGUI.exe`.

## Usage
- Choose mode: TCP or RTU.
- Configure connection parameters and click Connect.
- Set Unit ID (slave address), Function (Holding or Input registers), Start Address, Count, and Poll Interval.
- Click Start Polling to visualize the selected registers as waveforms.
- Use Write Single Register to write a value to a register when connected.

## Troubleshooting
- If plotting is slow, reduce Count or increase Poll Interval.
- Ensure Unit ID matches your device configuration.
- For RTU, verify baudrate, parity, stop bits, and wiring (A/B swap).

## License
MIT
