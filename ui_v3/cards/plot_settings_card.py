"""Plot channel settings card for the v3 GUI."""

from __future__ import annotations

from ui_v3.fluent_compat import CardWidget, PushButton, add_info_header, make_card_layout, stretch_row


class PlotSettingsCard(CardWidget):
    """Expose the live plot channel selector outside the plot surface."""

    def __init__(self, plot_panel, parent=None):
        super().__init__(parent)
        layout = make_card_layout(self)
        add_info_header(
            layout,
            "Plot Settings",
            "Select which pressure, flow, Fluigent, rotary, and valve channels are drawn in the live plot. "
            "Selections are saved with the local plot preferences and restored on the next start.",
        )
        pressure_button = PushButton("Pressure")
        sensors_button = PushButton("Pressure + Sensors")
        all_button = PushButton("All")
        clear_button = PushButton("Clear")

        pressure_button.setToolTip("Show target, corrected, and measured pressure traces.")
        sensors_button.setToolTip("Show pressure plus flow, Fluigent, and future sensor channels.")
        all_button.setToolTip("Show every available plot channel, including valves and rotary.")
        clear_button.setToolTip("Hide all plot channels.")

        pressure_button.clicked.connect(lambda _checked=False: plot_panel.apply_channel_preset("pressure"))
        sensors_button.clicked.connect(lambda _checked=False: plot_panel.apply_channel_preset("sensors"))
        all_button.clicked.connect(lambda _checked=False: plot_panel.apply_channel_preset("all"))
        clear_button.clicked.connect(lambda _checked=False: plot_panel.apply_channel_preset("clear"))

        layout.addWidget(stretch_row(pressure_button, sensors_button))
        layout.addWidget(stretch_row(all_button, clear_button))
        layout.addWidget(plot_panel.plot_settings_widget())
