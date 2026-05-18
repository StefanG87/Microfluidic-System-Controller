"""Matplotlib-backed plot panel for the v3 GUI."""

from __future__ import annotations

import math
from itertools import cycle

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QCheckBox, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from modules.mf_common import load_plot_settings, save_plot_settings
from ui_v3.fluent_compat import CaptionLabel, PushButton, TextEdit, add_info_header


PLOT_REDRAW_INTERVAL_MS = 500


class PlotPanel(QWidget):
    """Large responsive plot surface for pressure and sensor traces."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("V3PlotPanel")
        self._times = []
        self._time_zero = None
        self._target = []
        self._corrected = []
        self._measured = []
        self._flow_series = {}
        self._valve_series = {}
        self._fluigent_series = {}
        self._extra_series = {}
        self._rotary_active = []
        self._canvas = None
        self._figure = None
        self._axis = None
        self._flow_axis = None
        self._valve_axis = None
        self._target_line = None
        self._corrected_line = None
        self._measured_line = None
        self._flow_lines = {}
        self._valve_lines = {}
        self._fluigent_lines = {}
        self._extra_lines = {}
        self._current_target = 0.0
        self._checkbox_grid = None
        self._checkbox_holder = None
        self.checkboxes = {}
        self._dynamic_sensor_labels = set()
        self._dynamic_valve_labels = set()
        self._valve_labels = []
        self._rv_colors = [
            "#e41a1c",
            "#377eb8",
            "#4daf4a",
            "#984ea3",
            "#ff7f00",
            "#ffff33",
            "#a65628",
            "#f781bf",
            "#999999",
            "#66c2a5",
            "#e6ab02",
            "#a6761d",
        ]
        self._plot_settings = load_plot_settings()
        self._loading_plot_settings = False
        self._manual_view_limits = None
        self._toolbar = None
        self._legend = None
        self._layout_warning_logged = False
        self._layout_dirty = True
        self._plot_update_timer = QTimer(self)
        self._plot_update_timer.setSingleShot(True)
        self._plot_update_timer.setInterval(PLOT_REDRAW_INTERVAL_MS)
        self._plot_update_timer.timeout.connect(self.update_plot)
        self.lock_view_button = None
        self.autoscale_button = None
        self.log = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)
        add_info_header(
            layout,
            "Live Plot",
            "Displays buffered live data from the measurement session. "
            "Drag with the left mouse button to pan, use the mouse wheel to zoom, and Lock View to keep a manual view during live updates. "
            "Channel visibility is configured in the Plot Settings page.",
        )

        self._build_canvas(layout)

    def _build_canvas(self, layout: QVBoxLayout) -> None:
        """Create a Qt6 Matplotlib canvas, or a clear placeholder if unavailable."""
        try:
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
            from matplotlib.figure import Figure
        except Exception as exc:
            placeholder = QLabel(f"Matplotlib Qt6 canvas unavailable:\n{exc}")
            placeholder.setMinimumHeight(420)
            layout.addWidget(placeholder, 1)
            return

        self._figure = Figure(figsize=(8, 5), facecolor="#f8fbfc")
        self._axis = self._figure.add_subplot(111)
        self._flow_axis = self._axis.twinx()
        self._valve_axis = self._axis.twinx()
        self._figure.subplots_adjust(left=0.10, right=0.76, top=0.78, bottom=0.12)
        self._canvas = FigureCanvasQTAgg(self._figure)
        self._canvas.setMinimumHeight(420)

        tool_row = QWidget()
        tool_layout = QHBoxLayout(tool_row)
        tool_layout.setContentsMargins(0, 0, 0, 0)
        tool_layout.setSpacing(8)
        self._toolbar = NavigationToolbar2QT(self._canvas, self)
        self._toolbar.actionTriggered.connect(self._handle_toolbar_action)
        self._canvas.mpl_connect("button_release_event", self._handle_plot_release)
        self._canvas.mpl_connect("scroll_event", self._handle_plot_scroll)
        tool_layout.addWidget(self._toolbar)
        self.lock_view_button = PushButton("Lock View")
        self.lock_view_button.setCheckable(True)
        self.lock_view_button.setChecked(bool(self._plot_settings.get("lock_view", False)))
        self.lock_view_button.toggled.connect(lambda _checked: self._handle_lock_view_toggled())
        tool_layout.addWidget(self.lock_view_button)
        self.autoscale_button = PushButton("Autoscale")
        self.autoscale_button.setToolTip("Return to live autoscaling and clear any manual pan/zoom limits.")
        self.autoscale_button.clicked.connect(lambda _checked=False: self._reset_manual_view())
        tool_layout.addWidget(self.autoscale_button)
        tool_layout.addStretch(1)
        layout.addWidget(tool_row)

        layout.addWidget(self._canvas, 1)
        self._build_checkboxes()
        self.log = TextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("Program log...")
        self.log.setMinimumHeight(90)
        self.log.setMaximumHeight(140)
        layout.addWidget(self.log)
        self._configure_axes()
        QTimer.singleShot(0, self._activate_default_pan)

    def _build_checkboxes(self) -> None:
        """Create the shared plot channel selector used by the Plot Settings page."""
        self._checkbox_grid = QGridLayout()
        self._checkbox_grid.setContentsMargins(0, 0, 0, 0)
        self._checkbox_grid.setHorizontalSpacing(10)
        self._checkbox_grid.setVerticalSpacing(4)
        self._checkbox_holder = QWidget()
        self._checkbox_holder.setLayout(self._checkbox_grid)

        for label, checked in (
            ("Target", False),
            ("Corrected", True),
            ("Measured", False),
            ("Rotary", False),
            ("Flow 1", False),
            ("Flow 2", False),
            ("Flow 3", False),
            ("Flow 4", False),
        ):
            self._add_checkbox(label, checked=checked)

    def plot_settings_widget(self) -> QWidget:
        """Return the live channel selector widget for embedding in the left page stack."""
        if self._checkbox_holder is None:
            return QLabel("Plot channel controls are unavailable.")
        return self._checkbox_holder

    def axis_scale(self, axis_key: str) -> str:
        """Return the configured linear/log scale for a selectable plot axis."""
        return self._axis_scale_settings().get(str(axis_key).strip().lower(), "linear")

    def set_axis_scale(self, axis_key: str, scale: str) -> None:
        """Set a selectable axis scale from the Plot Settings page."""
        key = str(axis_key or "").strip().lower()
        selected_scale = str(scale or "").strip().lower()
        if key not in {"time", "pressure", "flow"} or selected_scale not in {"linear", "log"}:
            return

        scales = self._axis_scale_settings()
        if scales.get(key) == selected_scale:
            return
        scales[key] = selected_scale
        self._plot_settings["axis_scales"] = scales
        self._manual_view_limits = None
        self._layout_dirty = True
        self._apply_axis_scale_settings()
        self._save_plot_preferences()
        self.update_plot()

    def apply_channel_preset(self, preset: str) -> None:
        """Apply a saved-channel preset from the Plot Settings page."""
        preset_key = str(preset or "").strip().lower()
        if preset_key == "pressure":
            enabled = {"Target", "Corrected", "Measured"}
        elif preset_key == "sensors":
            enabled = {
                label
                for label in self.checkboxes
                if self._channel_category(label) in {"pressure", "flow", "fluigent", "other"}
            }
        elif preset_key == "all":
            enabled = set(self.checkboxes)
        elif preset_key == "clear":
            enabled = set()
        else:
            return

        self._loading_plot_settings = True
        try:
            for label, checkbox in self.checkboxes.items():
                checkbox.blockSignals(True)
                checkbox.setChecked(label in enabled)
                checkbox.blockSignals(False)
        finally:
            self._loading_plot_settings = False
        self._layout_dirty = True
        self._save_plot_preferences()
        self.update_plot()

    def _add_checkbox(self, label: str, checked: bool = False) -> QCheckBox | None:
        """Add one plot checkbox and redraw when the user toggles it."""
        if self._checkbox_grid is None:
            return None
        if label in self.checkboxes:
            return self.checkboxes[label]
        checkbox = QCheckBox(label)
        saved_channels = self._plot_settings.get("channels", {})
        if isinstance(saved_channels, dict) and label in saved_channels:
            checked = bool(saved_channels.get(label))
        checkbox.setChecked(bool(checked))
        checkbox.toggled.connect(lambda _checked: self._handle_channel_toggled())
        self.checkboxes[label] = checkbox
        self._reflow_checkboxes()
        return checkbox

    def _remove_checkbox(self, label: str) -> None:
        """Remove a dynamic sensor checkbox that no longer exists."""
        checkbox = self.checkboxes.pop(label, None)
        if checkbox is None or self._checkbox_grid is None:
            return
        self._checkbox_grid.removeWidget(checkbox)
        checkbox.deleteLater()
        self._reflow_checkboxes()

    def _reflow_checkboxes(self) -> None:
        """Keep selector layout compact after dynamic sensors change."""
        if self._checkbox_grid is None:
            return
        while self._checkbox_grid.count():
            item = self._checkbox_grid.takeAt(0)
            widget = item.widget()
            if widget is not None and widget not in self.checkboxes.values():
                widget.deleteLater()

        categories = (
            ("Pressure", [label for label in self.checkboxes if self._channel_category(label) == "pressure"]),
            ("Flow Sensors", [label for label in self.checkboxes if self._channel_category(label) == "flow"]),
            ("Fluigent / Pressure Sensors", [label for label in self.checkboxes if self._channel_category(label) == "fluigent"]),
            ("Valves / Rotary", [label for label in self.checkboxes if self._channel_category(label) == "valve"]),
            ("Other Sensors", [label for label in self.checkboxes if self._channel_category(label) == "other"]),
        )
        row = 0
        columns = 2
        for title, labels in categories:
            if not labels:
                continue
            self._checkbox_grid.addWidget(CaptionLabel(title), row, 0, 1, columns)
            row += 1
            for index, label in enumerate(labels):
                self._checkbox_grid.addWidget(self.checkboxes[label], row + index // columns, index % columns)
            row += math.ceil(len(labels) / columns)

    @staticmethod
    def _channel_category(label: str) -> str:
        """Return the settings group for a plot channel label."""
        normalized = str(label).strip().lower()
        if normalized in {"target", "corrected", "measured"}:
            return "pressure"
        if normalized.startswith("flow"):
            return "flow"
        if normalized.startswith("sn") or normalized.startswith("fluigent"):
            return "fluigent"
        if normalized == "rotary" or normalized.startswith(("pneumatic", "fluidic", "valve")):
            return "valve"
        return "other"

    def _is_checked(self, label: str) -> bool:
        """Return True for enabled plot channels."""
        checkbox = self.checkboxes.get(label)
        return bool(checkbox is not None and checkbox.isChecked())

    def _handle_channel_toggled(self) -> None:
        """Persist plot channel selection and redraw immediately."""
        if not self._loading_plot_settings:
            self._save_plot_preferences()
        self._layout_dirty = True
        self._request_plot_update()

    def _handle_lock_view_toggled(self) -> None:
        """Persist lock-view state and autoscale again when the lock is released."""
        if not self._is_lock_view_enabled():
            self._manual_view_limits = None
        self._save_plot_preferences()
        self.update_plot()

    def _reset_manual_view(self) -> None:
        """Return to live autoscaling after manual pan or wheel zoom."""
        self._manual_view_limits = None
        if self.lock_view_button is not None and self.lock_view_button.isChecked():
            self.lock_view_button.blockSignals(True)
            self.lock_view_button.setChecked(False)
            self.lock_view_button.blockSignals(False)
            self._save_plot_preferences()
        self.update_plot()
        QTimer.singleShot(0, self._activate_default_pan)

    def _handle_toolbar_action(self, action) -> None:
        """Keep live redraws compatible with Matplotlib toolbar navigation."""
        text = f"{action.text()} {action.toolTip()}".lower()
        if "home" in text or "original" in text or "reset" in text:
            self._manual_view_limits = None
            if self.lock_view_button is not None and self.lock_view_button.isChecked():
                self.lock_view_button.blockSignals(True)
                self.lock_view_button.setChecked(False)
                self.lock_view_button.blockSignals(False)
                self._save_plot_preferences()
            QTimer.singleShot(0, self._activate_default_pan)
            return
        if "back" in text or "forward" in text:
            QTimer.singleShot(0, self._store_manual_view_from_axes)
            QTimer.singleShot(0, self._activate_default_pan)

    def _activate_default_pan(self) -> None:
        """Keep the plot ready for left-drag panning without an extra toolbar click."""
        if self._toolbar is None:
            return
        mode = str(getattr(self._toolbar, "mode", "") or "").lower()
        if "pan" in mode:
            return
        try:
            self._toolbar.pan()
        except Exception as exc:
            if self.log is not None:
                self.log.append(f"[v3] Plot pan activation failed: {exc}")

    def _handle_plot_release(self, event) -> None:
        """Automatically preserve a toolbar pan/zoom view during live updates."""
        if event.inaxes not in {self._axis, self._flow_axis, self._valve_axis}:
            return
        mode = str(getattr(self._toolbar, "mode", "") or "").lower()
        if "pan" in mode or "zoom" in mode:
            QTimer.singleShot(0, self._store_manual_view_from_axes)

    def _handle_plot_scroll(self, event) -> None:
        """Allow wheel zooming without requiring the explicit Lock View button."""
        if event.inaxes not in {self._axis, self._flow_axis, self._valve_axis}:
            return
        self._zoom_axes_at_event(event)
        self._store_manual_view_from_axes()
        self._draw()

    def _store_manual_view_from_axes(self) -> None:
        """Store the current axes limits as the live redraw view."""
        self._manual_view_limits = self._capture_view_limits()

    def _zoom_axes_at_event(self, event) -> None:
        """Zoom the shared x-axis around the cursor and the active y-axis around its value."""
        if self._axis is None or event.xdata is None:
            return
        scale = 0.85 if getattr(event, "button", "") == "up" else 1.18

        x_min, x_max = self._axis.get_xlim()
        cursor_x = float(event.xdata)
        left = cursor_x - x_min
        right = x_max - cursor_x
        new_x_min = cursor_x - left * scale
        new_x_max = cursor_x + right * scale
        if self._axis.get_xscale() == "log" and new_x_min <= 0.0:
            new_x_min = max(min(x_min, cursor_x * 0.5), 1e-9)
        for axis in (self._axis, self._flow_axis, self._valve_axis):
            if axis is not None:
                axis.set_xlim(new_x_min, new_x_max)

        axis = event.inaxes
        if axis is not None and event.ydata is not None:
            y_min, y_max = axis.get_ylim()
            cursor_y = float(event.ydata)
            bottom = cursor_y - y_min
            top = y_max - cursor_y
            new_y_min = cursor_y - bottom * scale
            new_y_max = cursor_y + top * scale
            if axis.get_yscale() == "log" and new_y_min <= 0.0:
                new_y_min = max(min(y_min, cursor_y * 0.5), 1e-9)
            axis.set_ylim(new_y_min, new_y_max)

    def _save_plot_preferences(self) -> None:
        """Store plot channel and lock-view preferences in the existing settings JSON."""
        if self._loading_plot_settings:
            return
        self._plot_settings = {
            "channels": {
                label: checkbox.isChecked()
                for label, checkbox in self.checkboxes.items()
            },
            "lock_view": self._is_lock_view_enabled(),
            "axis_scales": self._axis_scale_settings(),
        }
        save_plot_settings(self._plot_settings)

    def _axis_scale_settings(self) -> dict:
        """Return sanitized axis scale settings for the plot."""
        raw = self._plot_settings.get("axis_scales", {})
        raw = raw if isinstance(raw, dict) else {}
        scales = {"time": "linear", "pressure": "linear", "flow": "linear"}
        for key in scales:
            value = str(raw.get(key, "linear")).strip().lower()
            if value in {"linear", "log"}:
                scales[key] = value
        return scales

    def _apply_axis_scale_settings(self) -> None:
        """Apply configured linear/log scales to the active axes."""
        if self._axis is None:
            return
        scales = self._axis_scale_settings()
        time_scale = scales["time"]
        for axis in (self._axis, self._flow_axis, self._valve_axis):
            if axis is not None:
                axis.set_xscale(time_scale)
        self._axis.set_yscale(scales["pressure"])
        if self._flow_axis is not None:
            self._flow_axis.set_yscale(scales["flow"])
        if self._valve_axis is not None:
            self._valve_axis.set_yscale("linear")
        self._ensure_valid_scale_limits()

    def _ensure_valid_scale_limits(self) -> None:
        """Keep log-scaled axes away from zero before data arrives."""
        if self._axis is None:
            return
        axes = (self._axis, self._flow_axis, self._valve_axis)
        if self._axis.get_xscale() == "log":
            for axis in axes:
                if axis is not None:
                    x_min, x_max = axis.get_xlim()
                    axis.set_xlim(max(x_min, 1e-3), max(x_max, 10.0))
        for axis in axes:
            if axis is not None and axis.get_yscale() == "log":
                y_min, y_max = axis.get_ylim()
                axis.set_ylim(max(y_min, 1e-9), max(y_max, max(y_min, 1e-9) * 10.0))

    def _is_lock_view_enabled(self) -> bool:
        """Return True when live redraws should preserve manual zoom limits."""
        return bool(self.lock_view_button is not None and self.lock_view_button.isChecked())

    def _configure_axes(self, draw: bool = True) -> None:
        """Apply the v3 light plot style."""
        if self._axis is None:
            return
        for axis in (self._axis, self._flow_axis, self._valve_axis):
            axis.set_facecolor("#ffffff")
            axis.tick_params(colors="#495966")
            for spine in axis.spines.values():
                spine.set_color("#cbd7df")
        self._axis.set_xlabel("Time [s]", color="#495966")
        self._axis.set_ylabel("Pressure [mbar]", color="#495966")
        self._flow_axis.set_ylabel("Flow / sensor values", color="#495966")
        self._flow_axis.spines["right"].set_position(("axes", 1.22))
        self._flow_axis.yaxis.set_label_position("right")
        self._flow_axis.yaxis.tick_right()
        self._valve_axis.set_ylabel("Valve state", color="#495966")
        self._valve_axis.spines["right"].set_position(("axes", 1.10))
        self._valve_axis.yaxis.set_label_position("right")
        self._valve_axis.yaxis.tick_right()
        self._axis.grid(True, color="#e1e9ee", linewidth=0.8)
        self._target_line = None
        self._corrected_line = None
        self._measured_line = None
        self._apply_axis_scale_settings()
        if draw:
            self._draw()

    def _clear_axes(self) -> None:
        """Clear axes before drawing the current buffers, matching the classic live plot."""
        if self._axis is None:
            return
        self._axis.clear()
        if self._flow_axis is not None:
            self._flow_axis.clear()
        if self._valve_axis is not None:
            self._valve_axis.clear()
        self._configure_axes(draw=False)

    def reset(self) -> None:
        """Clear all visible traces."""
        self._times.clear()
        self._time_zero = None
        self._target.clear()
        self._corrected.clear()
        self._measured.clear()
        self._flow_series.clear()
        self._valve_series.clear()
        self._fluigent_series.clear()
        self._extra_series.clear()
        self._rotary_active.clear()
        self._flow_lines.clear()
        self._valve_lines.clear()
        self._fluigent_lines.clear()
        self._extra_lines.clear()
        self._manual_view_limits = None
        if self._axis is not None:
            self._axis.clear()
        if self._flow_axis is not None:
            self._flow_axis.clear()
        if self._valve_axis is not None:
            self._valve_axis.clear()
        self._configure_axes()

    def append_log(self, message: str) -> None:
        """Append runtime/program messages below the live plot."""
        if self.log is not None:
            self.log.append(str(message))

    def set_device_catalog(self, catalog_info: dict | None) -> None:
        """Expose detected sensor channels as selectable plot traces."""
        if not isinstance(catalog_info, dict):
            catalog_info = {}

        valve_names = [
            str(name).strip()
            for name in catalog_info.get("valve_names", [])
            if str(name).strip()
        ]
        desired_valves = set(valve_names)
        for stale_label in sorted(self._dynamic_valve_labels - desired_valves):
            self._remove_checkbox(stale_label)
        for label in valve_names:
            if label not in self.checkboxes:
                self._add_checkbox(label, checked=False)
        self._dynamic_valve_labels = desired_valves
        self._valve_labels = valve_names

        descriptors = list(catalog_info.get("sensor_descriptors", []))
        desired_dynamic_labels = []
        for descriptor in descriptors:
            if not isinstance(descriptor, dict):
                continue
            label = str(descriptor.get("name", "")).strip()
            kind = str(descriptor.get("kind", "")).strip()
            if not label or kind in {"internal_pressure", "flow"}:
                continue
            desired_dynamic_labels.append(label)

        desired = set(desired_dynamic_labels)
        for stale_label in sorted(self._dynamic_sensor_labels - desired):
            self._remove_checkbox(stale_label)

        for label in desired_dynamic_labels:
            if label not in self.checkboxes:
                self._add_checkbox(label, checked=False)
            self._dynamic_sensor_labels.add(label)

        self._dynamic_sensor_labels = desired
        self._layout_dirty = True
        self.update_plot()

    def append_sample(self, sample) -> None:
        """Append one MeasurementSample emitted by the runtime controller."""
        sample_time = float(sample.rel_time)
        if self._time_zero is None:
            self._time_zero = sample_time
        self._times.append(max(0.0, sample_time - self._time_zero))
        self._target.append(self._current_target)
        self._corrected.append(float(sample.corrected_pressure))
        self._measured.append(float(sample.measured_pressure))
        try:
            active_port = int(getattr(sample, "rotary_active", 0) or 0)
        except (TypeError, ValueError):
            active_port = 0
        self._rotary_active.append(active_port)

        for index, state in enumerate(getattr(sample, "valve_states", []) or []):
            self._append_named_value(self._valve_series, self._valve_label(index), state)
        for name, value in sample.flow_values:
            self._append_named_value(self._flow_series, name, value)
        for name, value in sample.fluigent_values:
            self._append_named_value(self._fluigent_series, name, value)
        for name, value, _unit in sample.extra_values:
            self._append_named_value(self._extra_series, name, value)

        self._request_plot_update()

    def update_target(self, target_pressure: float) -> None:
        """Update the target series used by the next redraw."""
        new_target = float(target_pressure)
        target_changed = new_target != self._current_target
        self._current_target = new_target
        if self._target and self._target[-1] != self._current_target:
            self._target[-1] = self._current_target
            self._request_plot_update()
        elif target_changed and not self._target:
            self._request_plot_update()

    def _request_plot_update(self) -> None:
        """Coalesce live redraws so sampling is not blocked by Matplotlib rendering."""
        if self._axis is None:
            return
        if not self._plot_update_timer.isActive():
            self._plot_update_timer.start()

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

    def _valve_label(self, index: int) -> str:
        """Return the catalog label for a sampled valve index."""
        if 0 <= index < len(self._valve_labels):
            return self._valve_labels[index]
        return f"Valve {index + 1}"

    def _line_for_sensor(self, line_store: dict, name: str, label_prefix: str):
        """Create or return a line on the auxiliary axis."""
        if name in line_store:
            return line_store[name]
        if self._flow_axis is None:
            return None
        (line,) = self._flow_axis.plot([], [], label=f"{label_prefix}: {name}", linewidth=1.4)
        line_store[name] = line
        return line

    def update_plot(self) -> None:
        """Redraw the full plot from current buffers, like the classic PlotArea."""
        if self._axis is None:
            return
        locked_limits = self._capture_view_limits() if self._is_lock_view_enabled() else self._manual_view_limits
        axis_scales = self._capture_axis_scales()
        if not self._times:
            self._draw()
            return

        self._clear_axes()
        self._restore_axis_scales(axis_scales)
        color_cycle = cycle([
            "tab:blue",
            "tab:orange",
            "tab:green",
            "tab:red",
            "tab:purple",
            "tab:brown",
            "tab:pink",
            "tab:gray",
            "tab:olive",
            "tab:cyan",
        ])

        if self._is_checked("Target"):
            self._plot_series(self._axis, self._target, "Target", ":", next(color_cycle))
        if self._is_checked("Corrected"):
            self._plot_series(self._axis, self._corrected, "Corrected", "-", next(color_cycle))
        if self._is_checked("Measured"):
            self._plot_series(self._axis, self._measured, "Measured", "--", next(color_cycle))

        all_pressures = []
        if self._is_checked("Corrected"):
            all_pressures.extend(self._corrected)
        if self._is_checked("Measured"):
            all_pressures.extend(self._measured)
        if self._is_checked("Target"):
            all_pressures.extend(self._target)
        for name, values in self._fluigent_series.items():
            if not self._is_checked(name):
                continue
            self._plot_series(self._axis, values, f"Fluigent: {name}", "-", next(color_cycle))
            all_pressures.extend(value for value in values if value is not None)

        if all_pressures:
            valid_pressures = [value for value in all_pressures if value is not None]
        else:
            valid_pressures = []
        if valid_pressures:
            self._set_axis_y_limits(self._axis, valid_pressures)

        if self._is_checked("Rotary"):
            self._draw_rotary_active_full()

        if self._flow_axis is not None:
            flow_plotted = False
            for name, values in self._flow_series.items():
                if not self._is_checked(name):
                    continue
                self._plot_series(self._flow_axis, values, f"Flow: {name}", "-", next(color_cycle))
                flow_plotted = True
            for name, values in self._extra_series.items():
                if not self._is_checked(name):
                    continue
                self._plot_series(self._flow_axis, values, f"Extra: {name}", "-", next(color_cycle))
                flow_plotted = True
            if flow_plotted:
                self._flow_axis.set_ylabel("Flow / sensor values", color="#495966")
                self._flow_axis.spines["right"].set_visible(True)
                self._flow_axis.yaxis.set_label_position("right")
                self._flow_axis.yaxis.tick_right()
            else:
                self._flow_axis.set_ylabel("")
                self._flow_axis.set_yticks([])
                self._flow_axis.spines["right"].set_visible(False)

        if self._valve_axis is not None:
            valves_plotted = False
            for name, values in self._valve_series.items():
                if not self._is_checked(name):
                    continue
                self._plot_series(
                    self._valve_axis,
                    values,
                    f"Valve: {name}",
                    "-",
                    next(color_cycle),
                    drawstyle="steps-post",
                )
                valves_plotted = True
            if valves_plotted:
                self._valve_axis.set_ylabel("Valve state", color="#495966")
                self._valve_axis.set_ylim(-0.1, 1.1)
                self._valve_axis.set_yticks([0, 1])
                self._valve_axis.spines["right"].set_visible(True)
                self._valve_axis.yaxis.set_label_position("right")
                self._valve_axis.yaxis.tick_right()
            else:
                self._valve_axis.set_ylabel("")
                self._valve_axis.set_yticks([])
                self._valve_axis.spines["right"].set_visible(False)

        self._axis.set_xlabel("Time [s]", color="#495966")
        self._axis.set_ylabel("Pressure [mbar]", color="#495966")
        self._axis.grid(True, color="#e1e9ee", linewidth=0.8)
        if self._flow_axis is not None:
            self._flow_axis.grid(True, color="#edf2f5", linewidth=0.6)
        if self._valve_axis is not None:
            self._valve_axis.grid(False)
        if locked_limits:
            self._restore_view_limits(locked_limits)
        else:
            self._apply_time_axis()
        self._draw()

    @staticmethod
    def _finite_values(values) -> list[float]:
        """Return finite numeric values from a buffered plot series."""
        finite = []
        for value in values:
            try:
                number = float(value)
            except (TypeError, ValueError):
                continue
            if math.isfinite(number):
                finite.append(number)
        return finite

    def _set_axis_y_limits(self, axis, values, default=(0.0, 100.0)) -> None:
        """Apply readable y-limits while respecting a user-selected log scale."""
        finite = self._finite_values(values)
        if not finite:
            if axis.get_yscale() == "log":
                axis.set_ylim(0.1, 10.0)
                return
            axis.set_ylim(*default)
            return

        if axis.get_yscale() == "log":
            positive = [value for value in finite if value > 0.0]
            if not positive:
                axis.set_ylim(0.1, 10.0)
                return
            y_min = min(positive)
            y_max = max(positive)
            axis.set_ylim(max(y_min * 0.8, 1e-9), max(y_max * 1.2, y_min * 10.0))
            return

        y_min = min(finite)
        y_max = max(finite)
        pad = 0.1 * max(1.0, abs(y_max - y_min))
        axis.set_ylim(y_min - pad, y_max + pad)

    def _draw_rotary_active_full(self) -> None:
        """Draw v2-style rotary-port background bands from sampled active ports."""
        if self._axis is None or len(self._times) < 2 or not self._rotary_active:
            return
        n = min(len(self._times), len(self._rotary_active))
        if n < 2:
            return
        times = self._times[:n]
        ports = []
        for value in self._rotary_active[:n]:
            try:
                port = int(value or 0)
            except (TypeError, ValueError):
                port = 0
            ports.append(port if port > 0 else 0)

        try:
            from matplotlib.transforms import blended_transform_factory

            transform = blended_transform_factory(self._axis.transData, self._axis.transAxes)
        except Exception:
            transform = None

        index = 0
        while index < n:
            port = ports[index]
            end_index = index + 1
            while end_index < n and ports[end_index] == port:
                end_index += 1

            if port > 0:
                start_time = times[index]
                end_time = times[end_index] if end_index < n else times[-1]
                if end_time > start_time:
                    color = self._rv_colors[(port - 1) % len(self._rv_colors)]
                    self._axis.axvspan(start_time, end_time, color=color, alpha=0.15, zorder=0)
                    if transform is not None and (end_time - start_time) >= 0.25:
                        label_x = 0.5 * (start_time + end_time)
                        self._axis.text(
                            label_x,
                            0.98,
                            str(port),
                            transform=transform,
                            ha="center",
                            va="top",
                            fontsize=8,
                            color="#333333",
                            zorder=1,
                        )
            index = end_index

    def _apply_time_axis(self) -> None:
        """Autoscale the time axis from the actual buffered samples."""
        if self._axis is None or not self._times:
            return
        latest_time = max(float(value) for value in self._times)
        x_min = 0.0
        x_max = max(10.0, latest_time * 1.05)
        if latest_time > 10.0:
            x_max = latest_time + max(1.0, latest_time * 0.03)
        if self._axis.get_xscale() == "log":
            positive_times = [float(value) for value in self._times if float(value) > 0.0]
            x_min = min(positive_times) if positive_times else 1e-3
            x_max = max(x_max, x_min * 10.0)
        self._axis.set_xlim(x_min, x_max)
        if self._flow_axis is not None:
            self._flow_axis.set_xlim(x_min, x_max)
        if self._valve_axis is not None:
            self._valve_axis.set_xlim(x_min, x_max)

    def _capture_view_limits(self):
        """Capture current axes limits before a redraw when the user locked zoom."""
        if self._axis is None:
            return None
        limits = {
            "pressure": (self._axis.get_xlim(), self._axis.get_ylim()),
        }
        if self._flow_axis is not None:
            limits["flow"] = (self._flow_axis.get_xlim(), self._flow_axis.get_ylim())
        if self._valve_axis is not None:
            limits["valves"] = (self._valve_axis.get_xlim(), self._valve_axis.get_ylim())
        return limits

    def _capture_axis_scales(self):
        """Preserve user-selected linear/log axis scales across live redraws."""
        if self._axis is None:
            return None
        scales = {
            "pressure": (self._axis.get_xscale(), self._axis.get_yscale()),
        }
        if self._flow_axis is not None:
            scales["flow"] = (self._flow_axis.get_xscale(), self._flow_axis.get_yscale())
        if self._valve_axis is not None:
            scales["valves"] = (self._valve_axis.get_xscale(), self._valve_axis.get_yscale())
        return scales

    def _restore_axis_scales(self, scales) -> None:
        """Restore axis scale modes selected through settings or the Matplotlib toolbar."""
        if not scales or self._axis is None:
            return
        for key, axis in (
            ("pressure", self._axis),
            ("flow", self._flow_axis),
            ("valves", self._valve_axis),
        ):
            if axis is None or key not in scales:
                continue
            xscale, yscale = scales[key]
            try:
                axis.set_xscale(xscale)
                axis.set_yscale(yscale)
            except ValueError:
                axis.set_xscale("linear")
                axis.set_yscale("linear")

    def _restore_view_limits(self, limits) -> None:
        """Restore a manually zoomed view while live samples continue to arrive."""
        if not limits or self._axis is None:
            return
        pressure_limits = limits.get("pressure")
        if pressure_limits:
            self._axis.set_xlim(*pressure_limits[0])
            self._axis.set_ylim(*pressure_limits[1])
        flow_limits = limits.get("flow")
        if flow_limits and self._flow_axis is not None:
            self._flow_axis.set_xlim(*flow_limits[0])
            self._flow_axis.set_ylim(*flow_limits[1])
        valve_limits = limits.get("valves")
        if valve_limits and self._valve_axis is not None:
            self._valve_axis.set_xlim(*valve_limits[0])
            self._valve_axis.set_ylim(*valve_limits[1])

    def _plot_series(self, axis, values, label: str, linestyle: str, color: str, drawstyle: str | None = None) -> None:
        """Plot a buffered series using the shared v3 time axis."""
        n = min(len(self._times), len(values))
        if n <= 0:
            return
        kwargs = {}
        if drawstyle:
            kwargs["drawstyle"] = drawstyle
        axis.plot(
            self._times[:n],
            list(values)[:n],
            label=label,
            linestyle=linestyle,
            color=color,
            linewidth=1.6,
            **kwargs,
        )

    def _draw(self) -> None:
        """Draw the canvas if Matplotlib is active."""
        if self._canvas is None:
            return
        if self._layout_dirty:
            try:
                self._figure.tight_layout(rect=(0.02, 0.02, 0.88, 0.84))
            except Exception as exc:
                if not self._layout_warning_logged and self.log is not None:
                    self.log.append(f"[v3] Plot layout warning: {exc}")
                    self._layout_warning_logged = True
            finally:
                self._layout_dirty = False
        handles, labels = self._axis.get_legend_handles_labels()
        if self._flow_axis is not None:
            extra_handles, extra_labels = self._flow_axis.get_legend_handles_labels()
            handles.extend(extra_handles)
            labels.extend(extra_labels)
        if self._valve_axis is not None:
            valve_handles, valve_labels = self._valve_axis.get_legend_handles_labels()
            handles.extend(valve_handles)
            labels.extend(valve_labels)
        if self._figure is not None:
            for old_legend in list(self._figure.legends):
                old_legend.remove()
        if handles:
            # Figure-level legends are not clipped by the plot axes or the extra right axes.
            self._legend = self._figure.legend(
                handles,
                labels,
                loc="upper center",
                bbox_to_anchor=(0.5, 0.98),
                ncol=max(1, min(len(labels), 6)),
                fontsize="small",
                frameon=False,
            )
            for text in self._legend.get_texts():
                text.set_color("#26333d")
        self._canvas.draw_idle()
        self._canvas.update()
