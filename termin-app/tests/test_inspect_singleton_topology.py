from termin.inspect import _inspect_native as inspect_canonical


def test_inspect_singleton_topology_addresses():
    inspect_addr_canonical = inspect_canonical.inspect_registry_address()
    assert inspect_addr_canonical != 0

    kind_addr_canonical = inspect_canonical.kind_registry_cpp_address()
    assert kind_addr_canonical != 0


def test_python_component_without_own_fields_inherits_base_inspect_fields():
    from termin.inspect import InspectRegistry, TypeBackend
    from termin.scene import PythonComponent

    registry = InspectRegistry.instance()
    registry.unregister_type("NoOwnInspectFieldsProbeComponent")

    class NoOwnInspectFieldsProbeComponent(PythonComponent):
        pass

    field_paths = {field.path for field in registry.all_fields("NoOwnInspectFieldsProbeComponent")}

    assert registry.has_type("PythonComponent")
    assert registry.has_type("NoOwnInspectFieldsProbeComponent")
    assert registry.get_type_parent("NoOwnInspectFieldsProbeComponent") == "PythonComponent"
    assert registry.get_type_backend("NoOwnInspectFieldsProbeComponent") == TypeBackend.Python
    assert "enabled" in field_paths
