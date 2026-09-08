// editor_viewport_input_manager.hpp - Per-viewport input manager for editor mode
// Dispatches events to camera/scene components and delegates
// picking/gizmo/selection to EditorInteractionSystem singleton.
#pragma once

#include "core/tc_component.h"
#include "core/tc_scene.h"
#include "render/tc_display.h"
#include "render/tc_input_manager.h"
#include "render/tc_viewport.h"
#include "termin/input/input_events.hpp"

#include <unordered_set>

namespace termin {

    class EditorInteractionSystem;

    class EditorViewportInputManager {
    public:
        tc_input_manager _tc_im;
        tc_viewport_handle _viewport = TC_VIEWPORT_HANDLE_INVALID;
        tc_display_handle _display = TC_DISPLAY_HANDLE_INVALID;

    private:
        enum class PointerOwnerKind {
            None,
            InternalComponent,
            SceneComponent,
            EditorInteraction,
        };

        struct PointerOwner {
            PointerOwnerKind kind = PointerOwnerKind::None;
            tc_component* component = nullptr;
            tc_entity_handle entity = TC_ENTITY_HANDLE_INVALID;
            EditorInteractionSystem* interaction = nullptr;
            int button = -1;
        };

        double _last_cursor_x = 0.0;
        double _last_cursor_y = 0.0;
        bool _has_cursor = false;
        int _current_mods = 0;
        PointerOwner _pointer_owner;
        std::unordered_set<int> _cancelled_pointer_buttons;

        static tc_input_manager_vtable _vtable;

    public:
        EditorViewportInputManager(tc_viewport_handle viewport, tc_display_handle display);
        ~EditorViewportInputManager();

        bool rebind(tc_viewport_handle viewport, tc_display_handle display);
        void detach();

        tc_input_manager* tc_input_manager_ptr() {
            return &_tc_im;
        }
        tc_viewport_handle viewport() const {
            return _viewport;
        }
        tc_display_handle display() const {
            return _display;
        }

        // vtable event handlers
        void on_mouse_button(int button, int action, int mods, uint32_t click_count);
        void on_mouse_move(double x, double y);
        void on_scroll(double xoffset, double yoffset, int mods);
        void on_key(int key, int scancode, int action, int mods);
        void on_text(const char* text_utf8);
        void on_focus_lost();

    private:
        // Dispatch to scene components opted into editor input source.
        PointerOwner _dispatch_to_editor_components(tc_mouse_button_event* ev);
        void _dispatch_to_editor_components(tc_mouse_move_event* ev);
        void _dispatch_to_editor_components(tc_scroll_event* ev);
        void _dispatch_to_editor_components(tc_key_event* ev);
        void _dispatch_to_editor_components(tc_text_event* ev);
        void _dispatch_to_editor_components(tc_input_focus_event* ev);

        // Dispatch to viewport's internal entities
        PointerOwner _dispatch_to_internal_entities(tc_mouse_button_event* ev);
        void _dispatch_to_internal_entities(tc_mouse_move_event* ev);
        void _dispatch_to_internal_entities(tc_scroll_event* ev);
        void _dispatch_to_internal_entities(tc_key_event* ev);
        void _dispatch_to_internal_entities(tc_text_event* ev);
        void _dispatch_to_internal_entities(tc_input_focus_event* ev);
        tc_component* _resolve_pointer_component(const PointerOwner& owner) const;
        bool _dispatch_to_pointer_owner(const PointerOwner& owner, tc_mouse_button_event* ev);
        bool _dispatch_to_pointer_owner(const PointerOwner& owner, tc_mouse_move_event* ev);
        void _quarantine_pointer_owner(const char* reason);
    };

} // namespace termin
