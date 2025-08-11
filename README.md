# Modbus GUI (PySide6 + pymodbus)

A simple, extensible GUI for Modbus RTU communication. It provides:
- Connect/Disconnect to a serial Modbus device
- Periodic polling of holding registers into a table
- Single-register write
- Event log
- Live plot of a selected register

## Quickstart

1. Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Run the app:

```bash
python -m app.main
```

## Notes
- On Linux, serial ports usually look like `/dev/ttyUSB0`, `/dev/ttyS0`, etc.
- Ensure your user has permission to access the serial device (e.g., add to `dialout` group or use `sudo`).
- The polling range, device id, and baudrate can be adjusted from the GUI.
