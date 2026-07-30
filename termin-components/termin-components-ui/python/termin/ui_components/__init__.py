"""Native UI scene components."""

from termin_nanobind.runtime import preload_sdk_libs

preload_sdk_libs("nanobind", "termin_components_ui")

from termin.ui_components.component import UIComponent  # noqa: E402

__all__ = ["UIComponent"]
