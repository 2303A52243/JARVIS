"""Sree Industries Holographic HUD Interface for JARVIS OS.

Alias module providing full access to the Sree Industries HUD Home Panel and widgets.
"""

from ui.hud_home_panel import JarvisHudHomePanel
from ui.components.hud_widgets import (
    HudFrame,
    WaveformGraphWidget,
    CircularDriveGauge,
    DigitalClockWeatherWidget,
    JarvisOsBadgeWidget,
    SreeBottomBanner,
    StarkBottomBanner,
)

__all__ = [
    "JarvisHudHomePanel",
    "HudFrame",
    "WaveformGraphWidget",
    "CircularDriveGauge",
    "DigitalClockWeatherWidget",
    "JarvisOsBadgeWidget",
    "SreeBottomBanner",
    "StarkBottomBanner",
]
