// tc_kind.hpp - Kind handlers for serialization/deserialization
// Each language registers its own vtable for a kind.
#pragma once

#include <string>
#include <vector>
#include <unordered_map>
#include <functional>
#include <any>
#include <nanobind/nanobind.h>
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

namespace nb = nanobind;

namespace tc {

// TcKind - per-kind serialization handlers for each language
struct TcKind {
    std::string name;
    bool _has_cpp = false;
    bool _has_python = false;

    // C++ vtable - works with std::any and nos::trent
    struct CppVtable {
        std::function<nos::trent(const std::any&)> serialize;
        std::function<std::any(const nos::trent&)> deserialize;
        std::function<nb::object(const std::any&)> to_python;  // for inspector get()
    } cpp;

    // Python vtable - works with nb::object and nb::dict
    // These store Python callables directly
    struct PyVtable {
        nb::object serialize;    // callable(obj) -> dict
        nb::object deserialize;  // callable(dict) -> obj
        nb::object convert;      // callable(obj) -> obj
    } python;

    TcKind() = default;
    explicit TcKind(const std::string& n) : name(n) {}

    bool has_cpp() const { return _has_cpp; }
    bool has_python() const { return _has_python; }
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

    // Clear all Python references (call before Python finalization)
    void clear_python() {
        for (auto& [name, kind] : _kinds) {
            kind.python.serialize = nb::object();
            kind.python.deserialize = nb::object();
            kind.python.convert = nb::object();
            kind._has_python = false;
        }
    }

    // ========================================================================
    // C++ registration
    // ========================================================================

    void register_cpp(
        const std::string& name,
        std::function<nos::trent(const std::any&)> serialize,
        std::function<std::any(const nos::trent&)> deserialize,
        std::function<nb::object(const std::any&)> to_python = nullptr
    ) {
        auto& kind = get_or_create(name);
        kind.cpp.serialize = std::move(serialize);
        kind.cpp.deserialize = std::move(deserialize);
        kind.cpp.to_python = std::move(to_python);
        kind._has_cpp = true;
    }

    // ========================================================================
    // Python registration
    // ========================================================================

    void register_python(
        const std::string& name,
        nb::object serialize,
        nb::object deserialize,
        nb::object convert = nb::none()
    ) {
        auto& kind = get_or_create(name);
        kind.python.serialize = std::move(serialize);
        kind.python.deserialize = std::move(deserialize);
        kind.python.convert = std::move(convert);
        kind._has_python = true;
    }

    // ========================================================================
    // C++ serialization helpers
    // ========================================================================

    nos::trent serialize_cpp(const std::string& kind_name, const std::any& value) {
        auto* kind = get(kind_name);
        if (kind && kind->has_cpp()) {
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

    // Convert std::any to nb::object using registered to_python handler
    nb::object to_python_cpp(const std::string& kind_name, const std::any& value) {
        auto* kind = get(kind_name);
        if (kind && kind->cpp.to_python) {
            return kind->cpp.to_python(value);
        }
        return nb::none();
    }

    // ========================================================================
    // Python serialization helpers
    // ========================================================================

    nb::object serialize_python(const std::string& kind_name, nb::object obj) {
        auto* kind = get(kind_name);
        if (kind && kind->has_python()) {
            return kind->python.serialize(obj);
        }
        return nb::none();
    }

    nb::object deserialize_python(const std::string& kind_name, nb::object data) {
        auto* kind = get(kind_name);
        if (kind && kind->has_python()) {
            return kind->python.deserialize(data);
        }
        return nb::none();
    }

    nb::object convert_python(const std::string& kind_name, nb::object value) {
        auto* kind = get(kind_name);
        if (kind && kind->has_python()) {
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
        // deserialize: trent → std::any(H)
        [](const nos::trent& t) -> std::any {
            H h;
            h.deserialize_from(t);
            return h;
        },
        // to_python: std::any(H) → nb::object
        [](const std::any& value) -> nb::object {
            const H& h = std::any_cast<const H&>(value);
            return nb::cast(h);
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
        // to_python: std::any(vector<H>) → nb::list
        [](const std::any& value) -> nb::object {
            const auto& vec = std::any_cast<const std::vector<H>&>(value);
            nb::list result;
            for (const auto& h : vec) {
                result.append(nb::cast(h));
            }
            return result;
        }
    );
}

} // namespace tc
