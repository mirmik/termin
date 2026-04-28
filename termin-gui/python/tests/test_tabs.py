from tcgui.widgets.tabs import TabView

from .conftest import VIEWPORT_H, VIEWPORT_W, make_widget


def test_tab_view_on_changed_fires_when_selected_index_changes():
    tabs = TabView()
    first = make_widget(stretch=True)
    second = make_widget(stretch=True)
    changes: list[int] = []

    tabs.add_tab("First", first)
    tabs.add_tab("Second", second)
    tabs.layout(0, 0, 400, 300, VIEWPORT_W, VIEWPORT_H)
    tabs.on_changed = changes.append

    tabs.selected_index = 1

    assert changes == [1]
    assert first.visible is False
    assert second.visible is True


def test_tab_view_on_changed_does_not_fire_when_index_is_unchanged():
    tabs = TabView()
    tabs.add_tab("First", make_widget(stretch=True))
    changes: list[int] = []
    tabs.on_changed = changes.append

    tabs.selected_index = 0

    assert changes == []
