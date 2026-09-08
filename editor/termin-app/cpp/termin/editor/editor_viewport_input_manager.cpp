// editor_viewport_input_manager.cpp - Per-viewport input manager for editor mode

#include "termin/editor/editor_viewport_input_manager.hpp"
#include "core/tc_entity_pool.h"
#include "core/tc_input_entity_pool.h"
#include "core/tc_input_scene.h"
#include "render/tc_viewport.h"
#include "render/tc_viewport_pool.h"
#include "termin/editor/editor_interaction_system.hpp"
#include <tcbase/tc_log.h>

namespace termin {

    // Vtable callback wrappers
    static void editor_on_text(tc_input_manager* m, const char* text_utf8);

    static void editor_on_mouse_button(tc_input_manager* m, int button, int action, int mods, uint32_t click_count) {
        if (m && m->userdata) {
            static_cast<EditorViewportInputManager*>(m->userdata)->on_mouse_button(button, action, mods, click_count);
        }
    }

    static void editor_on_mouse_move(tc_input_manager* m, double x, double y) {
        if (m && m->userdata) {
            static_cast<EditorViewportInputManager*>(m->userdata)->on_mouse_move(x, y);
        }
    }

    static void editor_on_scroll(tc_input_manager* m, double x, double y, int mods) {
        if (m && m->userdata) {
            static_cast<EditorViewportInputManager*>(m->userdata)->on_scroll(x, y, mods);
        }
    }

    static void editor_on_key(tc_input_manager* m, int key, int scancode, int action, int mods) {
        if (m && m->userdata) {
            static_cast<EditorViewportInputManager*>(m->userdata)->on_key(key, scancode, action, mods);
        }
    }

    static void editor_on_char(tc_input_manager* m, uint32_t codepoint) {
        char text[5] = {};
        if (codepoint >= 0xd800 && codepoint <= 0xdfff) {
            tc_log_error("[EditorViewportInputManager] invalid Unicode surrogate");
            return;
        } else if (codepoint <= 0x7f) {
            text[0] = static_cast<char>(codepoint);
        } else if (codepoint <= 0x7ff) {
            text[0] = static_cast<char>(0xc0 | (codepoint >> 6));
            text[1] = static_cast<char>(0x80 | (codepoint & 0x3f));
        } else if (codepoint <= 0xffff) {
            text[0] = static_cast<char>(0xe0 | (codepoint >> 12));
            text[1] = static_cast<char>(0x80 | ((codepoint >> 6) & 0x3f));
            text[2] = static_cast<char>(0x80 | (codepoint & 0x3f));
        } else if (codepoint <= 0x10ffff) {
            text[0] = static_cast<char>(0xf0 | (codepoint >> 18));
            text[1] = static_cast<char>(0x80 | ((codepoint >> 12) & 0x3f));
            text[2] = static_cast<char>(0x80 | ((codepoint >> 6) & 0x3f));
            text[3] = static_cast<char>(0x80 | (codepoint & 0x3f));
        } else {
            tc_log_error("[EditorViewportInputManager] invalid Unicode codepoint");
            return;
        }
        editor_on_text(m, text);
    }

    static void editor_on_text(tc_input_manager* m, const char* text_utf8) {
        if (m && m->userdata) {
            static_cast<EditorViewportInputManager*>(m->userdata)->on_text(text_utf8);
        }
    }

    static void editor_on_focus_lost(tc_input_manager* m) {
        if (m && m->userdata) {
            static_cast<EditorViewportInputManager*>(m->userdata)->on_focus_lost();
        }
    }

    static void editor_destroy(tc_input_manager* m) {
        (void)m;
    }

    tc_input_manager_vtable EditorViewportInputManager::_vtable = {
        .on_pointer = nullptr,
        .on_mouse_button = editor_on_mouse_button,
        .on_mouse_move = editor_on_mouse_move,
        .on_scroll = editor_on_scroll,
        .on_key = editor_on_key,
        .on_char = editor_on_char,
        .destroy = editor_destroy,
        .on_text = editor_on_text,
        .on_focus_lost = editor_on_focus_lost,
    };

    // ============================================================================
    // Constructor
    // ============================================================================

