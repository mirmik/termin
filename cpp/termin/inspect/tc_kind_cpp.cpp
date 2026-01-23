// tc_kind_cpp.cpp - KindRegistryCpp singleton and C++ language vtable registration
// Compiled into entity_lib to ensure single instance across all modules

#include "tc_kind_cpp.hpp"

extern "C" {
#include "tc_kind.h"
}

namespace tc {

// ============================================================================
// C++ language vtable callbacks for C dispatcher
// ============================================================================

static bool cpp_has(const char* kind_name, void* ctx) {
    (void)ctx;
    return KindRegistryCpp::instance().has(kind_name);
}

static tc_value cpp_serialize(const char* kind_name, const tc_value* input, void* ctx) {
    (void)ctx;
    // For C++ kinds, actual serialization is done via KindRegistryCpp::serialize()
    // which works with std::any. This callback is pass-through since the value
    // is already serialized by the time it reaches the C API.
    if (!input) return tc_value_nil();
    return tc_value_copy(input);
}

static tc_value cpp_deserialize(const char* kind_name, const tc_value* input, tc_scene* scene, void* ctx) {
    (void)ctx;
    (void)scene;
    // For C++ kinds, actual deserialization is done via KindRegistryCpp::deserialize()
    // which works with std::any. This callback is pass-through.
    if (!input) return tc_value_nil();
    return tc_value_copy(input);
}

static size_t cpp_list(const char** out_names, size_t max_count, void* ctx) {
    (void)ctx;
    auto kinds = KindRegistryCpp::instance().kinds();
    size_t count = std::min(kinds.size(), max_count);
    if (out_names) {
        // Note: returning pointers to temporary strings is unsafe for this API
        // For now, we just return the count. Caller should use KindRegistryCpp::kinds() directly.
    }
    return kinds.size();
}

static bool g_cpp_vtable_initialized = false;

static void init_cpp_lang_vtable() {
    if (g_cpp_vtable_initialized) return;
    g_cpp_vtable_initialized = true;

    static tc_kind_lang_registry cpp_registry = {
        cpp_has,
        cpp_serialize,
        cpp_deserialize,
        cpp_list,
        nullptr
    };

    tc_kind_set_lang_registry(TC_KIND_LANG_CPP, &cpp_registry);
}

// ============================================================================
// Singleton
// ============================================================================

KindRegistryCpp& KindRegistryCpp::instance() {
    static KindRegistryCpp inst;

    // Ensure vtable is registered on first access
    init_cpp_lang_vtable();

    return inst;
}

} // namespace tc
