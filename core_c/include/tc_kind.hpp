// tc_kind.hpp - Kind handlers for serialization/deserialization
// Each language registers its own vtable for a kind.
#pragma once

#include <string>
#include <vector>
#include <unordered_map>
#include <functional>
#include <any>
#include <pybind11/pybind11.h>
#include "trent/trent.h"

// DLL export/import macros (same as InspectRegistry)
#ifdef _WIN32
    #ifdef ENTITY_LIB_EXPORTS
        #define TC_KIND_API __declspec(dllexport)
    #else
        #define TC_KIND_API __declspec(dllimport)
    #endif
#else
    #define TC_KIND_API
#endif

namespace py = pybind11;

namespace tc {

// TcKind - per-kind serialization handlers for each language
struct TcKind {
    std::string name;

    // C++ vtable - works with std::any and nos::trent
    struct CppVtable {
        std::function<nos::trent(const std::any&)> serialize;
        std::function<std::any(const nos::trent&)> deserialize;
        std::function<py::object(const std::any&)> to_python;  // for inspector get()
    } cpp;

    // Python vtable - works with py::object and py::dict
    // These store Python callables directly
    struct PyVtable {
        py::object serialize;    // callable(obj) -> dict
        py::object deserialize;  // callable(dict) -> obj
        py::object convert;      // callable(obj) -> obj
    } python;

    TcKind() = default;
    explicit TcKind(const std::string& n) : name(n) {}

    // Check if C++ vtable is set
    bool has_cpp() const {
        return cpp.serialize || cpp.deserialize;
    }

    // Check if Python vtable is set
    bool has_python() const {
        return !python.serialize.is_none() || !python.deserialize.is_none();
    }
};

// KindRegistry - singleton registry for all kinds
// Exported from entity_lib to ensure single instance across all modules
class TC_KIND_API KindRegistry {
    std::unordered_map<std::string, TcKind> _kinds;

public:
    // Defined in tc_kind.cpp (entity_lib) to ensure single instance
    static KindRegistry& instance();

    // Get kind by name, returns nullptr if not found
    TcKind* get(const std::string& name) {
        auto it = _kinds.find(name);
        return it != _kinds.end() ? &it->second : nullptr;
    }

    // Get or create kind by name
    TcKind& get_or_create(const std::string& name) {
        auto it = _kinds.find(name);
        if (it == _kinds.end()) {
            it = _kinds.emplace(name, TcKind(name)).first;
        }
        return it->second;
    }

    // Get all registered kind names
    std::vector<std::string> kinds() const {
        std::vector<std::string> result;
        result.reserve(_kinds.size());
        for (const auto& [name, _] : _kinds) {
            result.push_back(name);
        }
        return result;
    }

    // ========================================================================
    // C++ registration
    // ========================================================================

    void register_cpp(
        const std::string& name,
        std::function<nos::trent(const std::any&)> serialize,
        std::function<std::any(const nos::trent&)> deserialize,
        std::function<py::object(const std::any&)> to_python = nullptr
    ) {
        auto& kind = get_or_create(name);
        kind.cpp.serialize = std::move(serialize);
        kind.cpp.deserialize = std::move(deserialize);
        kind.cpp.to_python = std::move(to_python);
    }

    // ========================================================================
    // Python registration
    // ========================================================================

    void register_python(
        const std::string& name,
        py::object serialize,
        py::object deserialize,
        py::object convert = py::none()
    ) {
        auto& kind = get_or_create(name);
        kind.python.serialize = std::move(serialize);
        kind.python.deserialize = std::move(deserialize);
        kind.python.convert = std::move(convert);
    }

    // ========================================================================
    // C++ serialization helpers
    // ========================================================================

    nos::trent serialize_cpp(const std::string& kind_name, const std::any& value) {
        auto* kind = get(kind_name);
        if (kind && kind->cpp.serialize) {
            return kind->cpp.serialize(value);
        }
        return nos::trent::nil();
    }

    std::any deserialize_cpp(const std::string& kind_name, const nos::trent& data) {
        auto* kind = get(kind_name);
        if (kind && kind->cpp.deserialize) {
            return kind->cpp.deserialize(data);
        }
        return std::any{};
    }