    EditorViewportInputManager::EditorViewportInputManager(tc_viewport_handle viewport, tc_display_handle display) {
        tc_input_manager_init(&_tc_im, &_vtable);
        _tc_im.userdata = this;
        rebind(viewport, display);
    }

    EditorViewportInputManager::~EditorViewportInputManager() {
        detach();
    }

    bool EditorViewportInputManager::rebind(tc_viewport_handle viewport, tc_display_handle display) {
        detach();
        if (!tc_viewport_alive(viewport) || !tc_display_alive(display)) {
            tc_log_error("[EditorViewportInputManager] cannot bind to an invalid viewport/display");
            return false;
        }
        _viewport = viewport;
        _display = display;
        _last_cursor_x = 0.0;
        _last_cursor_y = 0.0;
        _has_cursor = false;
        _current_mods = 0;
        _cancelled_pointer_buttons.clear();
        tc_viewport_set_input_manager(_viewport, &_tc_im);
        if (tc_viewport_get_input_manager(_viewport) != &_tc_im) {
            tc_log_error("[EditorViewportInputManager] failed to attach to viewport");
            _viewport = TC_VIEWPORT_HANDLE_INVALID;
            _display = TC_DISPLAY_HANDLE_INVALID;
            return false;
        }
        return true;
    }

    void EditorViewportInputManager::detach() {
        on_focus_lost();
        if (tc_viewport_alive(_viewport) && tc_viewport_get_input_manager(_viewport) == &_tc_im)
            tc_viewport_set_input_manager(_viewport, nullptr);
        _viewport = TC_VIEWPORT_HANDLE_INVALID;
        _display = TC_DISPLAY_HANDLE_INVALID;
        _has_cursor = false;
    }

    // ============================================================================
    // Event Handlers
    // ============================================================================

    void EditorViewportInputManager::on_mouse_button(int button, int action, int mods, uint32_t click_count) {
        if (!tc_viewport_alive(_viewport)) {
            if (_pointer_owner.kind != PointerOwnerKind::None)
                _quarantine_pointer_owner("the viewport died");
            return;
        }

        double x = _last_cursor_x;
        double y = _last_cursor_y;

        if (_cancelled_pointer_buttons.contains(button)) {
            if (action == TC_INPUT_PRESS) {
                tc_log(TC_LOG_WARN,
                       "[EditorViewportInputManager] received a new Down before the cancelled pointer sequence's Up; "
                       "ending stale event suppression for button %d",
                       button);
                _cancelled_pointer_buttons.erase(button);
            } else {
                _cancelled_pointer_buttons.erase(button);
                return;
            }
        }

        MouseButtonEvent event(
            MouseButtonEventInit{_viewport, x, y, button, action, mods, TC_INPUT_SOURCE_EDITOR, click_count});
        event.platform_services = &_tc_im.platform_services;

        if (_pointer_owner.kind != PointerOwnerKind::None) {
            if (button != _pointer_owner.button)
                return;
            const bool terminal = action != TC_INPUT_PRESS;
            const PointerOwner owner = _pointer_owner;
            if (terminal)
                _pointer_owner = {};
            const bool delivered = _dispatch_to_pointer_owner(owner, &event);
            if (!delivered && !terminal)
                _quarantine_pointer_owner("its owner disappeared");
            return;
        }

        if (action != TC_INPUT_PRESS)
            return;

        // Down chooses one exact owner. Later events bypass ordinary priority
        // dispatch until the initiating button reaches Up or Cancel.
        PointerOwner owner = _dispatch_to_internal_entities(&event);
        if (event.handled) {
            _pointer_owner = owner;
            _pointer_owner.button = button;
            return;
        }
        owner = _dispatch_to_editor_components(&event);
        if (event.handled) {
            _pointer_owner = owner;
            _pointer_owner.button = button;
            return;
        }

        auto* sys = EditorInteractionSystem::instance();
        if (sys &&
            sys->on_mouse_button(
                button, action, mods, click_count, static_cast<float>(x), static_cast<float>(y), _viewport, _display)) {
            _pointer_owner.kind = PointerOwnerKind::EditorInteraction;
            _pointer_owner.interaction = sys;
            _pointer_owner.button = button;
        }
    }

