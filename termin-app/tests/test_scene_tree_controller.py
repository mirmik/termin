from pathlib import Path

from tcgui.widgets.icon_button import IconButton
from tcgui.widgets.label import Label
from tcgui.widgets.tree import TreeNode, TreeWidget

from termin.editor_tcgui.scene_tree_controller import SceneTreeControllerTcgui
import termin.editor_tcgui.scene_tree_controller as scene_tree_module


def _node(text: str, *, expanded: bool = False) -> TreeNode:
    label = Label()
    label.text = text
    node = TreeNode(label)
    node.expanded = expanded
    return node


def test_scene_tree_collapse_all_button_collapses_tree() -> None:
    tree = TreeWidget()
    collapse_button = IconButton()
    controller = SceneTreeControllerTcgui(
        tree_widget=tree,
        scene=None,
        undo_handler=lambda _cmd, _merge: None,
        dialog_service=object(),
        on_object_selected=lambda _obj: None,
        collapse_all_button=collapse_button,
    )
    root = _node("Root", expanded=True)
    child = _node("Child", expanded=True)
    grandchild = _node("Grandchild", expanded=True)
    child.add_node(grandchild)
    root.add_node(child)
    tree.add_root(root)

    assert collapse_button.on_click is not None
    collapse_button.on_click()

    assert root.expanded is False
    assert child.expanded is False
    assert grandchild.expanded is False
    assert tree._dirty is True
    assert controller.get_expanded_entity_uuids() == []


def test_tcgui_scene_tree_is_only_a_shared_controller_projection() -> None:
    source = Path(scene_tree_module.__file__).read_text(encoding="utf-8")

    assert "SceneHierarchyController" in source
    assert "EntityOperations" not in source
