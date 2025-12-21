import importlib
import pytest

def test_cpp_suite():
    mod = importlib.import_module("termin.tests._cpp_tests")
    mod.run()
