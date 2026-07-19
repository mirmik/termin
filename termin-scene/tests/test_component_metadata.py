import pytest


def _owned_component_type(type_name, owner, category, display_name):
    from termin.scene import PythonComponent, publish_python_component
    from termin_modules.module_context import (
        register_module_packages,
        unregister_module_packages,
    )

    package = f"tests.component_owner.{owner}"
    register_module_packages(owner, [package])
    try:
        cls = type(
            type_name,
            (PythonComponent,),
            {
                "__module__": package,
                "component_category": category,
                "component_display_name": display_name,
            },
        )
        publish_python_component(cls, owner=owner)
        return cls
    finally:
        unregister_module_packages(owner)


@pytest.fixture(scope="module", autouse=True)
def _component_runtime():
    import termin.bootstrap

    termin.bootstrap.bootstrap_player()
    yield
    termin.bootstrap.shutdown_player()


def test_python_component_metadata_is_registered() -> None:
    from termin.scene import ComponentRegistry, PythonComponent, publish_python_component

    class MetadataProbeComponent(PythonComponent):
        component_category = "Gameplay"
        component_display_name = "Metadata Probe"

    publish_python_component(MetadataProbeComponent)

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
    from termin.scene import ComponentRegistry, PythonComponent, publish_python_component

    class MetadataProbeBaseComponent(PythonComponent):
        component_category = "Gameplay"

    class MetadataProbeDerivedComponent(MetadataProbeBaseComponent):
        pass

    publish_python_component(MetadataProbeDerivedComponent)

    registry = ComponentRegistry.instance()
    try:
        info = registry.get_info("MetadataProbeDerivedComponent")

        assert info["category"] == "Gameplay"
        assert info["display_name"] == "Metadata Probe Derived Component"
    finally:
        registry.unregister_python("MetadataProbeDerivedComponent")
        registry.unregister_python("MetadataProbeBaseComponent")


def test_python_component_requirements_are_registered() -> None:
    from termin.scene import ComponentRegistry, PythonComponent, publish_python_components

    class RequiredMetadataProbeComponent(PythonComponent):
        pass

    class DependentMetadataProbeComponent(PythonComponent):
        required_components = ("RequiredMetadataProbeComponent",)

    publish_python_components(
        [RequiredMetadataProbeComponent, DependentMetadataProbeComponent],
        owner="termin-scene-python",
    )

    registry = ComponentRegistry.instance()
    try:
        assert registry.requirements_of("DependentMetadataProbeComponent") == [
            "RequiredMetadataProbeComponent"
        ]
    finally:
        registry.unregister_python("DependentMetadataProbeComponent")
        registry.unregister_python("RequiredMetadataProbeComponent")


def test_ownerless_python_component_descriptor_is_rejected() -> None:
    from termin.scene import ComponentRegistry

    registry = ComponentRegistry.instance()
    assert not registry.register_python(
        "OwnerlessPythonComponent",
        object,
        "",
        "PythonComponent",
        {},
        {},
        "Project",
        "Ownerless",
        [],
        [],
    )
    assert not registry.has("OwnerlessPythonComponent")


def test_same_owner_python_component_reload_replaces_factory_and_metadata() -> None:
    from termin.scene import ComponentRegistry

    registry = ComponentRegistry.instance()
    type_name = "DuplicateOwnedPythonComponent"
    owner = "component-registration-reload-test"
    first = _owned_component_type(
        type_name, owner, "First Category", "First Display Name"
    )
    try:
        second = _owned_component_type(
            type_name, owner, "Second Category", "Second Display Name"
        )

        assert registry.get_class(type_name) is second
        assert registry.get_class(type_name) is not first
        info = registry.get_info(type_name)
        assert info["category"] == "Second Category"
        assert info["display_name"] == "Second Display Name"
    finally:
        registry.unregister_python(type_name)


def test_cross_owner_python_component_collision_preserves_existing_registration() -> None:
    from termin.scene import ComponentRegistry

    registry = ComponentRegistry.instance()
    type_name = "DuplicateCrossOwnerPythonComponent"
    first = _owned_component_type(
        type_name,
        "component-registration-first-owner",
        "First Category",
        "First Display Name",
    )
    try:
        with pytest.raises(RuntimeError, match="another component owns"):
            _owned_component_type(
                type_name,
                "component-registration-second-owner",
                "Second Category",
                "Second Display Name",
            )

        assert registry.get_class(type_name) is first
        info = registry.get_info(type_name)
        assert info["category"] == "First Category"
        assert info["display_name"] == "First Display Name"
    finally:
        registry.unregister_python(type_name)
