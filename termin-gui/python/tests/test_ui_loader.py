"""UILoader YAML attribute tests."""

import pytest

from tcgui.widgets.button import Button
from tcgui.widgets.containers import HStack
from tcgui.widgets.loader import UILoader
from tcgui.widgets.menu import Menu
from tcgui.widgets.status_bar import StatusBar
from tcgui.widgets.tabs import TabView
from tcgui.widgets.tree import TreeNode, TreeWidget


def test_loader_applies_declarative_widget_attributes() -> None:
    root = UILoader().load_string(
        """
        type: HStack
        spacing: 12
        alignment: center
        justify: end
        children:
          - type: Button
            text: Run
            background_color: "#112233"
            font_size: 18
            padding: 6
        """
    )

    assert isinstance(root, HStack)
    assert root.spacing == 12.0
    assert root.alignment == "center"
    assert root.justify == "end"

    button = root.children[0]
    assert isinstance(button, Button)
    assert button.text == "Run"
    assert button.background_color == pytest.approx((17 / 255, 34 / 255, 51 / 255, 1.0))
    assert button.font_size == 18.0
    assert button.padding == 6.0


def test_loader_applies_structural_hooks() -> None:
    root = UILoader().load_string(
        """
        type: HStack
        children:
          - type: TreeWidget
            nodes:
              - type: TreeNode
                expanded: false
                content:
                  type: Button
                  text: Node
          - type: TabView
            tabs:
              - title: First
                content:
                  type: Button
                  text: Tab Button
          - type: Menu
            items:
              - label: Open
                shortcut: Ctrl+O
              - "---"
              - label: Disabled
                enabled: false
          - type: StatusBar
            text: Ready
        """
    )

    tree = root.children[0]
    assert isinstance(tree, TreeWidget)
    assert len(tree.root_nodes) == 1
    assert tree.root_nodes[0].expanded is False
    assert isinstance(tree.root_nodes[0].content, Button)
    assert tree.root_nodes[0].content.text == "Node"

    tabs = root.children[1]
    assert isinstance(tabs, TabView)
    assert tabs.tab_bar.tabs == ["First"]
    assert isinstance(tabs.pages[0], Button)
    assert tabs.pages[0].text == "Tab Button"

    menu = root.children[2]
    assert isinstance(menu, Menu)
    assert [item.separator for item in menu.items] == [False, True, False]
    assert menu.items[0].shortcut == "Ctrl+O"
    assert menu.items[2].enabled is False

    status = root.children[3]
    assert isinstance(status, StatusBar)
    assert status.text == "Ready"


def test_loader_rejects_unsupported_builtin_attribute() -> None:
    with pytest.raises(ValueError, match="Unsupported attribute.*Button.*texxt"):
        UILoader().load_string(
            """
            type: Button
            texxt: typo
            """
        )