    void EditorViewportInputManager::on_mouse_move(double x, double y) {
        if (!tc_viewport_alive(_viewport)) {
            if (_pointer_owner.kind != PointerOwnerKind::None)
                _quarantine_pointer_owner("the viewport died");
            return;
        }

        double dx = 0.0, dy = 0.0;
        if (_has_cursor) {
            dx = x - _last_cursor_x;
            dy = y - _last_cursor_y;
        }
        _last_cursor_x = x;
        _last_cursor_y = y;
        _has_cursor = true;

        MouseMoveEvent event(_viewport, x, y, dx, dy, TC_INPUT_SOURCE_EDITOR);
        event.platform_services = &_tc_im.platform_services;

        if (_pointer_owner.kind != PointerOwnerKind::None) {
            if (!_dispatch_to_pointer_owner(_pointer_owner, &event))
                _quarantine_pointer_owner("its owner disappeared");
            return;
        }
        if (!_cancelled_pointer_buttons.empty())
            return;

        _dispatch_to_internal_entities(&event);
        if (event.handled)
            return;
        _dispatch_to_editor_components(&event);
        if (event.handled)
            return;

        // Delegate to EditorInteractionSystem for hover/gizmo
        auto* sys = EditorInteractionSystem::instance();
        if (sys) {
            sys->on_mouse_move((float)x, (float)y, (float)dx, (float)dy, _viewport, _display);
        }
    }

    void EditorViewportInputManager::on_scroll(double xoffset, double yoffset, int mods) {
        if (!tc_viewport_alive(_viewport))
            return;

        double x = _last_cursor_x;
        double y = _last_cursor_y;

        // Use mods from parameter if provided, otherwise fall back to tracked mods
        int actual_mods = mods != 0 ? mods : _current_mods;

        ScrollEvent event(_viewport, x, y, xoffset, yoffset, actual_mods, TC_INPUT_SOURCE_EDITOR);
        event.platform_services = &_tc_im.platform_services;
        _dispatch_to_internal_entities(&event);
        if (event.handled)
            return;
        _dispatch_to_editor_components(&event);
        if (event.handled)
            return;

        // Request render update (zoom changes camera, needs redraw)
        auto* sys = EditorInteractionSystem::instance();
        if (sys && sys->on_request_update) {
            sys->on_request_update();
        }
    }

    void EditorViewportInputManager::on_key(int key, int scancode, int action, int mods) {
        if (!tc_viewport_alive(_viewport))
            return;

        _current_mods = mods;
        KeyEvent event(_viewport, key, scancode, action, mods, TC_INPUT_SOURCE_EDITOR);
        event.platform_services = &_tc_im.platform_services;
        _dispatch_to_internal_entities(&event);
        if (event.handled)
            return;
        _dispatch_to_editor_components(&event);
        if (event.handled)
            return;

        // Delegate to EditorInteractionSystem for editor-level key handling
        auto* sys = EditorInteractionSystem::instance();
        bool handled_by_editor = false;
        if (sys) {
            KeyEvent key_event(_viewport, key, scancode, action, mods, TC_INPUT_SOURCE_EDITOR);
            handled_by_editor =
                sys->handle_key_event(key_event,
                                      Vec2f{static_cast<float>(_last_cursor_x), static_cast<float>(_last_cursor_y)},
                                      _viewport,
                                      _display);
        } else if (key == TC_KEY_T || key == 't' || key == 292) {
            tc_log(TC_LOG_WARN, "[EditorViewportInputManager] no EditorInteractionSystem for snap hotkey");
        }
        if (sys && sys->on_key) {
            KeyEvent key_event(_viewport, key, scancode, action, mods, TC_INPUT_SOURCE_EDITOR);
            if (!handled_by_editor) {
                sys->on_key(key_event);
            }
        } else if (!sys) {
            tc_log(TC_LOG_WARN, "EditorViewportInputManager::on_key: no sys=%p or no on_key callback", (void*)sys);
        }
    }

    void EditorViewportInputManager::on_text(const char* text_utf8) {
        if (!tc_viewport_alive(_viewport) || !text_utf8 || !text_utf8[0])
            return;
        tc_text_event event;
        tc_text_event_init_source(&event, _viewport, text_utf8, TC_INPUT_SOURCE_EDITOR);
        event.platform_services = &_tc_im.platform_services;
        _dispatch_to_internal_entities(&event);
        if (!event.handled) {
            _dispatch_to_editor_components(&event);
        }
    }

