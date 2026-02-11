// tc_inspect_csharp.cpp - C# inspect integration implementation
#include "tc_inspect_csharp.h"
#include <string>
#include <vector>
#include <unordered_map>
#include <cstring>

// ============================================================================
// Internal storage for C# field metadata
// ============================================================================

struct CsFieldInfo {
    std::string path;
    std::string label;
    std::string kind;
    double min;
    double max;
    double step;
};

static std::unordered_map<std::string, std::vector<CsFieldInfo>>& get_cs_fields() {
    static std::unordered_map<std::string, std::vector<CsFieldInfo>> fields;
    return fields;
}

// Global C# inspect callbacks
static tc_cs_inspect_get_fn g_cs_inspect_get = nullptr;
static tc_cs_inspect_set_fn g_cs_inspect_set = nullptr;
static bool g_cs_vtable_initialized = false;

// ============================================================================
// tc_inspect_lang_vtable implementation for C#
// ============================================================================

static bool cs_has_type(const char* type_name, void* ctx) {
    (void)ctx;
    if (!type_name) return false;
    return get_cs_fields().count(type_name) > 0;
}

static const char* cs_get_parent(const char* type_name, void* ctx) {
    (void)ctx; (void)type_name;
    return nullptr;  // C# components have no parent in inspect hierarchy
}

static size_t cs_field_count(const char* type_name, void* ctx) {
    (void)ctx;
    if (!type_name) return 0;
    auto& fields = get_cs_fields();
    auto it = fields.find(type_name);
    if (it == fields.end()) return 0;
    return it->second.size();
}

static bool cs_get_field(const char* type_name, size_t index, tc_field_info* out, void* ctx) {
    (void)ctx;
    if (!type_name || !out) return false;
    auto& fields = get_cs_fields();
    auto it = fields.find(type_name);
    if (it == fields.end() || index >= it->second.size()) return false;

    const auto& f = it->second[index];
    out->path = f.path.c_str();
    out->label = f.label.c_str();
    out->kind = f.kind.c_str();
    out->min = f.min;
    out->max = f.max;
    out->step = f.step;
    out->is_serializable = true;
    out->is_inspectable = true;
    out->choices = nullptr;
    out->choice_count = 0;
    return true;
}

static bool cs_find_field(const char* type_name, const char* path, tc_field_info* out, void* ctx) {
    (void)ctx;
    if (!type_name || !path || !out) return false;
    auto& fields = get_cs_fields();
    auto it = fields.find(type_name);
    if (it == fields.end()) return false;

    for (const auto& f : it->second) {
        if (f.path == path) {
            out->path = f.path.c_str();
            out->label = f.label.c_str();
            out->kind = f.kind.c_str();
            out->min = f.min;
            out->max = f.max;
            out->step = f.step;
            out->is_serializable = true;
            out->is_inspectable = true;
            out->choices = nullptr;
            out->choice_count = 0;
            return true;
        }
    }
    return false;
}

static tc_value cs_get(void* obj, const char* type_name, const char* path, void* ctx) {
    (void)ctx;
    if (!obj || !type_name || !path || !g_cs_inspect_get)
        return tc_value_nil();
    return g_cs_inspect_get(obj, type_name, path);
}

static void cs_set(void* obj, const char* type_name, const char* path, tc_value value, tc_scene_handle scene, void* ctx) {
    (void)ctx;
    if (!obj || !type_name || !path || !g_cs_inspect_set)
        return;
    g_cs_inspect_set(obj, type_name, path, value, scene);
}

static void cs_action(void* obj, const char* type_name, const char* path, void* ctx) {
    (void)obj; (void)type_name; (void)path; (void)ctx;
    // Button actions not yet supported for C#
}

// ============================================================================
// Public API
// ============================================================================

void tc_inspect_csharp_init(void) {
    if (g_cs_vtable_initialized) return;
    g_cs_vtable_initialized = true;

    static tc_inspect_lang_vtable cs_vtable = {
        cs_has_type,
        cs_get_parent,
        cs_field_count,
        cs_get_field,
        cs_find_field,
        cs_get,
        cs_set,
        cs_action,
        nullptr  // ctx
    };

    tc_inspect_set_lang_vtable(TC_INSPECT_LANG_CSHARP, &cs_vtable);
}

void tc_inspect_csharp_register_type(const char* type_name) {
    if (!type_name) return;
    tc_inspect_csharp_init();
    // Ensure the type exists in the map (even if empty)
    get_cs_fields()[type_name];
}

void tc_inspect_csharp_register_field(
    const char* type_name,
    const char* path,
    const char* label,
    const char* kind,
    double min,
    double max,
    double step
) {
    if (!type_name || !path) return;
    tc_inspect_csharp_init();

    CsFieldInfo info;
    info.path = path;
    info.label = label ? label : path;
    info.kind = kind ? kind : "double";
    info.min = min;
    info.max = max;
    info.step = step;

    get_cs_fields()[type_name].push_back(std::move(info));
}

void tc_inspect_set_csharp_callbacks(
    tc_cs_inspect_get_fn getter,
    tc_cs_inspect_set_fn setter
) {
    g_cs_inspect_get = getter;
    g_cs_inspect_set = setter;
    tc_inspect_csharp_init();
}
