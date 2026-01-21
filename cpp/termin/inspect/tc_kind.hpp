// tc_kind.hpp - Unified kind registry (combines C++ and Python)
// This is the main header for code that needs both C++ and Python support.
// For C++-only code, use tc_kind_cpp.hpp instead.
#pragma once

#include "tc_kind_cpp.hpp"
#include "../bindings/inspect/tc_kind_python.hpp"

namespace tc {

// Register handle types that have serialize_to_value() and deserialize_from() methods
template<typename H>
void register_cpp_handle_kind(const std::string& kind_name) {
    // Register C++ handler
    KindRegistryCpp::instance().register_kind(kind_name,
        // serialize: std::any(H) → tc_value
        [](const std::any& value) -> tc_value {
            const H& h = std::any_cast<const H&>(value);
            return h.serialize_to_value();
        },
        // deserialize: tc_value, scene → std::any(H)
        [](const tc_value* v, tc_scene* scene) -> std::any {
            H h;
            h.deserialize_from(v, scene);
            return h;
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
                tc_value_list_push(&result, h.serialize_to_value());
            }
            return result;
        },
        // deserialize: tc_value, scene → std::any(vector<H>)
        [](const tc_value* v, tc_scene* scene) -> std::any {
            std::vector<H> vec;
            if (v->type == TC_VALUE_LIST) {
                for (size_t i = 0; i < v->data.list.count; i++) {
                    H h;
                    h.deserialize_from(&v->data.list.items[i], scene);
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
