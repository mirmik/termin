import importlib
import pytest


@pytest.mark.cpp
def test_cpp_suite():
    try:
        mod = importlib.import_module("termin.tests._cpp_tests")
    except ModuleNotFoundError:
        pytest.skip("C++ test module not built/installed")
    mod.run()
