import importlib

import pytest


@pytest.mark.parametrize(
    "module_name",
    [
        "termin._native.assets",
        "termin._native.scene",
        "termin._native.skeleton",
    ],
)
def test_empty_app_native_compat_submodules_are_removed(module_name: str) -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module_name)


def test_app_native_compat_aliases_are_removed() -> None:
    import termin._native as native

    removed_names = {
        "component",
        "editor",
        "geom",
        "graphics",
        "log",
        "mesh",
        "modules",
        "profiler",
        "render",
        "tgfx",
        "viewport",
        "_cleanup_python_objects",
    }

    assert removed_names.isdisjoint(dir(native))
