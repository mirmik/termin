#include "selection_manager.hpp"

namespace termin {

void SelectionManager::select(Entity entity) {
    if (!entity.valid() || !entity.selectable()) {
        entity = Entity();
    }

    if (entity == _selected) {
        return;
    }

    _selected = entity;
    selected_pick_id = entity.valid() ? entity.pick_id() : 0;

    if (on_selection_changed) {
        on_selection_changed(entity);
    }
}

void SelectionManager::hover(Entity entity) {
    if (!entity.valid() || !entity.selectable()) {
        entity = Entity();
    }

    if (entity == _hovered) {
        return;
    }

    _hovered = entity;
    hovered_pick_id = entity.valid() ? entity.pick_id() : 0;

    if (on_hover_changed) {
        on_hover_changed(entity);
    }
}

void SelectionManager::clear() {
    select(Entity());
    hover(Entity());
}

void SelectionManager::deselect() {
    select(Entity());
}

} // namespace termin
