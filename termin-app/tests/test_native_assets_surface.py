import importlib

import pytest


@pytest.mark.parametrize(
    "module_name",
    [
        "termin._native",
        "termin._native.assets",
        "termin._native.scene",
        "termin._native.skeleton",
    ],
)
def test_empty_app_native_compat_submodules_are_removed(module_name: str) -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module_name)
