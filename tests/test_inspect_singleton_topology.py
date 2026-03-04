from termin._native import inspect as inspect_native
from termin.entity import _entity_native


def test_inspect_singleton_topology_addresses():
    inspect_addr_native = inspect_native.inspect_registry_address()
    inspect_addr_entity = _entity_native._inspect_registry_address()
    assert inspect_addr_native != 0
    assert inspect_addr_entity != 0
    assert inspect_addr_native == inspect_addr_entity

    kind_addr_native = inspect_native.kind_registry_cpp_address()
    kind_addr_entity = _entity_native._kind_registry_cpp_address()
    assert kind_addr_native != 0
    assert kind_addr_entity != 0
    assert kind_addr_native == kind_addr_entity
