from termin.inspect import _inspect_native as inspect_canonical


def test_inspect_singleton_topology_addresses():
    inspect_addr_canonical = inspect_canonical.inspect_registry_address()
    assert inspect_addr_canonical != 0

    kind_addr_canonical = inspect_canonical.kind_registry_cpp_address()
    assert kind_addr_canonical != 0
