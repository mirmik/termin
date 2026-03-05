// tc_kind.hpp - Unified kind registry (combines C++ and Python)
// This is the main header for code that needs both C++ and Python support.
// For C++-only code, use tc_kind_cpp.hpp instead.
#pragma once

#include "inspect/tc_kind_cpp.hpp"
#include "inspect/tc_kind_python.hpp"

namespace tc {

template <typename>
inline constexpr bool always_false_v = false;

template<typename H>
tc_value serialize_handle_value(const H& h) {
    if constexpr (requires(const H& x) { x.serialize_to_value(); }) {
        return h.serialize_to_value();
    } else if constexpr (requires(const H& x) {
        x.is_valid();
        x.uuid();
        x.name();
    }) {
        tc_value d = tc_value_dict_new();
        if (h.is_valid()) {
            tc_value_dict_set(&d, "uuid", tc_value_string(h.uuid()));
            tc_value_dict_set(&d, "name", tc_value_string(h.name()));
        }
        return d;
    } else {
        static_assert(always_false_v<H>, "Handle type must provide serialize_to_value() or {is_valid, uuid, name}.");
    }
}

template<typename H>
H deserialize_handle_value(const tc_value* v, void* context) {
    if constexpr (requires(H x) { x.deserialize_from(v, context); }) {
        H h;
        h.deserialize_from(v, context);
        return h;
    } else if constexpr (requires { H::from_uuid(std::string()); }) {
        if (!v || v->type != TC_VALUE_DICT) {
            return H();
        }
        tc_value* uuid_val = tc_value_dict_get(const_cast<tc_value*>(v), "uuid");
        if (!uuid_val || uuid_val->type != TC_VALUE_STRING || !uuid_val->data.s) {
            return H();
        }
        return H::from_uuid(std::string(uuid_val->data.s));
    } else {
        static_assert(always_false_v<H>, "Handle type must provide deserialize_from() or static from_uuid().");
    }
}

// Register handle kinds.
template<typename H>
void register_cpp_handle_kind(const std::string& kind_name) {
    // Register C++ handler
    KindRegistryCpp::instance().register_kind(kind_name,
        // serialize: std::any(H) → tc_value
        [](const std::any& value) -> tc_value {
            const H& h = std::any_cast<const H&>(value);
            return serialize_handle_value(h);
        },
        // deserialize: tc_value, scene → std::any(H)
        [](const tc_value* v, void* context) -> std::any {
            return deserialize_handle_value<H>(v, context);
        }
    );

    // Register list handler for std::vector<H>
    std::string list_kind = "list[" + kind_name + "]";
    KindRegistryCpp::instance().register_kind(list_kind,
        // serialize: std::any(vector<H>) → tc_value (list)
        [](const std::any& value) -> tc_value {
            const auto& vec = std::any_cast<const std::vector<H>&>(value);
            tc_value result = tc_value_list_new();
            for (const auto& h : vec) {
                tc_value item = serialize_handle_value(h);
                tc_value_list_push(&result, item);
            }
            return result;
        },
        // deserialize: tc_value, scene → std::any(vector<H>)
        [](const tc_value* v, void* context) -> std::any {
            std::vector<H> vec;
            if (v->type == TC_VALUE_LIST) {
                for (size_t i = 0; i < v->data.list.count; i++) {
                    H h = deserialize_handle_value<H>(&v->data.list.items[i], context);
                    vec.push_back(h);
                }
            }
            return vec;
        }
    );
}

// Register builtin kinds (both C++ and Python compatible)
inline void register_builtin_kinds() {
    register_builtin_cpp_kinds();
}

} // namespace tc
