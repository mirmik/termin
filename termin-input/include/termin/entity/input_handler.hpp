#pragma once

#include "core/tc_input_component.h"
#include <termin/entity/component.hpp>
#include <termin_input/export.hpp>

struct tc_mouse_button_event;
struct tc_mouse_move_event;
struct tc_scroll_event;
struct tc_key_event;

namespace termin {

class TERMIN_INPUT_API InputHandler {
public:
    virtual ~InputHandler() = default;

    virtual void on_mouse_button(tc_mouse_button_event* event) {}
    virtual void on_mouse_move(tc_mouse_move_event* event) {}
    virtual void on_scroll(tc_scroll_event* event) {}
    virtual void on_key(tc_key_event* event) {}

    static const tc_input_vtable cxx_input_vtable;

protected:
    void install_input_vtable(tc_component* c) {
        if (c) {
            tc_input_capability_attach(c, &cxx_input_vtable);
        }
    }

private:
    static void _cb_on_mouse_button(tc_component* c, tc_mouse_button_event* event);
    static void _cb_on_mouse_move(tc_component* c, tc_mouse_move_event* event);
    static void _cb_on_scroll(tc_component* c, tc_scroll_event* event);
    static void _cb_on_key(tc_component* c, tc_key_event* event);
};

} // namespace termin
