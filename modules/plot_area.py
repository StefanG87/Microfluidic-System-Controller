
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QCheckBox
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from collections import deque
from modules.sampling_manager import sampling_manager


class PlotArea(QWidget):
    """
    Pressure/flow/valve plot with optional rotary time-bands.
    Rotary bands are derived from a stepwise series of (t_rel_s, active_port).
    A band persists as long as the same port remains active (>0).
    """

    def __init__(self, parent, time_data, target, corrected, measured,
                 valve_states, flow_sensors_data, fluigent_pressure_data,
                 fluigent_sensors, rotary_active=None):
        super().__init__(parent)
        self.parent = parent

        # Data sources (lists/deques maintained by the GUI)
        self.time_data = time_data
        self.target = target
        self.corrected = corrected
        self.measured = measured
        self.valve_states = valve_states
        self.flow_sensors_data = flow_sensors_data
        self.fluigent_pressure_data = fluigent_pressure_data
        self.fluigent_sensors = fluigent_sensors
        self.rotary_active = rotary_active

        # Rotary event stream: deque[(t_rel_s: float, port: int|0)]
        self.rotary_events = deque(maxlen=20000)

        # --- UI scaffold ---
        self.layout = QVBoxLayout(self)
        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.ax_pressure = self.figure.add_subplot(111)
        self.ax_flow = self.ax_pressure.twinx()
        self.ax_valves = self.ax_pressure.twinx()
        self.figure.subplots_adjust(left=0.10, right=0.76, top=0.82, bottom=0.12)

        # Place the two right spines
        self.ax_flow.spines["right"].set_position(("axes", 1.22))
        self.ax_valves.spines["right"].set_position(("axes", 1.10))
        self.ax_flow.yaxis.set_label_position('right'); self.ax_flow.yaxis.tick_right()
        self.ax_valves.yaxis.set_label_position('right'); self.ax_valves.yaxis.tick_right()

        self.layout.addWidget(self.canvas)

        # --- Checkboxes: fixed two-row layout ---
        from PyQt5.QtWidgets import QGridLayout, QCheckBox
        
        self.checkboxes = {}
        grid = QGridLayout()
        self.checkbox_grid = grid
        
        # Row 1: Target / Corrected / Measured / Rotary / Flows / Fluigent
        row0_labels = ["Target", "Corrected", "Measured", "Rotary"]
        row0_labels += [f"Flow {i+1}" for i in range(4)]
        row0_labels += [f"SN{sensor.device_sn}" for sensor in self.fluigent_sensors]
        # Choose enough columns so the full first row fits (at least 10).
        COLS = max(10, len(row0_labels))
        self.checkbox_columns = COLS
        self.sensor_checkbox_count = len(row0_labels)
        for c in range(COLS):
            grid.setColumnStretch(c, 1)
        # Add every item from the first row without truncating the list.
        for col, lab in enumerate(row0_labels):
            cb = QCheckBox(lab)
            if lab in ("Corrected", "Flow 1"):
                cb.setChecked(True)
            self.checkboxes[lab] = cb
            grid.addWidget(cb, 0, col)
        # Row 2: valves V1..V8, left-aligned.
        for i in range(8):
            lab = f"V{i+1}"
            cb = QCheckBox(lab)
            self.checkboxes[lab] = cb
            grid.addWidget(cb, 1, i)
        
        self.layout.addLayout(grid)



        # Fixed color map for up to 12 ports (repeats)
        self._rv_colors = [
    "#e41a1c",  # Red
    "#377eb8",  # Blue
    "#4daf4a",  # Green
    "#984ea3",  # Violet
    "#ff7f00",  # Orange
    "#ffff33",  # Yellow
    "#a65628",  # Brown
    "#f781bf",  # Pink
    "#999999",  # Gray
    "#66c2a5",  # Turquoise
    "#e6ab02",  # Ochre
    "#a6761d",  # Warm brown
]

    # -------- rotary API --------

    def set_rotary_events(self, events_deque):
        """Attach the (t, port) event deque used to render rotary bands."""
        self.rotary_events = events_deque

    def refresh_fluigent_sensors(self, fluigent_sensors, fluigent_pressure_data):
        """Attach refreshed Fluigent buffers and sync checkboxes with detected channels."""
        old_labels = {f"SN{sensor.device_sn}" for sensor in self.fluigent_sensors}
        new_labels = {f"SN{sensor.device_sn}" for sensor in fluigent_sensors}

        for label in sorted(old_labels - new_labels):
            checkbox = self.checkboxes.pop(label, None)
            if checkbox is not None:
                self.checkbox_grid.removeWidget(checkbox)
                checkbox.deleteLater()

        self.fluigent_sensors = fluigent_sensors
        self.fluigent_pressure_data = fluigent_pressure_data

        for sensor in self.fluigent_sensors:
            label = f"SN{sensor.device_sn}"
            if label in self.checkboxes:
                continue

            cb = QCheckBox(label)
            self.checkboxes[label] = cb
            col = self.sensor_checkbox_count
            self.sensor_checkbox_count += 1
            if col >= self.checkbox_columns:
                self.checkbox_columns = col + 1
                self.checkbox_grid.setColumnStretch(col, 1)
            self.checkbox_grid.addWidget(cb, 0, col)

        self.canvas.draw_idle()

    def _clear_axes(self):
        """Reset the three axes while keeping the spine layout consistent."""
        self.ax_pressure.clear()
        self.ax_flow.clear()
        self.ax_valves.clear()

        self.ax_flow.spines["right"].set_position(("axes", 1.22))
        self.ax_valves.spines["right"].set_position(("axes", 1.10))
        self.ax_flow.yaxis.set_label_position("right")
        self.ax_flow.yaxis.tick_right()
        self.ax_valves.yaxis.set_label_position("right")
        self.ax_valves.yaxis.tick_right()

    def reset_x_limits(self):
        """Clear stale plot content before a new measurement starts."""
        self._clear_axes()
        self.ax_pressure.set_xlabel("Time [s]")
        self.ax_pressure.set_ylabel("Pressure [mbar]")
        self.ax_pressure.set_xlim(0, 1)
        self.ax_pressure.grid(True, which="both", linestyle=":", linewidth=0.5)
        self.canvas.draw_idle()

    # -------- main render --------

    def update_plot(self):
        from itertools import cycle
    
        if len(self.time_data) < 2 or sampling_manager.start_timestamp is None:
            return
    
        # Clear axes
        self._clear_axes()
    
        # Helpers
        def minlen(*seqs):
            return min(len(s) for s in seqs if isinstance(s, (list, tuple, deque)))
    
        # Time base in seconds since run start
        time_rel = list(self.time_data)
    
        # --- Pressure curves ---
        color_cycle = cycle([
            "tab:blue", "tab:orange", "tab:green", "tab:red", "tab:purple",
            "tab:brown", "tab:pink", "tab:gray", "tab:olive", "tab:cyan"
        ])
    
        cb_target = self.checkboxes.get("Target")
        if cb_target and cb_target.isChecked():
            n = minlen(time_rel, self.target)
            if n > 0:
                self.ax_pressure.plot(time_rel[:n], list(self.target)[:n],
                                      label="Target", linestyle=":", color=next(color_cycle))
    
        cb_corr = self.checkboxes.get("Corrected")
        if cb_corr and cb_corr.isChecked():
            n = minlen(time_rel, self.corrected)
            if n > 0:
                self.ax_pressure.plot(time_rel[:n], list(self.corrected)[:n],
                                      label="Corrected", color=next(color_cycle))
    
        cb_meas = self.checkboxes.get("Measured")
        if cb_meas and cb_meas.isChecked():
            n = minlen(time_rel, self.measured)
            if n > 0:
                self.ax_pressure.plot(time_rel[:n], list(self.measured)[:n],
                                      label="Measured", linestyle="--", color=next(color_cycle))
    
        # Fluigent pressures
        for i, sensor in enumerate(self.fluigent_sensors):
            lab = f"SN{sensor.device_sn}"
            cb = self.checkboxes.get(lab)
            if cb and cb.isChecked():
                values = list(self.fluigent_pressure_data[i])
                n = minlen(time_rel, values)
                if n > 0:
                    self.ax_pressure.plot(time_rel[:n], values[:n], label=lab, color=next(color_cycle))
    
        # Pressure axis labels/limits
        self.ax_pressure.set_xlabel("Time [s]")
        self.ax_pressure.set_ylabel("Pressure [mbar]")
    
        all_pressures = list(self.corrected)
        for fp in self.fluigent_pressure_data:
            all_pressures += list(fp)
        if all_pressures:
            mn, mx = min(all_pressures), max(all_pressures)
            pad = 0.1 * max(1.0, abs(mx - mn))
            self.ax_pressure.set_ylim(mn - pad, mx + pad)
        else:
            self.ax_pressure.set_ylim(0, 100)
        # --- Draw rotary bands after the curve-based x/y limits are known ---
        cb_rv = self.checkboxes.get("Rotary")
        if cb_rv and cb_rv.isChecked():
            if self.rotary_events and len(self.rotary_events) > 0:
                # Event-based rendering: keep the band visible while the port remains active.
                self._draw_rotary_bands(self.ax_pressure, time_rel)
            else:
                # Fallback: sample-based rendering (None/0 means a gap).
                self._draw_rotary_active_full(time_rel)
    
        # --- Flows ---
        show_flows = any(
            (cb and cb.isChecked())
            for cb in (self.checkboxes.get(f"Flow {i+1}") for i in range(4))
        )

        if show_flows:
            self.ax_flow.spines["right"].set_visible(True)
            self.ax_flow.set_ylabel("Flow [uL/min]")
            self.ax_flow.yaxis.set_label_position("right")
            self.ax_flow.yaxis.tick_right()
            for i in range(4):
                key = f"Flow {i+1}"
                cb = self.checkboxes.get(key)
                if cb and cb.isChecked():
                    values = list(self.flow_sensors_data[i])
                    n = minlen(time_rel, values)
                    if n > 0:
                        self.ax_flow.plot(time_rel[:n], values[:n], label=key, color=next(color_cycle))
        else:
            self.ax_flow.spines["right"].set_visible(False)
            self.ax_flow.set_ylabel("")
            self.ax_flow.set_yticks([])

        # --- Valves ---
        show_valves = any((cb and cb.isChecked()) for cb in (self.checkboxes.get(f"V{i+1}") for i in range(8)))
        if show_valves:
            self.ax_valves.spines["right"].set_visible(True)
            self.ax_valves.set_ylabel("Valve State")
            self.ax_valves.yaxis.set_label_position('right')
            self.ax_valves.yaxis.tick_right()
            self.ax_valves.set_ylim(-0.1, 1.1)
            self.ax_valves.set_yticks([0, 1])
            for i in range(8):
                key = f"V{i+1}"
                cb = self.checkboxes.get(key)
                if cb and cb.isChecked():
                    series = [st[i] for st in self.valve_states if i < len(st)]
                    n = min(len(time_rel), len(series))
                    if n > 0:
                        label_text = cb.text() or key
                        color = self._rv_colors[i % len(self._rv_colors)]
                        self.ax_valves.plot(
                            time_rel[:n],
                            series[:n],
                            label=label_text,
                            drawstyle="steps-post",
                            color=color
                        )
        else:
            self.ax_valves.spines["right"].set_visible(False)
            self.ax_valves.set_ylabel("")
            self.ax_valves.set_yticks([])


    
        # Legend
        lines_labels = [ax.get_legend_handles_labels() for ax in
                        [self.ax_pressure, self.ax_flow, self.ax_valves]]
        lines, labels = [sum(x, []) for x in zip(*lines_labels)]
        if labels:
            self.figure.subplots_adjust(left=0.10, right=0.76, top=0.82, bottom=0.12)
            max_cols = 6
            ncol = min(len(labels), max_cols)
            self.ax_pressure.legend(
                lines, labels,
                loc="upper center", bbox_to_anchor=(0.5, 1.25),
                ncol=ncol, fontsize="small", frameon=False
            )
    
        # Grid and render
        self.ax_pressure.grid(True, which='both', linestyle=':', linewidth=0.5)
        self.ax_flow.grid(True, which='both', linestyle=':', linewidth=0.5)
        self.canvas.draw_idle()


    # -------- rotary band rendering --------

    def _draw_rotary_bands(self, ax, time_rel):
        """
        Build contiguous spans from self.rotary_events ([(t_rel_s, port)]) and draw them
        over the current x-axis viewport. port=0 creates a gap.
        There is no fixed time window; bands remain visible as long as the valve stays active.
        """
        if not self.rotary_events or len(time_rel) < 2:
            return
    
        tmin_data = time_rel[0]
        tmax_data = time_rel[-1]
        if tmax_data <= tmin_data:
            return
        # Read the visible range after the curves have set the limits.
        vis_min, vis_max = ax.get_xlim()
        # Clamp the viewport to the available data range.
        vis_min = max(vis_min, tmin_data)
        vis_max = min(vis_max, tmax_data)
        if vis_max <= vis_min:
            return
    
        events = list(self.rotary_events)
        if not events:
            return
        # Find the active port immediately before vis_min.
        active = 0
        for i in range(len(events) - 1, -1, -1):
            if events[i][0] <= vis_min:
                try:
                    active = int(events[i][1] or 0)
                except Exception:
                    active = 0
                break
        # Build spans from transition points inside the visible range.
        spans = []
        cur_t = vis_min
        cur_port = active
    
        for (te, pe) in events:
            if te < vis_min:
                continue
            if te > vis_max:
                break
            spans.append((cur_t, te, cur_port))
            cur_t = te
            try:
                cur_port = int(pe or 0)
            except Exception:
                cur_port = 0
    
        if cur_t < vis_max:
            spans.append((cur_t, vis_max, cur_port))
        # Draw only spans with an active port > 0.
        for (ta, tb, port) in spans:
            if port <= 0 or tb <= ta:
                continue
            color = self._rv_colors[(port - 1) % len(self._rv_colors)]
            ax.axvspan(ta, tb, ymin=0.0, ymax=1.0, color=color, alpha=0.15, zorder=0)
        # Add labels for longer segments.
        try:
            from matplotlib.transforms import blended_transform_factory
            trans = blended_transform_factory(ax.transData, ax.transAxes)
            for (ta, tb, port) in spans:
                if port > 0 and (tb - ta) >= 0.25:
                    xm = 0.5 * (ta + tb)
                    ax.text(xm, 0.98, f"{port}", transform=trans,
                            ha="center", va="top", fontsize=8, color="#333333", zorder=1)
        except Exception:
            pass



    def _draw_rotary_active_full(self, time_rel):
        """
        Draw colored backgrounds for contiguous phases of the same port using
        self.rotary_active (same length as time_data).
        Values: int>0 = port; None/0/other = gap (no color fill).
        """
        cb = self.checkboxes.get("Rotary")
        if not cb or not cb.isChecked():
            return
        if not self.rotary_active or len(time_rel) < 2:
            return
    
        rv = list(self.rotary_active)
        m = min(len(rv), len(time_rel))
        if m < 2:
            return
        rv, t = rv[:m], time_rel[:m]
        # Cast port values to int defensively; invalid values and None become 0 (gap).
        ports = []
        for v in rv:
            try:
                vv = int(v)
                ports.append(vv if vv > 0 else 0)
            except Exception:
                ports.append(0)
    
        from matplotlib.transforms import blended_transform_factory
        trans = blended_transform_factory(self.ax_pressure.transData, self.ax_pressure.transAxes)
    
        i = 0
        while i < m:
            v = ports[i]
            j = i + 1
            # Continue while the same port stays active.
            while j < m and ports[j] == v:
                j += 1
    
            if v > 0:
                t0 = t[i]
                # Use the timestamp after the segment as the end if available, otherwise the last sample.
                t1 = t[j] if j < m else t[-1]
                if t1 > t0:
                    color = self._rv_colors[(v - 1) % len(self._rv_colors)]
                    self.ax_pressure.axvspan(t0, t1, color=color, alpha=0.15, zorder=0)
                    # Label only longer segments.
                    if (t1 - t0) >= 0.25:
                        xc = 0.5 * (t0 + t1)
                        self.ax_pressure.text(
                            xc, 0.98, str(v),
                            transform=trans, ha="center", va="top",
                            fontsize=8, color="#333333", zorder=1
                        )
            i = j


    def set_valve_names(self, names):
        """
        Update checkbox labels (V1..V8) to the given names.
        'names' is a list of strings in valve index order.
        """
        try:
            for i in range(8):
                key = f"V{i+1}"
                cb = self.checkboxes.get(key)
                if cb and i < len(names) and names[i]:
                    cb.setText(str(names[i]))
        except Exception:
            pass



