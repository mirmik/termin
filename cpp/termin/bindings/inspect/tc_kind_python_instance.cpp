// tc_kind_python_instance.cpp - KindRegistryPython and KindRegistry singleton implementation
// Compiled into entity_lib to ensure single instance across all modules

#include "tc_kind_python.hpp"

extern "C" {
#include "tc_kind.h"
}

namespace tc {

// Global callback for lazy list handler creation
// Set by inspect_bindings.cpp at Python module init
EnsureListHandlerFn g_ensure_list_handler = nullptr;

// ============================================================================
// Python language vtable callbacks for C dispatcher
// ============================================================================

static bool python_has(const char* kind_name, void* ctx) {
    (void)ctx;
    return KindRegistryPython::instance().has(kind_name);
}

static tc_value python_serialize(const char* kind_name, const tc_value* input, void* ctx) {
    (void)ctx;
    (void)kind_name;
    // For Python kinds, actual serialization is done via KindRegistryPython::serialize()
    // which works with nb::object. This callback is pass-through.
    if (!input) return tc_value_nil();
    return tc_value_copy(input);
}

static tc_value python_deserialize(const char* kind_name, const tc_value* input, tc_scene_handle scene, void* ctx) {
    (void)ctx;
    (void)kind_name;
    (void)scene;
    // For Python kinds, actual deserialization is done via KindRegistryPython::deserialize()
    // which works with nb::object. This callback is pass-through.
    if (!input) return tc_value_nil();
    return tc_value_copy(input);
}

static size_t python_list(const char** out_names, size_t max_count, void* ctx) {
    (void)ctx;
    (void)out_names;
    (void)max_count;
    auto kinds = KindRegistryPython::instance().kinds();
    return kinds.size();
}

static bool g_python_vtable_initialized = false;

void init_python_lang_vtable() {
    if (g_python_vtable_initialized) return;
    g_python_vtable_initialized = true;

    static tc_kind_lang_registry python_registry = {
        python_has,
        python_serialize,
        python_deserialize,
        python_list,
        nullptr
    };

    tc_kind_set_lang_registry(TC_KIND_LANG_PYTHON, &python_registry);
}

// ============================================================================
// Singletons
// ============================================================================

KindRegistryPython& KindRegistryPython::instance() {
    static KindRegistryPython inst;
    return inst;
}

KindRegistry& KindRegistry::instance() {
    static KindRegistry inst;
    return inst;
}

} // namespace tc