    void EditorViewportInputManager::on_focus_lost() {
        const bool viewport_alive = tc_viewport_alive(_viewport);
        const bool owned_editor_interaction = _pointer_owner.kind == PointerOwnerKind::EditorInteraction;
        if (_pointer_owner.kind != PointerOwnerKind::None) {
            _cancelled_pointer_buttons.insert(_pointer_owner.button);
            _pointer_owner = {};
        }
        if (viewport_alive) {
            tc_input_focus_event event;
            tc_input_focus_event_init_source(&event, _viewport, TC_INPUT_SOURCE_EDITOR);
            event.platform_services = &_tc_im.platform_services;
            _dispatch_to_internal_entities(&event);
            _dispatch_to_editor_components(&event);
        }
        if (viewport_alive || owned_editor_interaction) {
            if (auto* sys = EditorInteractionSystem::instance())
                sys->on_focus_lost();
        }
        _has_cursor = false;
        _current_mods = 0;
    }

    // ============================================================================
    // Dispatch helpers - Editor components opted into editor input source
    // ============================================================================

    EditorViewportInputManager::PointerOwner
    EditorViewportInputManager::_dispatch_to_editor_components(tc_mouse_button_event* ev) {
        tc_scene_handle scene = tc_viewport_get_scene(_viewport);
        if (!tc_scene_handle_valid(scene))
            return {};
        PointerOwner owner;
        owner.kind = PointerOwnerKind::SceneComponent;
        struct DispatchState {
            tc_mouse_button_event* event;
            PointerOwner* owner;
        } state{ev, &owner};
        tc_scene_foreach_input_handler(
            scene,
            [](tc_component* c, void* ud) -> bool {
                auto* state = static_cast<DispatchState*>(ud);
                auto* ev = state->event;
                if (tc_component_accepts_input_source(c, ev->source)) {
                    const tc_entity_handle entity = c->owner;
                    tc_component_on_mouse_button(c, ev);
                    if (ev->handled) {
                        state->owner->component = c;
                        state->owner->entity = entity;
                    }
                }
                return !ev->handled;
            },
            &state,
            TC_SCENE_FILTER_ENABLED | TC_SCENE_FILTER_ENTITY_ENABLED);
        return owner;
    }

    void EditorViewportInputManager::_dispatch_to_editor_components(tc_mouse_move_event* ev) {
        tc_scene_handle scene = tc_viewport_get_scene(_viewport);
        if (!tc_scene_handle_valid(scene))
            return;
        tc_scene_foreach_input_handler(
            scene,
            [](tc_component* c, void* ud) -> bool {
                auto* ev = static_cast<tc_mouse_move_event*>(ud);
                if (tc_component_accepts_input_source(c, ev->source)) {
                    tc_component_on_mouse_move(c, ev);
                }
                return !ev->handled;
            },
            ev,
            TC_SCENE_FILTER_ENABLED | TC_SCENE_FILTER_ENTITY_ENABLED);
    }

    void EditorViewportInputManager::_dispatch_to_editor_components(tc_scroll_event* ev) {
        tc_scene_handle scene = tc_viewport_get_scene(_viewport);
        if (!tc_scene_handle_valid(scene))
            return;
        tc_scene_foreach_input_handler(
            scene,
            [](tc_component* c, void* ud) -> bool {
                auto* ev = static_cast<tc_scroll_event*>(ud);
                if (tc_component_accepts_input_source(c, ev->source)) {
                    tc_component_on_scroll(c, ev);
                }
                return !ev->handled;
            },
            ev,
            TC_SCENE_FILTER_ENABLED | TC_SCENE_FILTER_ENTITY_ENABLED);
    }

    void EditorViewportInputManager::_dispatch_to_editor_components(tc_key_event* ev) {
        tc_scene_handle scene = tc_viewport_get_scene(_viewport);
        if (!tc_scene_handle_valid(scene))
            return;
        tc_scene_foreach_input_handler(
            scene,
            [](tc_component* c, void* ud) -> bool {
                auto* ev = static_cast<tc_key_event*>(ud);
                if (tc_component_accepts_input_source(c, ev->source)) {
                    tc_component_on_key(c, ev);
                }
                return !ev->handled;
            },
            ev,
            TC_SCENE_FILTER_ENABLED | TC_SCENE_FILTER_ENTITY_ENABLED);
    }

