// tc_kind.hpp - Unified kind registry (combines C++ and Python)
// This is the main header for code that needs both C++ and Python support.
// For C++-only code, use tc_kind_cpp.hpp instead.
#pragma once

#include "tc_kind_cpp.hpp"
#include "../bindings/inspect/tc_kind_python.hpp"

namespace tc {

// For backward compatibility, re-export register_cpp_handle_kind template
// that works with both C++ and Python serialization
template<typename H>
void register_cpp_handle_kind(const std::string& kind_name) {
    // Register C++ handler
    KindRegistryCpp::instance().register_kind(kind_name,
        // serialize: std::any(H) → trent
        [](const std::any& value) -> nos::trent {
            const H& h = std::any_cast<const H&>(value);
            nb::dict d = h.serialize();
            nos::trent result;
            result.init(nos::trent_type::dict);
            for (auto item : d) {
                std::string key = nb::cast<std::string>(nb::str(item.first));
                nb::object val = nb::borrow<nb::object>(item.second);
                if (nb::isinstance<nb::str>(val)) {
                    result[key] = nos::trent(nb::cast<std::string>(val));
                } else if (nb::isinstance<nb::int_>(val)) {
                    result[key] = nos::trent(nb::cast<int64_t>(val));
                } else if (nb::isinstance<nb::float_>(val)) {
                    result[key] = nos::trent(nb::cast<double>(val));
                }
            }
            return result;
        },
        // deserialize: trent, scene → std::any(H)
        [](const nos::trent& t, tc_scene* scene) -> std::any {
            H h;
            h.deserialize_from(t, scene);
            return h;
        }
    );

    // Register list handler for std::vector<H>
    std::string list_kind = "list[" + kind_name + "]";
    KindRegistryCpp::instance().register_kind(list_kind,
        // serialize: std::any(vector<H>) → trent (list)
        [](const std::any& value) -> nos::trent {
            const auto& vec = std::any_cast<const std::vector<H>&>(value);
            nos::trent result;
            result.init(nos::trent_type::list);
            for (const auto& h : vec) {
                nb::dict d = h.serialize();
                nos::trent item;
                item.init(nos::trent_type::dict);
                for (auto kv : d) {
                    std::string key = nb::cast<std::string>(nb::str(kv.first));
                    nb::object val = nb::borrow<nb::object>(kv.second);
                    if (nb::isinstance<nb::str>(val)) {
                        item[key] = nos::trent(nb::cast<std::string>(val));
                    } else if (nb::isinstance<nb::int_>(val)) {
                        item[key] = nos::trent(nb::cast<int64_t>(val));
                    } else if (nb::isinstance<nb::float_>(val)) {
                        item[key] = nos::trent(nb::cast<double>(val));
                    }
                }
                result.push_back(item);
            }
            return result;
        },
        // deserialize: trent, scene → std::any(vector<H>)
        [list_kind](const nos::trent& t, tc_scene* scene) -> std::any {
            std::vector<H> vec;
            tc_log(TC_LOG_INFO, "[list deserialize] %s: is_list=%d scene=%p",
                list_kind.c_str(), t.is_list() ? 1 : 0, (void*)scene);
            if (t.is_list()) {
                tc_log(TC_LOG_INFO, "[list deserialize] list size=%zu", t.as_list().size());
                for (const auto& item : t.as_list()) {
                    H h;
                    h.deserialize_from(item, scene);
                    vec.push_back(h);
                }
            }
            tc_log(TC_LOG_INFO, "[list deserialize] result size=%zu", vec.size());
            return vec;
        }
    );
}

// Register builtin kinds (both C++ and Python compatible)
inline void register_builtin_kinds() {
    register_builtin_cpp_kinds();
}

} // namespace tc
