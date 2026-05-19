"""Compatibility re-export for asset plugin preload adapter.

New code should import from termin.assets.plugin_preloader.
"""

from termin.assets.plugin_preloader import PluginPreLoader

__all__ = ["PluginPreLoader"]
