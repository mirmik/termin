// tc_inspect_component_adapter.cpp - Scene/component adapter for inspect API

#include <termin/entity/component.hpp>

#include "inspect/tc_inspect_component_adapter.h"

#include <algorithm>
#include <cstring>
#include <mutex>
#include <string>

namespace {

void* get_inspect_object(tc_component* c) {
    if (!c) return nullptr;
    if (c->kind == TC_CXX_COMPONENT) {
        return termin::CxxComponent::from_tc(c);
    }
    return c->body;
}

std::string read_component_field_string(tc_component* c, const char* path) {
    tc_value v = tc_component_inspect_get(c, path);
    std::string result;
    if (v.type == TC_VALUE_STRING && v.data.s) {
        result = v.data.s;
    }
    tc_value_free(&v);
    return result;
}

std::mutex g_legacy_field_string_mutex;
std::string g_legacy_field_string_result;

} // namespace

extern "C" {

void tc_inspect_component_adapter_init(void) {
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
    tc_value v = tc_value_list_new();
    tc_value_list_push(&v, tc_value_double(value.x));
    tc_value_list_push(&v, tc_value_double(value.y));
    tc_value_list_push(&v, tc_value_double(value.z));
    tc_component_inspect_set(c, path, v, context);
    tc_value_free(&v);
}

void tc_component_get_field_vec3(tc_component* c, const char* path, tc_vec3* out_value) {
    if (!out_value) return;

    tc_value v = tc_component_inspect_get(c, path);
    tc_vec3 result = {0.0, 0.0, 0.0};
    if (v.type == TC_VALUE_LIST && v.data.list.count >= 3) {
        auto get_d = [](tc_value* item) -> double {
            if (!item) return 0.0;
            if (item->type == TC_VALUE_DOUBLE) return item->data.d;
            if (item->type == TC_VALUE_FLOAT) return (double)item->data.f;
            if (item->type == TC_VALUE_INT) return (double)item->data.i;
            return 0.0;
        };
        result.x = get_d(tc_value_list_get(&v, 0));
        result.y = get_d(tc_value_list_get(&v, 1));
        result.z = get_d(tc_value_list_get(&v, 2));
    }
    tc_value_free(&v);
    *out_value = result;
}

void tc_component_set_field_quat(tc_component* c, const char* path, tc_quat value, void* context) {
    tc_value v = tc_value_list_new();
    tc_value_list_push(&v, tc_value_double(value.x));
    tc_value_list_push(&v, tc_value_double(value.y));
    tc_value_list_push(&v, tc_value_double(value.z));
    tc_value_list_push(&v, tc_value_double(value.w));
    tc_component_inspect_set(c, path, v, context);
    tc_value_free(&v);
}

void tc_component_get_field_quat(tc_component* c, const char* path, tc_quat* out_value) {
    if (!out_value) return;

    tc_value v = tc_component_inspect_get(c, path);
    tc_quat result = {0, 0, 0, 1};
    if (v.type == TC_VALUE_LIST && v.data.list.count >= 4) {
        auto get_d = [](tc_value* item) -> double {
            if (!item) return 0.0;
            if (item->type == TC_VALUE_DOUBLE) return item->data.d;
            if (item->type == TC_VALUE_FLOAT) return (double)item->data.f;
            if (item->type == TC_VALUE_INT) return (double)item->data.i;
            return 0.0;
        };
        result.x = get_d(tc_value_list_get(&v, 0));
        result.y = get_d(tc_value_list_get(&v, 1));
        result.z = get_d(tc_value_list_get(&v, 2));
        result.w = get_d(tc_value_list_get(&v, 3));
    }
    tc_value_free(&v);
    *out_value = result;
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

size_t tc_component_get_field_string_buffer(
    tc_component* c, const char* path, char* buffer, size_t buffer_size) {
    std::string result = read_component_field_string(c, path);
    if (buffer && buffer_size > 0) {
        const size_t copy_size = std::min(result.size(), buffer_size - 1);
        if (copy_size > 0) {
            std::memcpy(buffer, result.data(), copy_size);
        }
        buffer[copy_size] = '\0';
    }
    return result.size();
}

const char* tc_component_get_field_string(tc_component* c, const char* path) {
    std::lock_guard<std::mutex> lock(g_legacy_field_string_mutex);
    g_legacy_field_string_result = read_component_field_string(c, path);
    return g_legacy_field_string_result.c_str();
}

} // extern "C"
