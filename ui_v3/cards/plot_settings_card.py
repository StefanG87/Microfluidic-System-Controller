"""Plot channel settings card for the v3 GUI."""

from __future__ import annotations

from ui_v3.fluent_compat import CardWidget, add_info_header, make_card_layout


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
        layout.addWidget(plot_panel.plot_settings_widget())
