import importlib
import pytest

@pytest.mark.skip(reason="C++ test module not built (BUILD_TESTS=OFF)")
def test_cpp_suite():
    mod = importlib.import_module("termin.tests._cpp_tests")
    mod.run()
