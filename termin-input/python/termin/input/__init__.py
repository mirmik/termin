# termin.input - input handling
from termin_nanobind.runtime import preload_sdk_libs

preload_sdk_libs("termin_input")

from termin.input.input_component import InputComponent

__all__ = ["InputComponent"]