    void EditorViewportInputManager::_dispatch_to_editor_components(tc_text_event* ev) {
        tc_scene_handle scene = tc_viewport_get_scene(_viewport);
        if (!tc_scene_handle_valid(scene))
            return;
        tc_scene_foreach_input_handler(
            scene,
            [](tc_component* c, void* ud) -> bool {
                auto* ev = static_cast<tc_text_event*>(ud);
                if (tc_component_accepts_input_source(c, ev->source)) {
                    tc_component_on_text(c, ev);
                }
                return !ev->handled;
            },
            ev,
            TC_SCENE_FILTER_ENABLED | TC_SCENE_FILTER_ENTITY_ENABLED);
    }

    void EditorViewportInputManager::_dispatch_to_editor_components(tc_input_focus_event* ev) {
        tc_scene_handle scene = tc_viewport_get_scene(_viewport);
        if (!tc_scene_handle_valid(scene))
            return;
        tc_scene_foreach_input_handler(
            scene,
            [](tc_component* c, void* ud) -> bool {
                auto* ev = static_cast<tc_input_focus_event*>(ud);
                if (tc_component_accepts_input_source(c, ev->source)) {
                    tc_component_on_focus_lost(c, ev);
                }
                return true;
            },
            ev,
            TC_SCENE_FILTER_ENABLED | TC_SCENE_FILTER_ENTITY_ENABLED);
    }

    // ============================================================================
    // Dispatch helpers - Internal entities
    // ============================================================================

    EditorViewportInputManager::PointerOwner
    EditorViewportInputManager::_dispatch_to_internal_entities(tc_mouse_button_event* ev) {
        tc_entity_handle ent = tc_viewport_get_internal_entities(_viewport);
        if (!tc_entity_handle_valid(ent))
            return {};
        PointerOwner owner;
        owner.kind = PointerOwnerKind::InternalComponent;
        struct DispatchState {
            tc_mouse_button_event* event;
            PointerOwner* owner;
        } state{ev, &owner};
        tc_entity_foreach_input_handler_subtree(
            ent,
            [](tc_component* c, void* ud) -> bool {
                auto* state = static_cast<DispatchState*>(ud);
                auto* ev = state->event;
                if (tc_component_accepts_input_source(c, ev->source)) {
                    const tc_entity_handle entity = c->owner;
                    tc_component_on_mouse_button(c, ev);
                    if (ev->handled) {
                        state->owner->component = c;
                        state->owner->entity = entity;
                    }
                }
                return !ev->handled;
            },
            &state);
        return owner;
    }

    void EditorViewportInputManager::_dispatch_to_internal_entities(tc_mouse_move_event* ev) {
        tc_entity_handle ent = tc_viewport_get_internal_entities(_viewport);
        if (!tc_entity_handle_valid(ent))
            return;
        tc_entity_foreach_input_handler_subtree(
            ent,
            [](tc_component* c, void* ud) -> bool {
                auto* ev = static_cast<tc_mouse_move_event*>(ud);
                if (tc_component_accepts_input_source(c, ev->source)) {
                    tc_component_on_mouse_move(c, ev);
                }
                return !ev->handled;
            },
            ev);
    }

    void EditorViewportInputManager::_dispatch_to_internal_entities(tc_scroll_event* ev) {
        tc_entity_handle ent = tc_viewport_get_internal_entities(_viewport);
        if (!tc_entity_handle_valid(ent))
            return;
        tc_entity_foreach_input_handler_subtree(
            ent,
            [](tc_component* c, void* ud) -> bool {
                auto* ev = static_cast<tc_scroll_event*>(ud);
                if (tc_component_accepts_input_source(c, ev->source)) {
                    tc_component_on_scroll(c, ev);
                }
                return !ev->handled;
            },
            ev);
    }

