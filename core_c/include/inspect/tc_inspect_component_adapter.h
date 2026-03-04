// tc_inspect_component_adapter.h - Component-level inspect adapter API
#ifndef TC_INSPECT_COMPONENT_ADAPTER_H
#define TC_INSPECT_COMPONENT_ADAPTER_H

#include "inspect/tc_inspect.h"
#include <tgfx/resources/tc_mesh.h>
#include <tgfx/resources/tc_material.h>

#ifdef __cplusplus
extern "C" {
#endif

struct tc_component;
typedef struct tc_component tc_component;

// Component field access (unified API for native and external components)
// Works with tc_component* directly, handles both C++ and Python components.
TC_API tc_value tc_component_inspect_get(tc_component* c, const char* path);
TC_API void tc_component_inspect_set(tc_component* c, const char* path, tc_value value, tc_scene_handle scene);

// Simplified field setters for FFI (no tc_value marshalling needed).
TC_API void tc_component_set_field_int(tc_component* c, const char* path, int64_t value, tc_scene_handle scene);
TC_API void tc_component_set_field_float(tc_component* c, const char* path, float value, tc_scene_handle scene);
TC_API void tc_component_set_field_double(tc_component* c, const char* path, double value, tc_scene_handle scene);
TC_API void tc_component_set_field_bool(tc_component* c, const char* path, bool value, tc_scene_handle scene);
TC_API void tc_component_set_field_string(tc_component* c, const char* path, const char* value, tc_scene_handle scene);
TC_API void tc_component_set_field_mesh(tc_component* c, const char* path, tc_mesh_handle handle, tc_scene_handle scene);
TC_API void tc_component_set_field_material(tc_component* c, const char* path, tc_material_handle handle, tc_scene_handle scene);
TC_API void tc_component_set_field_vec3(tc_component* c, const char* path, tc_vec3 value, tc_scene_handle scene);
TC_API tc_vec3 tc_component_get_field_vec3(tc_component* c, const char* path);
TC_API void tc_component_set_field_quat(tc_component* c, const char* path, tc_quat value, tc_scene_handle scene);
TC_API tc_quat tc_component_get_field_quat(tc_component* c, const char* path);

// Simplified field getters.
TC_API int64_t tc_component_get_field_int(tc_component* c, const char* path);
TC_API float tc_component_get_field_float(tc_component* c, const char* path);
TC_API double tc_component_get_field_double(tc_component* c, const char* path);
TC_API bool tc_component_get_field_bool(tc_component* c, const char* path);
TC_API const char* tc_component_get_field_string(tc_component* c, const char* path);

#ifdef __cplusplus
}
#endif

#endif // TC_INSPECT_COMPONENT_ADAPTER_H
