// selection_manager.hpp - Tracks selected and hovered entities
#pragma once

#include "termin/entity/entity.hpp"
#include <cstdint>
#include <functional>

namespace termin {

class SelectionManager {
public:
    uint32_t selected_pick_id = 0;
    uint32_t hovered_pick_id = 0;

private:
    Entity _selected;
    Entity _hovered;

public:
    std::function<void(Entity)> on_selection_changed;
    std::function<void(Entity)> on_hover_changed;

public:
    SelectionManager() = default;

    Entity selected() const { return _selected; }
    Entity hovered() const { return _hovered; }

    void select(Entity entity) {
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

    void hover(Entity entity) {
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

    void clear() {
        select(Entity());
        hover(Entity());
    }

    void deselect() {
        select(Entity());
    }
};

} // namespace termin
