def test_python_component_metadata_is_registered() -> None:
    from termin.scene import ComponentRegistry, PythonComponent

    class MetadataProbeComponent(PythonComponent):
        component_category = "Gameplay"
        component_display_name = "Metadata Probe"

    registry = ComponentRegistry.instance()
    try:
        info = registry.get_info("MetadataProbeComponent")

        assert info["category"] == "Gameplay"
        assert info["display_name"] == "Metadata Probe"
        assert info["kind"] == "python"
        assert not info["is_abstract"]
    finally:
        registry.unregister_python("MetadataProbeComponent")


def test_python_component_category_inherits_from_base() -> None:
    from termin.scene import ComponentRegistry, PythonComponent

    class MetadataProbeBaseComponent(PythonComponent):
        component_category = "Gameplay"

    class MetadataProbeDerivedComponent(MetadataProbeBaseComponent):
        pass

    registry = ComponentRegistry.instance()
    try:
        info = registry.get_info("MetadataProbeDerivedComponent")

        assert info["category"] == "Gameplay"
        assert info["display_name"] == "Metadata Probe Derived Component"
    finally:
        registry.unregister_python("MetadataProbeDerivedComponent")
        registry.unregister_python("MetadataProbeBaseComponent")
