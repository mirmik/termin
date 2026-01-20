// tc_kind_cpp.hpp - C++ layer for kind serialization
// Works standalone without Python. Python support is in tc_kind_python.hpp.
#pragma once

#include <string>
#include <vector>
#include <unordered_map>
#include <functional>
#include <any>

#include "trent/trent.h"

extern "C" {
#include "tc_inspect.h"
#include "tc_kind.h"
#include "tc_log.h"
#include "tc_scene.h"
}

// DLL export/import macros - singletons must be in entity_lib
#ifdef _WIN32
    #ifdef ENTITY_LIB_EXPORTS
        #define TC_KIND_CPP_API __declspec(dllexport)
    #else
        #define TC_KIND_CPP_API __declspec(dllimport)
    #endif
#else
    #define TC_KIND_CPP_API __attribute__((visibility("default")))
#endif

namespace tc {

// C++ kind handler - uses std::any and nos::trent for serialization
struct KindCpp {
    std::string name;
    std::function<nos::trent(const std::any&)> serialize;
    std::function<std::any(const nos::trent&, tc_scene*)> deserialize;

    bool is_valid() const {
        return serialize && deserialize;
    }
};

// C++ Kind Registry - manages C++ serialization handlers
// This is separate from the C tc_kind_handler system.
// Python layer (KindPython) can be added on top.
class TC_KIND_CPP_API KindRegistryCpp {
    std::unordered_map<std::string, KindCpp> _kinds;

public:
    // Singleton - defined in tc_kind_cpp.cpp (entity_lib)
    static KindRegistryCpp& instance();

    // Register C++ handler
    void register_kind(
        const std::string& name,
        std::function<nos::trent(const std::any&)> serialize,
        std::function<std::any(const nos::trent&, tc_scene*)> deserialize
    ) {
        KindCpp kind;
        kind.name = name;
        kind.serialize = std::move(serialize);
        kind.deserialize = std::move(deserialize);
        _kinds[name] = std::move(kind);
        // C registry is informed via vtable callbacks, no per-kind registration needed
    }

    // Get handler (returns nullptr if not found)
    KindCpp* get(const std::string& name) {
        auto it = _kinds.find(name);
        return it != _kinds.end() ? &it->second : nullptr;
    }

    const KindCpp* get(const std::string& name) const {
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

    // Serialize value
    nos::trent serialize(const std::string& kind_name, const std::any& value) const {
        auto* kind = get(kind_name);
        if (kind && kind->serialize) {
            return kind->serialize(value);
        }
        return nos::trent::nil();
    }

    // Deserialize value
    std::any deserialize(const std::string& kind_name, const nos::trent& data, tc_scene* scene = nullptr) const {
        auto* kind = get(kind_name);
        if (kind && kind->deserialize) {
            return kind->deserialize(data, scene);
        }
        return std::any{};
    }
};

// Register builtin C++ kinds (bool, int, float, double, string)
inline void register_builtin_cpp_kinds() {
    auto& reg = KindRegistryCpp::instance();

    // bool
    reg.register_kind("bool",
        [](const std::any& v) { return nos::trent(std::any_cast<bool>(v)); },
        [](const nos::trent& t, tc_scene*) -> std::any { return t.as_bool(); }
    );
    reg.register_kind("checkbox",
        [](const std::any& v) { return nos::trent(std::any_cast<bool>(v)); },
        [](const nos::trent& t, tc_scene*) -> std::any { return t.as_bool(); }
    );

    // int
    reg.register_kind("int",
        [](const std::any& v) { return nos::trent(static_cast<int64_t>(std::any_cast<int>(v))); },
        [](const nos::trent& t, tc_scene*) -> std::any { return static_cast<int>(t.as_numer()); }
    );
    reg.register_kind("slider_int",
        [](const std::any& v) { return nos::trent(static_cast<int64_t>(std::any_cast<int>(v))); },
        [](const nos::trent& t, tc_scene*) -> std::any { return static_cast<int>(t.as_numer()); }
    );
    // enum (C++ uses int for enum-like fields with choices)
    reg.register_kind("enum",
        [](const std::any& v) { return nos::trent(static_cast<int64_t>(std::any_cast<int>(v))); },
        [](const nos::trent& t, tc_scene*) -> std::any { return static_cast<int>(t.as_numer()); }
    );

    // float
    reg.register_kind("float",
        [](const std::any& v) { return nos::trent(static_cast<double>(std::any_cast<float>(v))); },
        [](const nos::trent& t, tc_scene*) -> std::any { return static_cast<float>(t.as_numer()); }
    );
    reg.register_kind("slider",
        [](const std::any& v) { return nos::trent(static_cast<double>(std::any_cast<float>(v))); },
        [](const nos::trent& t, tc_scene*) -> std::any { return static_cast<float>(t.as_numer()); }
    );
    reg.register_kind("drag_float",
        [](const std::any& v) { return nos::trent(static_cast<double>(std::any_cast<float>(v))); },
        [](const nos::trent& t, tc_scene*) -> std::any { return static_cast<float>(t.as_numer()); }
    );

    // double
    reg.register_kind("double",
        [](const std::any& v) { return nos::trent(std::any_cast<double>(v)); },
        [](const nos::trent& t, tc_scene*) -> std::any { return t.as_numer(); }
    );

    // string
    reg.register_kind("string",
        [](const std::any& v) { return nos::trent(std::any_cast<std::string>(v)); },
        [](const nos::trent& t, tc_scene*) -> std::any { return t.as_string(); }
    );
    reg.register_kind("text",
        [](const std::any& v) { return nos::trent(std::any_cast<std::string>(v)); },
        [](const nos::trent& t, tc_scene*) -> std::any { return t.as_string(); }
    );
    reg.register_kind("multiline_text",
        [](const std::any& v) { return nos::trent(std::any_cast<std::string>(v)); },
        [](const nos::trent& t, tc_scene*) -> std::any { return t.as_string(); }
    );
    reg.register_kind("clip_selector",
        [](const std::any& v) { return nos::trent(std::any_cast<std::string>(v)); },
        [](const nos::trent& t, tc_scene*) -> std::any { return t.as_string(); }
    );
}

// Helper to register handle types that have serialize() and deserialize_from() methods
template<typename H>
void register_cpp_handle_kind(const std::string& kind_name);

} // namespace tc
