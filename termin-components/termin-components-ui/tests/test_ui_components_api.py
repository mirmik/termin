from termin.ui_components import UIComponent


def test_ui_component_is_exported_from_canonical_package() -> None:
    assert UIComponent.__name__ == "UIComponent"
