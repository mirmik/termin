// tc_inspect_csharp.h - C# inspect integration
// Allows C# components to register inspectable fields and provides
// getter/setter dispatch back to C# managed code.
#ifndef TC_INSPECT_CSHARP_H
#define TC_INSPECT_CSHARP_H

#include "inspect/tc_inspect.h"

#ifdef __cplusplus
extern "C" {
#endif

// Register an inspectable field for a C# component type.
// Strings are copied internally — caller does not need to keep them alive.
TC_API void tc_inspect_csharp_register_field(
    const char* type_name,
    const char* path,
    const char* label,
    const char* kind,       // "double", "bool", "string", "vec3", etc.
    double min,
    double max,
    double step
);

// Mark a C# type as registered (even if it has no fields).
TC_API void tc_inspect_csharp_register_type(const char* type_name);

// C# inspect getter/setter callbacks (set once at initialization).
// These are called from the inspect dispatcher when accessing C# component fields.
// obj is the void* body from tc_component (GCHandle IntPtr).
typedef tc_value (*tc_cs_inspect_get_fn)(void* obj, const char* type_name, const char* path);
typedef void (*tc_cs_inspect_set_fn)(void* obj, const char* type_name, const char* path, tc_value value, tc_scene_handle scene);

TC_API void tc_inspect_set_csharp_callbacks(
    tc_cs_inspect_get_fn getter,
    tc_cs_inspect_set_fn setter
);

// Initialize C# inspect vtable (registers with tc_inspect_set_lang_vtable).
// Called automatically when tc_inspect_set_csharp_callbacks is first called.
TC_API void tc_inspect_csharp_init(void);

#ifdef __cplusplus
}
#endif

#endif // TC_INSPECT_CSHARP_H
