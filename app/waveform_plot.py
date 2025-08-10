from __future__ import annotations

from typing import Dict, List

from PySide6 import QtGui
import pyqtgraph as pg


class WaveformPlot(pg.PlotWidget):
    def __init__(self, max_points: int = 1000, parent=None) -> None:
        super().__init__(parent=parent, background="w")
        self.max_points = max_points
        self._curves: Dict[int, pg.PlotDataItem] = {}
        self._buffers: Dict[int, List[float]] = {}

        self._configure_appearance()

    def _configure_appearance(self) -> None:
        self.setLabel("left", "Value")
        self.setLabel("bottom", "Sample")
        self.showGrid(x=True, y=True, alpha=0.3)
        self.addLegend(offset=(10, 10))

    def ensure_channels(self, num_channels: int) -> None:
        for ch in range(num_channels):
            if ch not in self._curves:
                color = self._index_to_color(ch)
                curve = self.plot(pen=pg.mkPen(color=color, width=2), name=f"Ch {ch}")
                self._curves[ch] = curve
                self._buffers[ch] = []

        # Remove extra channels if reduced
        for ch in list(self._curves.keys()):
            if ch >= num_channels:
                self.removeItem(self._curves[ch])
                del self._curves[ch]
                del self._buffers[ch]

    def add_sample(self, values: List[float]) -> None:
        self.ensure_channels(len(values))
        for ch, value in enumerate(values):
            buffer = self._buffers[ch]
            buffer.append(float(value))
            if len(buffer) > self.max_points:
                del buffer[: len(buffer) - self.max_points]
            self._curves[ch].setData(buffer)

    def clear_all(self) -> None:
        for ch in list(self._curves.keys()):
            self._buffers[ch] = []
            self._curves[ch].setData([])

    @staticmethod
    def _index_to_color(index: int) -> QtGui.QColor:
        palette = [
            (52, 152, 219),   # blue
            (46, 204, 113),   # green
            (231, 76, 60),    # red
            (155, 89, 182),   # purple
            (241, 196, 15),   # yellow
            (26, 188, 156),   # teal
            (230, 126, 34),   # orange
        ]
        r, g, b = palette[index % len(palette)]
        return QtGui.QColor(r, g, b)