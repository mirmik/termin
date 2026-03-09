// input_handler.cpp - InputHandler vtable implementation
// Note: tc_input_event.h types are forward-declared in the header.
// This .cpp needs the full definitions, so the consumer (termin/cpp)
// must ensure core_c include path is available at build time.

#include <termin/entity/input_handler.hpp>

// We need the full event struct definitions for the callback implementations.
// These are provided by the consumer's include path (core_c).
// If building termin-scene standalone without core_c, input_handler
// callbacks will use only the pointer (no struct member access needed
// since we just forward to virtual methods).

namespace termin {

// Static callback implementations for input vtable

void InputHandler::_cb_on_mouse_button(tc_component* c, tc_mouse_button_event* event) {
    if (!c || c->kind != TC_CXX_COMPONENT) return;

    CxxComponent* comp = CxxComponent::from_tc(c);
    if (!comp) return;

    InputHandler* handler = dynamic_cast<InputHandler*>(comp);
    if (!handler) return;

    handler->on_mouse_button(event);
}

void InputHandler::_cb_on_mouse_move(tc_component* c, tc_mouse_move_event* event) {
    if (!c || c->kind != TC_CXX_COMPONENT) return;

    CxxComponent* comp = CxxComponent::from_tc(c);
    if (!comp) return;

    InputHandler* handler = dynamic_cast<InputHandler*>(comp);
    if (!handler) return;

    handler->on_mouse_move(event);
}

void InputHandler::_cb_on_scroll(tc_component* c, tc_scroll_event* event) {
    if (!c || c->kind != TC_CXX_COMPONENT) return;

    CxxComponent* comp = CxxComponent::from_tc(c);
    if (!comp) return;

    InputHandler* handler = dynamic_cast<InputHandler*>(comp);
    if (!handler) return;

    handler->on_scroll(event);
}

void InputHandler::_cb_on_key(tc_component* c, tc_key_event* event) {
    if (!c || c->kind != TC_CXX_COMPONENT) return;

    CxxComponent* comp = CxxComponent::from_tc(c);
    if (!comp) return;

    InputHandler* handler = dynamic_cast<InputHandler*>(comp);
    if (!handler) return;

    handler->on_key(event);
}

// Static vtable instance
const tc_input_vtable InputHandler::cxx_input_vtable = {
    &InputHandler::_cb_on_mouse_button,
    &InputHandler::_cb_on_mouse_move,
    &InputHandler::_cb_on_scroll,
    &InputHandler::_cb_on_key
};

} // namespace termin