    // Convert std::any to py::object using registered to_python handler
    py::object to_python_cpp(const std::string& kind_name, const std::any& value) {
        auto* kind = get(kind_name);
        if (kind && kind->cpp.to_python) {
            return kind->cpp.to_python(value);
        }
        return py::none();
    }

    // ========================================================================
    // Python serialization helpers
    // ========================================================================

    py::object serialize_python(const std::string& kind_name, py::object obj) {
        auto* kind = get(kind_name);
        if (kind && !kind->python.serialize.is_none()) {
            return kind->python.serialize(obj);
        }
        return py::none();
    }

    py::object deserialize_python(const std::string& kind_name, py::object data) {
        auto* kind = get(kind_name);
        if (kind && !kind->python.deserialize.is_none()) {
            return kind->python.deserialize(data);
        }
        return py::none();
    }

    py::object convert_python(const std::string& kind_name, py::object value) {
        auto* kind = get(kind_name);
        if (kind && !kind->python.convert.is_none()) {
            return kind->python.convert(value);
        }
        return value;
    }
};

// ============================================================================
// C++ registration helpers (template-based)
// ============================================================================

// Register a C++ handle type that has serialize() and deserialize_from(trent)
// Also registers list[kind_name] for std::vector<H>
template<typename H>
void register_cpp_handle_kind(const std::string& kind_name) {
    // Single element handler
    KindRegistry::instance().register_cpp(kind_name,
        // serialize: std::any(H) → trent
        [](const std::any& value) -> nos::trent {
            const H& h = std::any_cast<const H&>(value);
            py::dict d = h.serialize();
            nos::trent result;
            result.init(nos::trent_type::dict);
            for (auto item : d) {
                std::string key = py::str(item.first).cast<std::string>();
                py::object val = py::reinterpret_borrow<py::object>(item.second);
                if (py::isinstance<py::str>(val)) {
                    result[key] = nos::trent(val.cast<std::string>());
                } else if (py::isinstance<py::int_>(val)) {
                    result[key] = nos::trent(val.cast<int64_t>());
                } else if (py::isinstance<py::float_>(val)) {
                    result[key] = nos::trent(val.cast<double>());
                }
            }
            return result;
        },
        // deserialize: trent → std::any(H)
        [](const nos::trent& t) -> std::any {
            H h;
            h.deserialize_from(t);
            return h;
        },
        // to_python: std::any(H) → py::object
        [](const std::any& value) -> py::object {
            const H& h = std::any_cast<const H&>(value);
            return py::cast(h);
        }
    );

    // List handler for std::vector<H>
    std::string list_kind = "list[" + kind_name + "]";
    KindRegistry::instance().register_cpp(list_kind,
        // serialize: std::any(vector<H>) → trent (list)
        [](const std::any& value) -> nos::trent {
            const auto& vec = std::any_cast<const std::vector<H>&>(value);
            nos::trent result;
            result.init(nos::trent_type::list);
            for (const auto& h : vec) {
                py::dict d = h.serialize();
                nos::trent item;
                item.init(nos::trent_type::dict);
                for (auto kv : d) {
                    std::string key = py::str(kv.first).cast<std::string>();
                    py::object val = py::reinterpret_borrow<py::object>(kv.second);
                    if (py::isinstance<py::str>(val)) {
                        item[key] = nos::trent(val.cast<std::string>());
                    } else if (py::isinstance<py::int_>(val)) {
                        item[key] = nos::trent(val.cast<int64_t>());
                    } else if (py::isinstance<py::float_>(val)) {
                        item[key] = nos::trent(val.cast<double>());
                    }
                }
                result.push_back(item);
            }
            return result;
        },
        // deserialize: trent → std::any(vector<H>)
        [](const nos::trent& t) -> std::any {
            std::vector<H> vec;
            if (t.is_list()) {
                for (const auto& item : t.as_list()) {
                    H h;
                    h.deserialize_from(item);
                    vec.push_back(h);
                }
            }
            return vec;
        },
        // to_python: std::any(vector<H>) → py::list
        [](const std::any& value) -> py::object {
            const auto& vec = std::any_cast<const std::vector<H>&>(value);
            py::list result;
            for (const auto& h : vec) {
                result.append(py::cast(h));
            }
            return result;
        }
    );
}

} // namespace tc
