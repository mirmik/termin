// tc_inspect_csharp.cpp - C# inspect integration implementation
#include <termin_csharp/tc_inspect_csharp.h>
#include <string>
#include <vector>
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

struct tc_csharp_inspect_descriptor {
    std::string type_name;
    std::vector<CsFieldInfo> fields;
};

static constexpr const char* k_csharp_inspect_facet = "termin.inspect.csharp_fields";

static tc_csharp_inspect_descriptor* cs_facet(const char* type_name) {
    return static_cast<tc_csharp_inspect_descriptor*>(
        tc_runtime_type_registry_get_facet(type_name, k_csharp_inspect_facet));
}

static void destroy_cs_facet(void* payload) {
    delete static_cast<tc_csharp_inspect_descriptor*>(payload);
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
    return cs_facet(type_name) != nullptr;
}

static const char* cs_get_parent(const char* type_name, void* ctx) {
    (void)ctx;
    return tc_runtime_type_registry_get_parent(type_name);
}

static size_t cs_field_count(const char* type_name, void* ctx) {
    (void)ctx;
    if (!type_name) return 0;
    auto* facet = cs_facet(type_name);
    return facet ? facet->fields.size() : 0;
}

static bool cs_get_field(const char* type_name, size_t index, tc_field_info* out, void* ctx) {
    (void)ctx;
    if (!type_name || !out) return false;
    auto* facet = cs_facet(type_name);
    if (!facet || index >= facet->fields.size()) return false;

    const auto& f = facet->fields[index];
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
    auto* facet = cs_facet(type_name);
    if (!facet) return false;

    for (const auto& f : facet->fields) {
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

static bool cs_set(void* obj, const char* type_name, const char* path, tc_value value, void* context, void* ctx) {
    (void)ctx;
    if (!obj || !type_name || !path || !g_cs_inspect_set)
        return false;
    g_cs_inspect_set(obj, type_name, path, value, context);
    return true;
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

tc_csharp_inspect_descriptor* tc_csharp_inspect_descriptor_create(
    const char* type_name
) {
    if (!type_name || !type_name[0]) return nullptr;
    auto* descriptor = new tc_csharp_inspect_descriptor;
    descriptor->type_name = type_name;
    return descriptor;
}

bool tc_csharp_inspect_descriptor_add_field(
    tc_csharp_inspect_descriptor* descriptor,
    const char* path,
    const char* label,
    const char* kind,
    double min,
    double max,
    double step
) {
    if (!descriptor || !path || !path[0]) return false;
    tc_inspect_csharp_init();

    for (const auto& field : descriptor->fields) {
        if (field.path == path) return false;
    }

    CsFieldInfo info;
    info.path = path;
    info.label = label ? label : path;
    info.kind = kind ? kind : "double";
    info.min = min;
    info.max = max;
    info.step = step;

    descriptor->fields.push_back(std::move(info));
    return true;
}

bool tc_csharp_inspect_descriptor_attach(
    tc_csharp_inspect_descriptor* inspect_descriptor,
    tc_runtime_type_descriptor* runtime_descriptor
) {
    if (!inspect_descriptor || !runtime_descriptor) return false;
    if (!tc_runtime_type_descriptor_add_facet(
            runtime_descriptor,
            k_csharp_inspect_facet,
            inspect_descriptor,
            destroy_cs_facet,
            nullptr,
            1)) {
        return false;
    }
    tc_inspect_csharp_init();
    return true;
}

void tc_csharp_inspect_descriptor_destroy(
    tc_csharp_inspect_descriptor* descriptor
) {
    delete descriptor;
}

void tc_inspect_set_csharp_callbacks(
    tc_cs_inspect_get_fn getter,
    tc_cs_inspect_set_fn setter
) {
    g_cs_inspect_get = getter;
    g_cs_inspect_set = setter;
    tc_inspect_csharp_init();
}
