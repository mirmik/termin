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


def test_rejected_unowned_python_component_collision_preserves_existing_metadata() -> None:
    from termin.scene import ComponentRegistry, PythonComponent

    registry = ComponentRegistry.instance()
    type_name = "DuplicateUnownedPythonComponent"
    registry.set_registration_owner("")
    first = type(
        type_name,
        (PythonComponent,),
        {
            "component_category": "First Category",
            "component_display_name": "First Display Name",
        },
    )
    try:
        second = type(
            type_name,
            (PythonComponent,),
            {
                "component_category": "Second Category",
                "component_display_name": "Second Display Name",
            },
        )

        assert registry.get_class(type_name) is first
        assert registry.get_class(type_name) is not second
        info = registry.get_info(type_name)
        assert info["category"] == "First Category"
        assert info["display_name"] == "First Display Name"
    finally:
        registry.unregister_python(type_name)


def test_same_owner_python_component_reload_replaces_factory_and_metadata() -> None:
    from termin.scene import ComponentRegistry, PythonComponent

    registry = ComponentRegistry.instance()
    type_name = "DuplicateOwnedPythonComponent"
    owner = "component-registration-reload-test"
    registry.set_registration_owner(owner)
    first = type(
        type_name,
        (PythonComponent,),
        {
            "component_category": "First Category",
            "component_display_name": "First Display Name",
        },
    )
    try:
        second = type(
            type_name,
            (PythonComponent,),
            {
                "component_category": "Second Category",
                "component_display_name": "Second Display Name",
            },
        )

        assert registry.get_class(type_name) is second
        assert registry.get_class(type_name) is not first
        info = registry.get_info(type_name)
        assert info["category"] == "Second Category"
        assert info["display_name"] == "Second Display Name"
    finally:
        registry.unregister_python(type_name)
        registry.set_registration_owner("")


def test_cross_owner_python_component_collision_preserves_existing_registration() -> None:
    from termin.scene import ComponentRegistry, PythonComponent

    registry = ComponentRegistry.instance()
    type_name = "DuplicateCrossOwnerPythonComponent"
    registry.set_registration_owner("component-registration-first-owner")
    first = type(
        type_name,
        (PythonComponent,),
        {
            "component_category": "First Category",
            "component_display_name": "First Display Name",
        },
    )
    try:
        registry.set_registration_owner("component-registration-second-owner")
        second = type(
            type_name,
            (PythonComponent,),
            {
                "component_category": "Second Category",
                "component_display_name": "Second Display Name",
            },
        )

        assert registry.get_class(type_name) is first
        assert registry.get_class(type_name) is not second
        info = registry.get_info(type_name)
        assert info["category"] == "First Category"
        assert info["display_name"] == "First Display Name"
    finally:
        registry.unregister_python(type_name)
        registry.set_registration_owner("")
