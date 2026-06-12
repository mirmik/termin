// tc_component_ref.hpp - Non-owning reference to tc_component
#pragma once

#include <string>
#include <cstring>
#include <tcbase/trent/trent.h>
#include "core/tc_component.h"
#include "core/tc_drawable_protocol.h"
#include "core/tc_input_component.h"
#include "inspect/tc_inspect.h"
#include "inspect/tc_inspect_context.h"
#include "core/tc_scene.h"
#include <tcbase/tc_value_trent.hpp>
#include <termin/entity/component.hpp>

namespace termin {

class Entity;

// Non-owning reference to a tc_component - allows working with components
// without requiring Python bindings for their specific type.
// This is the pure C++ version with trent-based serialization.
class TcComponentRef {
public:
    tc_component* _c = nullptr;

    TcComponentRef() = default;
    explicit TcComponentRef(tc_component* c) : _c(c) {}

    bool valid() const { return _c != nullptr; }

    const char* type_name() const {
        return _c ? tc_component_type_name(_c) : "";
    }

    bool enabled() const { return _c ? _c->enabled : false; }
    void set_enabled(bool v) { if (_c) _c->enabled = v; }

    bool active_in_editor() const { return _c ? _c->active_in_editor : false; }
    void set_active_in_editor(bool v) { if (_c) _c->active_in_editor = v; }

    std::string display_name() const {
        return _c ? tc_component_get_display_name(_c) : "";
    }

    void set_display_name(const std::string& v) {
        if (_c) tc_component_set_display_name(_c, v.c_str());
    }

    bool is_drawable() const { return tc_component_is_drawable(_c); }
    bool is_input_handler() const { return tc_component_is_input_handler(_c); }

    tc_component_kind kind() const {
        return _c ? _c->kind : TC_CXX_COMPONENT;
    }

    // Get owner entity handle
    tc_entity_handle entity_handle() const {
        if (!_c) return TC_ENTITY_HANDLE_INVALID;
        return _c->owner;
    }

    // Serialize component data to trent using tc_inspect
    nos::trent serialize_data_trent() const {
        if (!_c) return nos::trent();

        if (_c->kind == TC_CXX_COMPONENT) {
            CxxComponent* cxx = CxxComponent::from_tc(_c);
            if (!cxx) return nos::trent();
            tc_value v = cxx->serialize_data();
            write_base_fields_to_data(&v, _c);
            nos::trent result = tc::tc_value_to_trent(v);
            tc_value_free(&v);
            return result;
        } else {
            void* obj_ptr = _c->body;
            if (!obj_ptr) return nos::trent();
            tc_value v = tc_inspect_serialize(obj_ptr, tc_component_type_name(_c));
            write_base_fields_to_data(&v, _c);
            nos::trent result = tc::tc_value_to_trent(v);
            tc_value_free(&v);
            return result;
        }
    }

    // Full serialize to trent (type + data)
    nos::trent serialize_trent() const {
        if (!_c) return nos::trent();

        const char* tname = type_name();

        // Special case for UnknownComponent - return original type
        if (tname && strcmp(tname, "UnknownComponent") == 0 && _c->kind == TC_CXX_COMPONENT) {
            CxxComponent* cxx = CxxComponent::from_tc(_c);
            if (cxx) {
                tc_value orig_type = tc_inspect_get(cxx, "UnknownComponent", "original_type");
                tc_value orig_data = tc_inspect_get(cxx, "UnknownComponent", "original_data");

                nos::trent result;
                if (orig_type.type == TC_VALUE_STRING && orig_type.data.s && orig_type.data.s[0]) {
                    result["type"] = orig_type.data.s;
                } else {
                    result["type"] = "UnknownComponent";
                }
                result["data"] = tc::tc_value_to_trent(orig_data);

                tc_value_free(&orig_type);
                tc_value_free(&orig_data);
                return result;
            }
        }

        nos::trent result;
        result["type"] = tname;
        result["data"] = serialize_data_trent();
        return result;
    }

    // Deserialize data from trent
    void deserialize_data_trent(const nos::trent& data, tc_scene_handle scene = TC_SCENE_HANDLE_INVALID) {
        if (!_c || data.is_nil()) return;

        if (_c->kind == TC_CXX_COMPONENT) {
            CxxComponent* cxx = CxxComponent::from_tc(_c);
            if (!cxx) return;
            tc_value v = tc::trent_to_tc_value(data);
            read_base_fields_from_data(_c, &v);
            cxx->deserialize_data(&v, scene);
            tc_value_free(&v);
            return;
        } else {
            void* obj_ptr = _c->body;
            if (!obj_ptr) return;
            tc_value v = tc::trent_to_tc_value(data);
            read_base_fields_from_data(_c, &v);
            tc_scene_inspect_context inspect_ctx = tc_scene_inspect_context_make(scene);
            tc_inspect_deserialize(obj_ptr, tc_component_type_name(_c), &v, &inspect_ctx);
            tc_value_free(&v);
        }
    }

    // Comparison
    bool operator==(const TcComponentRef& other) const { return _c == other._c; }
    bool operator!=(const TcComponentRef& other) const { return _c != other._c; }

private:
    static void write_base_fields_to_data(tc_value* data, const tc_component* component) {
        if (!data || data->type != TC_VALUE_DICT || !component) return;

        const char* name = tc_component_get_display_name(component);
        if (name && name[0] && !tc_value_dict_has(data, "display_name")) {
            tc_value_dict_set(data, "display_name", tc_value_string(name));
        }
    }

    static void read_base_fields_from_data(tc_component* component, const tc_value* data) {
        if (!component || !data || data->type != TC_VALUE_DICT) return;

        tc_value* display_name = tc_value_dict_get(const_cast<tc_value*>(data), "display_name");
        if (display_name && display_name->type == TC_VALUE_STRING) {
            tc_component_set_display_name(component, display_name->data.s);
        }

        tc_value* enabled = tc_value_dict_get(const_cast<tc_value*>(data), "enabled");
        if (enabled && enabled->type == TC_VALUE_BOOL) {
            component->enabled = enabled->data.b;
        }

        tc_value* active_in_editor = tc_value_dict_get(const_cast<tc_value*>(data), "active_in_editor");
        if (active_in_editor && active_in_editor->type == TC_VALUE_BOOL) {
            component->active_in_editor = active_in_editor->data.b;
        }
    }
};

} // namespace termin
