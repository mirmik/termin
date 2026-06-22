// tc_inspect_component_adapter.h - Component-level inspect adapter API
#ifndef TC_INSPECT_COMPONENT_ADAPTER_H
#define TC_INSPECT_COMPONENT_ADAPTER_H

#include "inspect/tc_inspect.h"
#include "inspect/tc_inspect_context.h"
#include <tgfx/resources/tc_mesh.h>
#include <tgfx/resources/tc_material.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

struct tc_component;
typedef struct tc_component tc_component;

// Component field access (unified API for native and external components)
// Works with tc_component* directly, handles both C++ and Python components.
// Kept as compatibility adapter surface during migration.
TC_API tc_value tc_component_inspect_get(tc_component* c, const char* path);
TC_API void tc_component_inspect_set(tc_component* c, const char* path, tc_value value, void* context);

// Simplified field setters for FFI (no tc_value marshalling needed).
TC_API void tc_component_set_field_int(tc_component* c, const char* path, int64_t value, void* context);
TC_API void tc_component_set_field_float(tc_component* c, const char* path, float value, void* context);
TC_API void tc_component_set_field_double(tc_component* c, const char* path, double value, void* context);
TC_API void tc_component_set_field_bool(tc_component* c, const char* path, bool value, void* context);
TC_API void tc_component_set_field_string(tc_component* c, const char* path, const char* value, void* context);
TC_API void tc_component_set_field_mesh(tc_component* c, const char* path, tc_mesh_handle handle, void* context);
TC_API void tc_component_set_field_material(tc_component* c, const char* path, tc_material_handle handle, void* context);
TC_API void tc_component_set_field_vec3(tc_component* c, const char* path, tc_vec3 value, void* context);
TC_API void tc_component_set_field_quat(tc_component* c, const char* path, tc_quat value, void* context);

// Simplified field getters.
TC_API void tc_component_get_field_vec3(tc_component* c, const char* path, tc_vec3* out_value);
TC_API void tc_component_get_field_quat(tc_component* c, const char* path, tc_quat* out_value);
TC_API int64_t tc_component_get_field_int(tc_component* c, const char* path);
TC_API float tc_component_get_field_float(tc_component* c, const char* path);
TC_API double tc_component_get_field_double(tc_component* c, const char* path);
TC_API bool tc_component_get_field_bool(tc_component* c, const char* path);
// Copies the UTF-8 string field into caller-owned storage. Returns the byte
// length excluding the null terminator. Passing a null/zero-sized buffer is a
// size query.
TC_API size_t tc_component_get_field_string_buffer(
    tc_component* c, const char* path, char* buffer, size_t buffer_size);
// Deprecated compatibility helper. The returned pointer is valid until the
// next call to this function and should not be used by new FFI bindings.
TC_API const char* tc_component_get_field_string(tc_component* c, const char* path);

#ifdef __cplusplus
}
#endif

#endif // TC_INSPECT_COMPONENT_ADAPTER_H