    void EditorViewportInputManager::_dispatch_to_internal_entities(tc_key_event* ev) {
        tc_entity_handle ent = tc_viewport_get_internal_entities(_viewport);
        if (!tc_entity_handle_valid(ent))
            return;
        tc_entity_foreach_input_handler_subtree(
            ent,
            [](tc_component* c, void* ud) -> bool {
                auto* ev = static_cast<tc_key_event*>(ud);
                if (tc_component_accepts_input_source(c, ev->source)) {
                    tc_component_on_key(c, ev);
                }
                return !ev->handled;
            },
            ev);
    }

    void EditorViewportInputManager::_dispatch_to_internal_entities(tc_text_event* ev) {
        tc_entity_handle ent = tc_viewport_get_internal_entities(_viewport);
        if (!tc_entity_handle_valid(ent))
            return;
        tc_entity_foreach_input_handler_subtree(
            ent,
            [](tc_component* c, void* ud) -> bool {
                auto* ev = static_cast<tc_text_event*>(ud);
                if (tc_component_accepts_input_source(c, ev->source)) {
                    tc_component_on_text(c, ev);
                }
                return !ev->handled;
            },
            ev);
    }

    void EditorViewportInputManager::_dispatch_to_internal_entities(tc_input_focus_event* ev) {
        tc_entity_handle ent = tc_viewport_get_internal_entities(_viewport);
        if (!tc_entity_handle_valid(ent))
            return;
        tc_entity_foreach_input_handler_subtree(
            ent,
            [](tc_component* c, void* ud) -> bool {
                auto* ev = static_cast<tc_input_focus_event*>(ud);
                if (tc_component_accepts_input_source(c, ev->source)) {
                    tc_component_on_focus_lost(c, ev);
                }
                return true;
            },
            ev);
    }

    tc_component* EditorViewportInputManager::_resolve_pointer_component(const PointerOwner& owner) const {
        if (!owner.component || !tc_entity_handle_valid(owner.entity))
            return nullptr;
        const size_t count = tc_entity_component_count(owner.entity);
        for (size_t index = 0; index < count; ++index) {
            if (tc_entity_component_at(owner.entity, index) == owner.component)
                return owner.component;
        }
        return nullptr;
    }

    bool EditorViewportInputManager::_dispatch_to_pointer_owner(const PointerOwner& owner, tc_mouse_button_event* ev) {
        if (owner.kind == PointerOwnerKind::EditorInteraction) {
            if (!owner.interaction || EditorInteractionSystem::instance() != owner.interaction)
                return false;
            owner.interaction->on_mouse_button(ev->button,
                                               ev->action,
                                               ev->mods,
                                               ev->click_count,
                                               static_cast<float>(ev->x),
                                               static_cast<float>(ev->y),
                                               _viewport,
                                               _display);
            return true;
        }
        tc_component* component = _resolve_pointer_component(owner);
        if (!component)
            return false;
        tc_component_on_mouse_button(component, ev);
        return true;
    }

    bool EditorViewportInputManager::_dispatch_to_pointer_owner(const PointerOwner& owner, tc_mouse_move_event* ev) {
        if (owner.kind == PointerOwnerKind::EditorInteraction) {
            if (!owner.interaction || EditorInteractionSystem::instance() != owner.interaction)
                return false;
            owner.interaction->on_mouse_move(static_cast<float>(ev->x),
                                             static_cast<float>(ev->y),
                                             static_cast<float>(ev->dx),
                                             static_cast<float>(ev->dy),
                                             _viewport,
                                             _display);
            return true;
        }
        tc_component* component = _resolve_pointer_component(owner);
        if (!component)
            return false;
        tc_component_on_mouse_move(component, ev);
        return true;
    }

    void EditorViewportInputManager::_quarantine_pointer_owner(const char* reason) {
        if (_pointer_owner.kind == PointerOwnerKind::None)
            return;
        const bool owned_editor_interaction = _pointer_owner.kind == PointerOwnerKind::EditorInteraction;
        tc_log(TC_LOG_WARN,
               "[EditorViewportInputManager] pointer sequence cancelled because %s; suppressing button %d until Up",
               reason ? reason : "its owner became unavailable",
               _pointer_owner.button);
        _cancelled_pointer_buttons.insert(_pointer_owner.button);
        _pointer_owner = {};
        if (owned_editor_interaction) {
            if (auto* sys = EditorInteractionSystem::instance())
                sys->on_focus_lost();
        }
    }

} // namespace termin
