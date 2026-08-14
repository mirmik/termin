#include <termin/entity/input_handler.hpp>

namespace termin {

    void InputHandler::_cb_on_pointer(tc_component* c, tc_pointer_event* event) {
        if (!c || c->kind != TC_CXX_COMPONENT)
            return;

        CxxComponent* comp = CxxComponent::from_tc(c);
        if (!comp)
            return;

        InputHandler* handler = dynamic_cast<InputHandler*>(comp);
        if (!handler)
            return;

        handler->on_pointer(event);
    }

    void InputHandler::_cb_on_mouse_button(tc_component* c, tc_mouse_button_event* event) {
        if (!c || c->kind != TC_CXX_COMPONENT)
            return;

        CxxComponent* comp = CxxComponent::from_tc(c);
        if (!comp)
            return;

        InputHandler* handler = dynamic_cast<InputHandler*>(comp);
        if (!handler)
            return;

        handler->on_mouse_button(event);
    }

    void InputHandler::_cb_on_mouse_move(tc_component* c, tc_mouse_move_event* event) {
        if (!c || c->kind != TC_CXX_COMPONENT)
            return;

        CxxComponent* comp = CxxComponent::from_tc(c);
        if (!comp)
            return;

        InputHandler* handler = dynamic_cast<InputHandler*>(comp);
        if (!handler)
            return;

        handler->on_mouse_move(event);
    }

    void InputHandler::_cb_on_scroll(tc_component* c, tc_scroll_event* event) {
        if (!c || c->kind != TC_CXX_COMPONENT)
            return;

        CxxComponent* comp = CxxComponent::from_tc(c);
        if (!comp)
            return;

        InputHandler* handler = dynamic_cast<InputHandler*>(comp);
        if (!handler)
            return;

        handler->on_scroll(event);
    }

    void InputHandler::_cb_on_key(tc_component* c, tc_key_event* event) {
        if (!c || c->kind != TC_CXX_COMPONENT)
            return;

        CxxComponent* comp = CxxComponent::from_tc(c);
        if (!comp)
            return;

        InputHandler* handler = dynamic_cast<InputHandler*>(comp);
        if (!handler)
            return;

        handler->on_key(event);
    }

    void InputHandler::_cb_on_text(tc_component* c, tc_text_event* event) {
        if (!c || c->kind != TC_CXX_COMPONENT)
            return;
        CxxComponent* comp = CxxComponent::from_tc(c);
        InputHandler* handler = comp ? dynamic_cast<InputHandler*>(comp) : nullptr;
        if (handler)
            handler->on_text(event);
    }

    void InputHandler::_cb_on_focus_lost(tc_component* c, tc_input_focus_event* event) {
        if (!c || c->kind != TC_CXX_COMPONENT)
            return;
        CxxComponent* comp = CxxComponent::from_tc(c);
        InputHandler* handler = comp ? dynamic_cast<InputHandler*>(comp) : nullptr;
        if (handler)
            handler->on_focus_lost(event);
    }

    const tc_input_vtable InputHandler::cxx_input_vtable = {
        &InputHandler::_cb_on_pointer,
        &InputHandler::_cb_on_mouse_button,
        &InputHandler::_cb_on_mouse_move,
        &InputHandler::_cb_on_scroll,
        &InputHandler::_cb_on_key,
        &InputHandler::_cb_on_text,
        &InputHandler::_cb_on_focus_lost,
    };

} // namespace termin
