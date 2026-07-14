#include "guard_main.h"

#include "termin/editor/selection_manager.hpp"

namespace {

termin::Entity make_entity(const char* name) {
    return termin::Entity::create(termin::Entity::standalone_pool_handle(), name);
}

} // namespace

TEST_CASE("SelectionManager normalizes selection and hover state")
{
    termin::SelectionManager selection;
    termin::Entity selected = make_entity("selected");
    termin::Entity unselectable = make_entity("unselectable");
    unselectable.set_selectable(false);

    int selection_changes = 0;
    int hover_changes = 0;
    selection.on_selection_changed = [&](termin::Entity) { ++selection_changes; };
    selection.on_hover_changed = [&](termin::Entity) { ++hover_changes; };

    selection.select(selected);
    selection.hover(selected);
    CHECK(selection.selected() == selected);
    CHECK(selection.hovered() == selected);
    CHECK_EQ(selection.selected_pick_id, selected.pick_id());
    CHECK_EQ(selection.hovered_pick_id, selected.pick_id());

    selection.select(selected);
    selection.hover(selected);
    CHECK_EQ(selection_changes, 1);
    CHECK_EQ(hover_changes, 1);

    selection.select(unselectable);
    selection.hover(unselectable);
    CHECK(!selection.selected().valid());
    CHECK(!selection.hovered().valid());
    CHECK_EQ(selection.selected_pick_id, 0U);
    CHECK_EQ(selection.hovered_pick_id, 0U);
    CHECK_EQ(selection_changes, 2);
    CHECK_EQ(hover_changes, 2);
}

TEST_CASE("SelectionManager deselect and clear notify only changed state")
{
    termin::SelectionManager selection;
    termin::Entity entity = make_entity("entity");
    int selection_changes = 0;
    int hover_changes = 0;
    selection.on_selection_changed = [&](termin::Entity) { ++selection_changes; };
    selection.on_hover_changed = [&](termin::Entity) { ++hover_changes; };

    selection.select(entity);
    selection.hover(entity);
    selection.deselect();
    selection.deselect();
    CHECK(!selection.selected().valid());
    CHECK(selection.hovered().valid());
    CHECK_EQ(selection_changes, 2);
    CHECK_EQ(hover_changes, 1);

    selection.clear();
    selection.clear();
    CHECK(!selection.selected().valid());
    CHECK(!selection.hovered().valid());
    CHECK_EQ(selection.selected_pick_id, 0U);
    CHECK_EQ(selection.hovered_pick_id, 0U);
    CHECK_EQ(selection_changes, 2);
    CHECK_EQ(hover_changes, 2);
}
