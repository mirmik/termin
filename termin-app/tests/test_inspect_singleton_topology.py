from termin.inspect import _inspect_native as inspect_canonical
from termin import _native


def test_inspect_singleton_topology_addresses():
    """Verify that singleton addresses returned by canonical inspect and _native are consistent."""
    inspect_addr_canonical = inspect_canonical.inspect_registry_address()
    inspect_addr_from_main = _native._inspect_registry_address()
    assert inspect_addr_canonical != 0
    assert inspect_addr_from_main != 0
    assert inspect_addr_canonical == inspect_addr_from_main

    kind_addr_canonical = inspect_canonical.kind_registry_cpp_address()
    kind_addr_from_main = _native._kind_registry_cpp_address()
    assert kind_addr_canonical != 0
    assert kind_addr_from_main != 0
    assert kind_addr_canonical == kind_addr_from_main
