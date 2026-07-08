from tcgui.widgets.menu import MenuItem

from termin.editor_tcgui.entity_inspector import _build_add_component_menu_items


def test_add_component_menu_groups_components_by_category() -> None:
    added = []
    items = _build_add_component_menu_items(
        [
            {
                "name": "MeshRenderer",
                "display_name": "Mesh Renderer",
                "category": "Rendering",
                "is_abstract": False,
            },
            {
                "name": "PlayerController",
                "display_name": "Player Controller",
                "category": "Project",
                "is_abstract": False,
            },
            {
                "name": "AbstractBase",
                "display_name": "Abstract Base",
                "category": "Project",
                "is_abstract": True,
            },
        ],
        added.append,
    )

    assert [item.label for item in items] == ["Rendering", "Project"]
    rendering_submenu = items[0].submenu
    project_submenu = items[1].submenu
    assert isinstance(rendering_submenu, list)
    assert isinstance(project_submenu, list)
    assert all(isinstance(item, MenuItem) for item in rendering_submenu)
    assert all(isinstance(item, MenuItem) for item in project_submenu)

    assert rendering_submenu[0].label == "Mesh Renderer"
    assert project_submenu[0].label == "Player Controller"

    assert rendering_submenu[0].on_click is not None
    rendering_submenu[0].on_click()

    assert added == ["MeshRenderer"]
