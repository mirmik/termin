from termin._native import inspect as inspect_native
from termin import _native


def test_inspect_singleton_topology_addresses():
    """Verify that singleton addresses returned by _native and its inspect submodule are consistent."""
    inspect_addr_native = inspect_native.inspect_registry_address()
    inspect_addr_from_main = _native._inspect_registry_address()
    assert inspect_addr_native != 0
    assert inspect_addr_from_main != 0
    assert inspect_addr_native == inspect_addr_from_main

    kind_addr_native = inspect_native.kind_registry_cpp_address()
    kind_addr_from_main = _native._kind_registry_cpp_address()
    assert kind_addr_native != 0
    assert kind_addr_from_main != 0
    assert kind_addr_native == kind_addr_from_main
