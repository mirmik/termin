// tc_kind_python.hpp - Python bindings for kind serialization
// Extends KindRegistryCpp with Python-specific handlers via nanobind.
#pragma once

#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <string>
#include <unordered_map>

#include "termin/inspect/tc_kind_cpp.hpp"

// DLL export/import macros - singletons must be in entity_lib
#ifdef _WIN32
    #ifdef ENTITY_LIB_EXPORTS
        #define TC_KIND_PYTHON_API __declspec(dllexport)
    #else
        #define TC_KIND_PYTHON_API __declspec(dllimport)
    #endif
#else
    #define TC_KIND_PYTHON_API __attribute__((visibility("default")))
#endif

namespace nb = nanobind;

namespace tc {

// Combined kind handler - has both C++ and Python vtables
// This is the unified type used by tc_inspect.hpp
struct TcKind {
    std::string name;
    bool _has_cpp = false;
    bool _has_python = false;

    // C++ vtable - works with std::any and nos::trent
    struct CppVtable {
        std::function<nos::trent(const std::any&)> serialize;
        std::function<std::any(const nos::trent&, tc_scene*)> deserialize;
    } cpp;

    // Python vtable - works with nb::object
    struct PyVtable {
        nb::object serialize;    // callable(obj) -> dict
        nb::object deserialize;  // callable(dict) -> obj
    } python;

    TcKind() = default;
    explicit TcKind(const std::string& n) : name(n) {}

    bool has_cpp() const { return _has_cpp; }
    bool has_python() const { return _has_python; }
};

// Alias for backward compatibility with tc_inspect.hpp
using KindHandler = TcKind;

// Python kind handler - uses nb::object for Python callables
struct KindPython {
    std::string name;
    nb::object serialize;    // callable(obj) -> dict
    nb::object deserialize;  // callable(dict) -> obj

    bool is_valid() const {
        return serialize.ptr() != nullptr && deserialize.ptr() != nullptr;
    }
};

// Python Kind Registry - manages Python serialization handlers
// Works alongside KindRegistryCpp.
class TC_KIND_PYTHON_API KindRegistryPython {
    std::unordered_map<std::string, KindPython> _kinds;

public:
    // Singleton - defined in tc_kind_python_instance.cpp (entity_lib)
    static KindRegistryPython& instance();

    // Register Python handler
    void register_kind(
        const std::string& name,
        nb::object serialize,
        nb::object deserialize
    ) {
        KindPython kind;
        kind.name = name;
        kind.serialize = std::move(serialize);
        kind.deserialize = std::move(deserialize);
        _kinds[name] = std::move(kind);
    }

    // Get handler (returns nullptr if not found)
    KindPython* get(const std::string& name) {
        auto it = _kinds.find(name);
        return it != _kinds.end() ? &it->second : nullptr;
    }

    const KindPython* get(const std::string& name) const {
        auto it = _kinds.find(name);
        return it != _kinds.end() ? &it->second : nullptr;
    }

    bool has(const std::string& name) const {
        return _kinds.find(name) != _kinds.end();
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

    // Serialize value using Python handler
    nb::object serialize(const std::string& kind_name, nb::object obj) const {
        auto* kind = get(kind_name);
        if (kind && kind->serialize.ptr()) {
            return kind->serialize(obj);
        }
        return nb::none();
    }

    // Deserialize value using Python handler
    nb::object deserialize(const std::string& kind_name, nb::object data) const {
        auto* kind = get(kind_name);
        if (kind && kind->deserialize.ptr()) {
            return kind->deserialize(data);
        }
        return nb::none();
    }

    // Clear all Python references (call before Python finalization)
    void clear() {
        for (auto& [name, kind] : _kinds) {
            kind.serialize = nb::object();
            kind.deserialize = nb::object();
        }
        _kinds.clear();
    }
};

// Unified Kind Registry - combines C++ and Python registries
// This is what Python code interacts with.
class TC_KIND_PYTHON_API KindRegistry {
    // Combined handlers cache
    mutable std::unordered_map<std::string, TcKind> _combined;

    // Build or update combined handler for a kind
    TcKind* get_or_build(const std::string& name) {
        auto it = _combined.find(name);
        if (it == _combined.end()) {
            it = _combined.emplace(name, TcKind(name)).first;
        }

        TcKind& kind = it->second;

        // Sync C++ handler
        auto* cpp_kind = KindRegistryCpp::instance().get(name);
        if (cpp_kind) {
            kind.cpp.serialize = cpp_kind->serialize;
            kind.cpp.deserialize = cpp_kind->deserialize;
            kind._has_cpp = true;
        }

        // Sync Python handler
        auto* py_kind = KindRegistryPython::instance().get(name);
        if (py_kind) {
            kind.python.serialize = py_kind->serialize;
            kind.python.deserialize = py_kind->deserialize;
            kind._has_python = true;
        }

        return &kind;
    }

public:
    // Singleton - defined in tc_kind_python_instance.cpp (entity_lib)
    static KindRegistry& instance();

