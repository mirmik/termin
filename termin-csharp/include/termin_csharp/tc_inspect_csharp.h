// tc_inspect_csharp.h - C# inspect integration
// Allows C# components to register inspectable fields and provides
// getter/setter dispatch back to C# managed code.
#ifndef TC_INSPECT_CSHARP_H
#define TC_INSPECT_CSHARP_H

#include "inspect/tc_inspect.h"
#include "inspect/tc_runtime_type_registry.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct tc_csharp_inspect_descriptor tc_csharp_inspect_descriptor;

// Stage a complete C# inspect facet before publishing the runtime type.
TC_API tc_csharp_inspect_descriptor* tc_csharp_inspect_descriptor_create(
    const char* type_name
);
TC_API bool tc_csharp_inspect_descriptor_add_field(
    tc_csharp_inspect_descriptor* descriptor,
    const char* path,
    const char* label,
    const char* kind,       // "double", "bool", "string", "vec3", etc.
    double min,
    double max,
    double step
);
TC_API bool tc_csharp_inspect_descriptor_attach(
    tc_csharp_inspect_descriptor* inspect_descriptor,
    tc_runtime_type_descriptor* runtime_descriptor
);
TC_API void tc_csharp_inspect_descriptor_destroy(
    tc_csharp_inspect_descriptor* descriptor
);

// C# inspect getter/setter callbacks (set once at initialization).
// These are called from the inspect dispatcher when accessing C# component fields.
// obj is the void* body from tc_component (GCHandle IntPtr).
typedef tc_value (*tc_cs_inspect_get_fn)(void* obj, const char* type_name, const char* path);
typedef void (*tc_cs_inspect_set_fn)(void* obj, const char* type_name, const char* path, tc_value value, void* context);

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
