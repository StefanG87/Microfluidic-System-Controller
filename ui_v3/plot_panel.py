"""Matplotlib-backed plot panel for the v3 GUI."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ui_v3.fluent_compat import CaptionLabel, SubtitleLabel


class PlotPanel(QWidget):
    """Large responsive plot surface for pressure and sensor traces."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("V3PlotPanel")
        self._times = []
        self._target = []
        self._corrected = []
        self._measured = []
        self._flow_series = {}
        self._fluigent_series = {}
        self._extra_series = {}
        self._canvas = None
        self._figure = None
        self._axis = None
        self._flow_axis = None
        self._target_line = None
        self._corrected_line = None
        self._measured_line = None
        self._flow_lines = {}
        self._fluigent_lines = {}
        self._extra_lines = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        layout.addWidget(SubtitleLabel("Live Measurement"))
        layout.addWidget(CaptionLabel("Pressure, flow, Fluigent, and future measurement channels"))

        self._build_canvas(layout)

    def _build_canvas(self, layout: QVBoxLayout) -> None:
        """Create a Qt6 Matplotlib canvas, or a clear placeholder if unavailable."""
        try:
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
            from matplotlib.figure import Figure
        except Exception as exc:
            placeholder = QLabel(f"Matplotlib Qt6 canvas unavailable:\n{exc}")
            placeholder.setMinimumHeight(420)
            layout.addWidget(placeholder, 1)
            return

        self._figure = Figure(figsize=(8, 5), facecolor="#111316")
        self._axis = self._figure.add_subplot(111)
        self._flow_axis = self._axis.twinx()
        self._figure.subplots_adjust(left=0.10, right=0.78, top=0.92, bottom=0.12)
        self._canvas = FigureCanvasQTAgg(self._figure)
        self._canvas.setMinimumHeight(420)
        layout.addWidget(self._canvas, 1)
        self._configure_axes()

    def _configure_axes(self) -> None:
        """Apply the v3 dark plot style."""
        if self._axis is None:
            return
        for axis in (self._axis, self._flow_axis):
            axis.set_facecolor("#15181d")
            axis.tick_params(colors="#d7dce2")
            for spine in axis.spines.values():
                spine.set_color("#596273")
        self._axis.set_xlabel("Time [s]", color="#d7dce2")
        self._axis.set_ylabel("Pressure [mbar]", color="#d7dce2")
        self._flow_axis.set_ylabel("Sensor values", color="#d7dce2")
        self._flow_axis.spines["right"].set_position(("axes", 1.08))
        self._axis.grid(True, color="#2a3039", linewidth=0.7)
        (self._target_line,) = self._axis.plot([], [], color="#ffb454", label="Target")
        (self._corrected_line,) = self._axis.plot([], [], color="#50fa7b", label="Corrected")
        (self._measured_line,) = self._axis.plot([], [], color="#8be9fd", label="Measured")
        self._draw()

    def reset(self) -> None:
        """Clear all visible traces."""
        self._times.clear()
        self._target.clear()
        self._corrected.clear()
        self._measured.clear()
        self._flow_series.clear()
        self._fluigent_series.clear()
        self._extra_series.clear()
        self._flow_lines.clear()
        self._fluigent_lines.clear()
        self._extra_lines.clear()
        if self._axis is not None:
            self._axis.clear()
        if self._flow_axis is not None:
            self._flow_axis.clear()
        self._configure_axes()

    def append_sample(self, sample) -> None:
        """Append one MeasurementSample emitted by the runtime controller."""
        self._times.append(float(sample.rel_time))
        self._target.append(None)
        self._corrected.append(float(sample.corrected_pressure))
        self._measured.append(float(sample.measured_pressure))

        for name, value in sample.flow_values:
            self._append_named_value(self._flow_series, name, value)
        for name, value in sample.fluigent_values:
            self._append_named_value(self._fluigent_series, name, value)
        for name, value, _unit in sample.extra_values:
            self._append_named_value(self._extra_series, name, value)

        self._update_lines()

    def update_target(self, target_pressure: float) -> None:
        """Update the target series used by the next redraw."""
        if self._target:
            self._target[-1] = float(target_pressure)
            self._update_lines()

    def _append_named_value(self, store: dict, name: str, value) -> None:
        """Keep sensor series aligned with the pressure time axis."""
        clean_name = str(name)
        if clean_name not in store:
            store[clean_name] = [None] * (len(self._times) - 1)
        try:
            store[clean_name].append(float(value))
        except (TypeError, ValueError):
            store[clean_name].append(None)
        for other_name, values in store.items():
            if other_name != clean_name and len(values) < len(self._times):
                values.append(None)

    def _line_for_sensor(self, line_store: dict, name: str, label_prefix: str):
        """Create or return a line on the auxiliary axis."""
        if name in line_store:
            return line_store[name]
        if self._flow_axis is None:
            return None
        (line,) = self._flow_axis.plot([], [], label=f"{label_prefix}: {name}", linewidth=1.4)
        line_store[name] = line
        return line

    def _update_lines(self) -> None:
        """Redraw all traces with autoscaled axes."""
        if self._axis is None:
            return
        target = [
            self._target[index] if self._target[index] is not None else None
            for index in range(len(self._times))
        ]
        self._target_line.set_data(self._times, target)
        self._corrected_line.set_data(self._times, self._corrected)
        self._measured_line.set_data(self._times, self._measured)

        for name, values in self._flow_series.items():
            line = self._line_for_sensor(self._flow_lines, name, "Flow")
            if line is not None:
                line.set_data(self._times[: len(values)], values)
        for name, values in self._fluigent_series.items():
            line = self._line_for_sensor(self._fluigent_lines, name, "Fluigent")
            if line is not None:
                line.set_data(self._times[: len(values)], values)
        for name, values in self._extra_series.items():
            line = self._line_for_sensor(self._extra_lines, name, "Extra")
            if line is not None:
                line.set_data(self._times[: len(values)], values)

        self._axis.relim()
        self._axis.autoscale_view()
        if self._flow_axis is not None:
            self._flow_axis.relim()
            self._flow_axis.autoscale_view()
        self._draw()

    def _draw(self) -> None:
        """Draw the canvas if Matplotlib is active."""
        if self._canvas is None:
            return
        handles, labels = self._axis.get_legend_handles_labels()
        if self._flow_axis is not None:
            extra_handles, extra_labels = self._flow_axis.get_legend_handles_labels()
            handles.extend(extra_handles)
            labels.extend(extra_labels)
        if handles:
            self._axis.legend(handles, labels, loc="upper left", facecolor="#1b1e23", labelcolor="#f3f5f7")
        self._canvas.draw_idle()
