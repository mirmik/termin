// tc_inspect_instance.cpp - InspectRegistry singleton, vtable callbacks, and methods needing Component
// This file must be compiled into entity_lib to ensure single instance across all modules
// NOTE: Python-specific InspectRegistryPythonExt is in cpp/termin/bindings/inspect/tc_inspect_python.cpp

#include "../../cpp/trent/trent.h"

// Include Component BEFORE tc_inspect so it's fully defined
#include "../../cpp/termin/entity/component.hpp"

#include "../include/tc_inspect_cpp.hpp"
#include "../include/render/tc_pass.h"
#include "../include/tc_mesh_registry.h"
#include "../include/tc_material_registry.h"
#include "tc_log.hpp"

#include <string>

namespace tc {

// ============================================================================
// InspectRegistry singleton
// ============================================================================

InspectRegistry& InspectRegistry::instance() {
    static InspectRegistry reg;
    return reg;
}

// ============================================================================
// C++ vtable callbacks for C dispatcher
// ============================================================================

static bool cpp_has_type(const char* type_name, void* ctx) {
    (void)ctx;
    return InspectRegistry::instance().has_type(type_name);
}

static const char* cpp_get_parent(const char* type_name, void* ctx) {
    (void)ctx;
    static std::string parent;  // Static to keep string alive
    parent = InspectRegistry::instance().get_type_parent(type_name);
    return parent.empty() ? nullptr : parent.c_str();
}

static size_t cpp_field_count(const char* type_name, void* ctx) {
    (void)ctx;
    return InspectRegistry::instance().all_fields_count(type_name);
}

static bool cpp_get_field(const char* type_name, size_t index, tc_field_info* out, void* ctx) {
    (void)ctx;
    const InspectFieldInfo* info = InspectRegistry::instance().get_field_by_index(type_name, index);
    if (!info) return false;
    info->fill_c_info(out);
    return true;
}

static bool cpp_find_field(const char* type_name, const char* path, tc_field_info* out, void* ctx) {
    (void)ctx;
    const InspectFieldInfo* info = InspectRegistry::instance().find_field(type_name, path);
    if (!info) return false;
    info->fill_c_info(out);
    return true;
}

static tc_value cpp_get(void* obj, const char* type_name, const char* path, void* ctx) {
    (void)ctx;
    return InspectRegistry::instance().get_tc_value(obj, type_name, path);
}

static void cpp_set(void* obj, const char* type_name, const char* path, tc_value value, tc_scene_handle scene, void* ctx) {
    (void)ctx;
    InspectRegistry::instance().set_tc_value(obj, type_name, path, value, scene);
}

static void cpp_action(void* obj, const char* type_name, const char* path, void* ctx) {
    (void)ctx;
    InspectRegistry::instance().action_field(obj, type_name, path);
}

static bool g_cpp_vtable_initialized = false;

void init_cpp_inspect_vtable() {
    if (g_cpp_vtable_initialized) return;
    g_cpp_vtable_initialized = true;

    static tc_inspect_lang_vtable cpp_vtable = {
        cpp_has_type,
        cpp_get_parent,
        cpp_field_count,
        cpp_get_field,
        cpp_find_field,
        cpp_get,
        cpp_set,
        cpp_action,
        nullptr  // ctx
    };

    tc_inspect_set_lang_vtable(TC_INSPECT_LANG_CPP, &cpp_vtable);
}

// ============================================================================
// Component field access - C API implementation
// ============================================================================

static void* get_inspect_object(tc_component* c) {
    if (!c) return nullptr;
    if (c->kind == TC_NATIVE_COMPONENT) {
        return termin::CxxComponent::from_tc(c);
    } else {
        // For external components, body holds the Python object
        return c->body;
    }
}

} // namespace tc

