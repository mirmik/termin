// tc_component_ref.hpp - Non-owning reference to tc_component
#pragma once

#include <string>
#include <cstring>
#include <trent/trent.h>
#include "core/tc_component.h"
#include "inspect/tc_inspect.h"
#include "core/tc_scene.h"
#include "../render/tc_value_trent.hpp"
#include "component.hpp"

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

        void* obj_ptr = nullptr;
        if (_c->kind == TC_CXX_COMPONENT) {
            obj_ptr = CxxComponent::from_tc(_c);
        } else {
            obj_ptr = _c->body;
        }
        if (!obj_ptr) return nos::trent();

        tc_value v = tc_inspect_serialize(obj_ptr, tc_component_type_name(_c));
        nos::trent result = tc::tc_value_to_trent(v);
        tc_value_free(&v);
        return result;
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

        void* obj_ptr = nullptr;
        if (_c->kind == TC_CXX_COMPONENT) {
            obj_ptr = CxxComponent::from_tc(_c);
        } else {
            obj_ptr = _c->body;
        }
        if (!obj_ptr) return;

        tc_value v = tc::trent_to_tc_value(data);
        tc_inspect_deserialize(obj_ptr, tc_component_type_name(_c), &v, scene);
        tc_value_free(&v);
    }

    // Comparison
    bool operator==(const TcComponentRef& other) const { return _c == other._c; }
    bool operator!=(const TcComponentRef& other) const { return _c != other._c; }
};

} // namespace termin