    // Get combined handler (returns nullptr if no handler exists)
    TcKind* get(const std::string& name) {
        if (!KindRegistryCpp::instance().has(name) &&
            !KindRegistryPython::instance().has(name)) {
            return nullptr;
        }
        return get_or_build(name);
    }

    // Get or create combined handler
    TcKind& get_or_create(const std::string& name) {
        return *get_or_build(name);
    }

    // Check if kind has C++ handler
    bool has_cpp(const std::string& name) const {
        return KindRegistryCpp::instance().has(name);
    }

    // Check if kind has Python handler
    bool has_python(const std::string& name) const {
        return KindRegistryPython::instance().has(name);
    }

    // Get all kinds (combined from both registries)
    std::vector<std::string> kinds() const {
        std::vector<std::string> result;

        // Add C++ kinds
        for (const auto& name : KindRegistryCpp::instance().kinds()) {
            result.push_back(name);
        }

        // Add Python kinds (if not already present)
        for (const auto& name : KindRegistryPython::instance().kinds()) {
            bool found = false;
            for (const auto& existing : result) {
                if (existing == name) {
                    found = true;
                    break;
                }
            }
            if (!found) {
                result.push_back(name);
            }
        }

        return result;
    }

    // Register C++ handler (delegates to KindRegistryCpp)
    void register_cpp(
        const std::string& name,
        std::function<nos::trent(const std::any&)> serialize,
        std::function<std::any(const nos::trent&, tc_scene*)> deserialize
    ) {
        KindRegistryCpp::instance().register_kind(name, serialize, deserialize);
        // Invalidate cache
        _combined.erase(name);
    }

    // Register Python handler
    void register_python(
        const std::string& name,
        nb::object serialize,
        nb::object deserialize
    ) {
        KindRegistryPython::instance().register_kind(name, serialize, deserialize);
        // Invalidate cache to rebuild with new Python handler
        _combined.erase(name);
    }

    // Serialize using C++ handler
    nos::trent serialize_cpp(const std::string& kind_name, const std::any& value) const {
        return KindRegistryCpp::instance().serialize(kind_name, value);
    }

    // Deserialize using C++ handler
    std::any deserialize_cpp(const std::string& kind_name, const nos::trent& data, tc_scene* scene = nullptr) const {
        return KindRegistryCpp::instance().deserialize(kind_name, data, scene);
    }

    // Serialize using Python handler
    nb::object serialize_python(const std::string& kind_name, nb::object obj) const {
        return KindRegistryPython::instance().serialize(kind_name, obj);
    }

    // Deserialize using Python handler
    nb::object deserialize_python(const std::string& kind_name, nb::object data) const {
        return KindRegistryPython::instance().deserialize(kind_name, data);
    }

    // Clear Python references
    void clear_python() {
        KindRegistryPython::instance().clear();
        // Clear combined cache entries that have Python handlers
        for (auto& [name, kind] : _combined) {
            kind.python.serialize = nb::object();
            kind.python.deserialize = nb::object();
            kind._has_python = false;
        }
    }

    // Access to underlying registries
    KindRegistryCpp& cpp() { return KindRegistryCpp::instance(); }
    const KindRegistryCpp& cpp() const { return KindRegistryCpp::instance(); }

    KindRegistryPython& python() { return KindRegistryPython::instance(); }
    const KindRegistryPython& python() const { return KindRegistryPython::instance(); }
};

// Bind KindRegistry to Python
inline void bind_kind_registry(nb::module_& m) {
    nb::class_<KindRegistry>(m, "KindRegistry")
        .def_static("instance", &KindRegistry::instance, nb::rv_policy::reference)
        .def("kinds", &KindRegistry::kinds)
        .def("has_cpp", &KindRegistry::has_cpp, nb::arg("name"))
        .def("has_python", &KindRegistry::has_python, nb::arg("name"))
        .def("register_python", &KindRegistry::register_python,
             nb::arg("name"), nb::arg("serialize"), nb::arg("deserialize"))
        .def("serialize", &KindRegistry::serialize_python,
             nb::arg("kind"), nb::arg("obj"))
        .def("deserialize", &KindRegistry::deserialize_python,
             nb::arg("kind"), nb::arg("data"));
}

} // namespace tc