extern "C" {

tc_value tc_component_inspect_get(tc_component* c, const char* path) {
    if (!c || !path) return tc_value_nil();

    const char* type_name = tc_component_type_name(c);
    if (!type_name) return tc_value_nil();

    void* obj = tc::get_inspect_object(c);
    if (!obj) return tc_value_nil();

    return tc::InspectRegistry::instance().get_tc_value(obj, type_name, path);
}

void tc_component_inspect_set(tc_component* c, const char* path, tc_value value, tc_scene_handle scene) {
    if (!c || !path) return;

    const char* type_name = tc_component_type_name(c);
    if (!type_name) return;

    void* obj = tc::get_inspect_object(c);
    if (!obj) return;

    tc::InspectRegistry::instance().set_tc_value(obj, type_name, path, value, scene);
}

tc_value tc_pass_inspect_get(tc_pass* p, const char* path) {
    if (!p || !path) return tc_value_nil();

    const char* type_name = tc_pass_type_name(p);
    if (!type_name) return tc_value_nil();

    void* obj = p->body;
    if (!obj) return tc_value_nil();

    return tc::InspectRegistry::instance().get_tc_value(obj, type_name, path);
}

void tc_pass_inspect_set(tc_pass* p, const char* path, tc_value value, tc_scene_handle scene) {
    if (!p || !path) return;

    const char* type_name = tc_pass_type_name(p);
    if (!type_name) return;

    void* obj = p->body;
    if (!obj) return;

    tc::InspectRegistry::instance().set_tc_value(obj, type_name, path, value, scene);
}

// ============================================================================
// Simplified field setters for FFI
// ============================================================================

void tc_component_set_field_int(tc_component* c, const char* path, int64_t value, tc_scene_handle scene) {
    tc_value v = tc_value_int(value);
    tc_component_inspect_set(c, path, v, scene);
    tc_value_free(&v);
}

void tc_component_set_field_float(tc_component* c, const char* path, float value, tc_scene_handle scene) {
    tc_value v = tc_value_float(value);
    tc_component_inspect_set(c, path, v, scene);
    tc_value_free(&v);
}

void tc_component_set_field_double(tc_component* c, const char* path, double value, tc_scene_handle scene) {
    tc_value v = tc_value_double(value);
    tc_component_inspect_set(c, path, v, scene);
    tc_value_free(&v);
}

void tc_component_set_field_bool(tc_component* c, const char* path, bool value, tc_scene_handle scene) {
    tc_value v = tc_value_bool(value);
    tc_component_inspect_set(c, path, v, scene);
    tc_value_free(&v);
}

void tc_component_set_field_string(tc_component* c, const char* path, const char* value, tc_scene_handle scene) {
    tc_value v = tc_value_string(value ? value : "");
    tc_component_inspect_set(c, path, v, scene);
    tc_value_free(&v);
}

void tc_component_set_field_mesh(tc_component* c, const char* path, tc_mesh_handle handle, tc_scene_handle scene) {
    // Mesh is serialized as dict with uuid
    const char* uuid = tc_mesh_uuid(handle);
    if (!uuid) return;

    tc_value v = tc_value_dict_new();
    tc_value_dict_set(&v, "uuid", tc_value_string(uuid));
    const char* name = tc_mesh_name(handle);
    if (name) tc_value_dict_set(&v, "name", tc_value_string(name));

    tc_component_inspect_set(c, path, v, scene);
    tc_value_free(&v);
}

void tc_component_set_field_material(tc_component* c, const char* path, tc_material_handle handle, tc_scene_handle scene) {
    // Material is serialized as dict with uuid
    const char* uuid = tc_material_uuid(handle);
    if (!uuid) return;

    tc_value v = tc_value_dict_new();
    tc_value_dict_set(&v, "uuid", tc_value_string(uuid));
    const char* name = tc_material_name(handle);
    if (name) tc_value_dict_set(&v, "name", tc_value_string(name));

    tc_component_inspect_set(c, path, v, scene);
    tc_value_free(&v);
}

// ============================================================================
// Simplified field getters for FFI
// ============================================================================

int64_t tc_component_get_field_int(tc_component* c, const char* path) {
    tc_value v = tc_component_inspect_get(c, path);
    int64_t result = 0;
    if (v.type == TC_VALUE_INT) result = v.data.i;
    else if (v.type == TC_VALUE_FLOAT) result = (int64_t)v.data.f;
    else if (v.type == TC_VALUE_DOUBLE) result = (int64_t)v.data.d;
    tc_value_free(&v);
    return result;
}

float tc_component_get_field_float(tc_component* c, const char* path) {
    tc_value v = tc_component_inspect_get(c, path);
    float result = 0.0f;
    if (v.type == TC_VALUE_FLOAT) result = v.data.f;
    else if (v.type == TC_VALUE_DOUBLE) result = (float)v.data.d;
    else if (v.type == TC_VALUE_INT) result = (float)v.data.i;
    tc_value_free(&v);
    return result;
}

double tc_component_get_field_double(tc_component* c, const char* path) {
    tc_value v = tc_component_inspect_get(c, path);
    double result = 0.0;
    if (v.type == TC_VALUE_DOUBLE) result = v.data.d;
    else if (v.type == TC_VALUE_FLOAT) result = (double)v.data.f;
    else if (v.type == TC_VALUE_INT) result = (double)v.data.i;
    tc_value_free(&v);
    return result;
}

bool tc_component_get_field_bool(tc_component* c, const char* path) {
    tc_value v = tc_component_inspect_get(c, path);
    bool result = false;
    if (v.type == TC_VALUE_BOOL) result = v.data.b;
    else if (v.type == TC_VALUE_INT) result = v.data.i != 0;
    tc_value_free(&v);
    return result;
}

// Note: Returns pointer to internal buffer, caller should NOT free.
// The string is valid until the next call to tc_component_get_field_string.
static thread_local std::string g_field_string_result;

const char* tc_component_get_field_string(tc_component* c, const char* path) {
    tc_value v = tc_component_inspect_get(c, path);
    g_field_string_result.clear();
    if (v.type == TC_VALUE_STRING && v.data.s) {
        g_field_string_result = v.data.s;
    }
    tc_value_free(&v);
    return g_field_string_result.c_str();
}

} // extern "C"
