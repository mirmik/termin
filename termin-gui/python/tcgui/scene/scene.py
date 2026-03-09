"""Scene container for graphics items."""

from __future__ import annotations

from tcgui.scene.item import GraphicsItem, SceneTransform


class GraphicsScene:
    """Holds top-level graphics items and selection state."""

    def __init__(self) -> None:
        self.items: list[GraphicsItem] = []
        self.selected_items: list[GraphicsItem] = []

    def add_item(self, item: GraphicsItem) -> GraphicsItem:
        item.parent = None
        self.items.append(item)
        return item

    def remove_item(self, item: GraphicsItem) -> None:
        if item in self.items:
            if item in self.selected_items:
                self.selected_items.remove(item)
            self.items.remove(item)

    def clear(self) -> None:
        self.items.clear()
        self.selected_items.clear()

    def hit_test(self, wx: float, wy: float) -> GraphicsItem | None:
        for item in sorted(self.items, key=lambda i: i.z_index, reverse=True):
            hit = item.hit_test(wx, wy)
            if hit is not None:
                return hit
        return None

    def clear_selection(self) -> None:
        for item in self.selected_items:
            item.selected = False
        self.selected_items.clear()

    def set_selected(self, item: GraphicsItem | None) -> None:
        self.clear_selection()
        if item is None or not item.selectable:
            return
        item.selected = True
        self.selected_items.append(item)

    def toggle_selected(self, item: GraphicsItem | None) -> None:
        if item is None or not item.selectable:
            return
        if item in self.selected_items:
            item.selected = False
            self.selected_items.remove(item)
            return
        item.selected = True
        self.selected_items.append(item)

    def render(self, renderer, transform: SceneTransform) -> None:
        for item in sorted(self.items, key=lambda i: i.z_index):
            item.render(renderer, transform)
