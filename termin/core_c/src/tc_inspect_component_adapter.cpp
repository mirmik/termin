// tc_inspect_component_adapter.cpp - Scene/component adapter for inspect API

#include <termin/entity/component.hpp>
#include "../../cpp/termin/inspect/tc_kind_cpp_ext.hpp"
#include "../../cpp/termin/mesh/tc_mesh_handle.hpp"
#include <tgfx/tgfx_material_handle.hpp>

#include "inspect/tc_inspect_component_adapter.h"

#include <string>

namespace {

void* get_inspect_object(tc_component* c) {
    if (!c) return nullptr;
    if (c->kind == TC_CXX_COMPONENT) {
        return termin::CxxComponent::from_tc(c);
    }
    return c->body;
}

} // namespace

namespace tc {

void register_component_adapter_kinds() {
    static bool registered = false;
    if (registered) return;
    registered = true;

    register_cpp_handle_kind<termin::TcMesh>("tc_mesh");
    register_cpp_handle_kind<termin::TcMaterial>("tc_material");
}

} // namespace tc

extern "C" {

void tc_inspect_component_adapter_init(void) {
    tc::register_component_adapter_kinds();
}

tc_value tc_component_inspect_get(tc_component* c, const char* path) {
    if (!c || !path) return tc_value_nil();

    const char* type_name = tc_component_type_name(c);
    if (!type_name) return tc_value_nil();

    void* obj = get_inspect_object(c);
    if (!obj) return tc_value_nil();

    return tc_inspect_get(obj, type_name, path);
}

void tc_component_inspect_set(tc_component* c, const char* path, tc_value value, void* context) {
    if (!c || !path) return;

    const char* type_name = tc_component_type_name(c);
    if (!type_name) return;

    void* obj = get_inspect_object(c);
    if (!obj) return;

    tc_inspect_set(obj, type_name, path, value, context);
}

void tc_component_set_field_vec3(tc_component* c, const char* path, tc_vec3 value, void* context) {
    tc_value v = tc_value_vec3(value);
    tc_component_inspect_set(c, path, v, context);
    tc_value_free(&v);
}

tc_vec3 tc_component_get_field_vec3(tc_component* c, const char* path) {
    tc_value v = tc_component_inspect_get(c, path);
    tc_vec3 result = {0.0, 0.0, 0.0};
    if (v.type == TC_VALUE_VEC3) {
        result = v.data.v3;
    }
    tc_value_free(&v);
    return result;
}

void tc_component_set_field_quat(tc_component* c, const char* path, tc_quat value, void* context) {
    tc_value v = tc_value_quat(value);
    tc_component_inspect_set(c, path, v, context);
    tc_value_free(&v);
}

tc_quat tc_component_get_field_quat(tc_component* c, const char* path) {
    tc_value v = tc_component_inspect_get(c, path);
    tc_quat result = {0, 0, 0, 1};
    if (v.type == TC_VALUE_QUAT) {
        result = v.data.q;
    }
    tc_value_free(&v);
    return result;
}

void tc_component_set_field_int(tc_component* c, const char* path, int64_t value, void* context) {
    tc_value v = tc_value_int(value);
    tc_component_inspect_set(c, path, v, context);
    tc_value_free(&v);
}

void tc_component_set_field_float(tc_component* c, const char* path, float value, void* context) {
    tc_value v = tc_value_float(value);
    tc_component_inspect_set(c, path, v, context);
    tc_value_free(&v);
}

void tc_component_set_field_double(tc_component* c, const char* path, double value, void* context) {
    tc_value v = tc_value_double(value);
    tc_component_inspect_set(c, path, v, context);
    tc_value_free(&v);
}

void tc_component_set_field_bool(tc_component* c, const char* path, bool value, void* context) {
    tc_value v = tc_value_bool(value);
    tc_component_inspect_set(c, path, v, context);
    tc_value_free(&v);
}

void tc_component_set_field_string(tc_component* c, const char* path, const char* value, void* context) {
    tc_value v = tc_value_string(value ? value : "");
    tc_component_inspect_set(c, path, v, context);
    tc_value_free(&v);
}

void tc_component_set_field_mesh(tc_component* c, const char* path, tc_mesh_handle handle, void* context) {
    const char* uuid = tc_mesh_uuid(handle);
    if (!uuid) return;

    tc_value v = tc_value_dict_new();
    tc_value_dict_set(&v, "uuid", tc_value_string(uuid));
    const char* name = tc_mesh_name(handle);
    if (name) tc_value_dict_set(&v, "name", tc_value_string(name));

    tc_component_inspect_set(c, path, v, context);
    tc_value_free(&v);
}

void tc_component_set_field_material(tc_component* c, const char* path, tc_material_handle handle, void* context) {
    const char* uuid = tc_material_uuid(handle);
    if (!uuid) return;

    tc_value v = tc_value_dict_new();
    tc_value_dict_set(&v, "uuid", tc_value_string(uuid));
    const char* name = tc_material_name(handle);
    if (name) tc_value_dict_set(&v, "name", tc_value_string(name));

    tc_component_inspect_set(c, path, v, context);
    tc_value_free(&v);
}

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
