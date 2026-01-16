// tc_inspect.h - Field inspection/serialization for components
// Core knows only primitive types. Domain-specific types (mesh_handle, etc.)
// are registered as plugins by their respective modules.
#ifndef TC_INSPECT_H
#define TC_INSPECT_H

#include "tc_types.h"
#include <stdbool.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// Value type - tagged union for field values
// Core types only. Extensions use TC_VALUE_CUSTOM with kind string.
// ============================================================================

typedef enum tc_value_type {
    TC_VALUE_NIL = 0,
    TC_VALUE_BOOL,
    TC_VALUE_INT,
    TC_VALUE_FLOAT,
    TC_VALUE_DOUBLE,
    TC_VALUE_STRING,
    TC_VALUE_VEC3,
    TC_VALUE_QUAT,
    TC_VALUE_LIST,
    TC_VALUE_DICT,
    TC_VALUE_CUSTOM,    // Extension point: data is opaque, kind identifies type
} tc_value_type;

typedef struct tc_value tc_value;
typedef struct tc_value_list tc_value_list;
typedef struct tc_value_dict tc_value_dict;

struct tc_value_list {
    tc_value* items;
    size_t count;
    size_t capacity;
};

typedef struct tc_value_dict_entry {
    char* key;
    tc_value* value;
} tc_value_dict_entry;

struct tc_value_dict {
    tc_value_dict_entry* entries;
    size_t count;
    size_t capacity;
};

struct tc_value {
    tc_value_type type;
    const char* kind;   // For CUSTOM: registered kind name (interned)
    union {
        bool b;
        int64_t i;
        float f;
        double d;
        char* s;           // owned string
        tc_vec3 v3;
        tc_quat q;
        tc_value_list list;
        tc_value_dict dict;
        void* custom;      // For CUSTOM: opaque pointer, handler manages lifetime
    } data;
};

// ============================================================================
// Value constructors (core types)
// ============================================================================

TC_API tc_value tc_value_nil(void);
TC_API tc_value tc_value_bool(bool v);
TC_API tc_value tc_value_int(int64_t v);
TC_API tc_value tc_value_float(float v);
TC_API tc_value tc_value_double(double v);
TC_API tc_value tc_value_string(const char* s);
TC_API tc_value tc_value_vec3(tc_vec3 v);
TC_API tc_value tc_value_quat(tc_quat q);
TC_API tc_value tc_value_list_new(void);
TC_API tc_value tc_value_dict_new(void);

// Custom value - kind must be registered
TC_API tc_value tc_value_custom(const char* kind, void* data);

// ============================================================================
// Value operations
// ============================================================================

TC_API void tc_value_free(tc_value* v);
TC_API tc_value tc_value_copy(const tc_value* v);
TC_API bool tc_value_equals(const tc_value* a, const tc_value* b);

// List operations
TC_API void tc_value_list_push(tc_value* list, tc_value item);
TC_API tc_value* tc_value_list_get(tc_value* list, size_t index);
TC_API size_t tc_value_list_count(const tc_value* list);

// Dict operations
TC_API void tc_value_dict_set(tc_value* dict, const char* key, tc_value item);
TC_API tc_value* tc_value_dict_get(tc_value* dict, const char* key);
TC_API bool tc_value_dict_has(const tc_value* dict, const char* key);

// ============================================================================
// Custom type handler - for TC_VALUE_CUSTOM memory management
// (Separate from tc_kind.h which handles language-specific serialization)
// ============================================================================

typedef struct tc_custom_type_handler {
    // Kind name (e.g., "mesh_handle", "entity_handle")
    const char* kind;

    // Serialize value to JSON-compatible tc_value (string, dict, etc.)
    // Returns new value, caller owns it
    tc_value (*serialize)(const tc_value* v);

    // Deserialize from JSON-compatible tc_value
    // Returns new value with type=TC_VALUE_CUSTOM, caller owns it
    tc_value (*deserialize)(const tc_value* v);

    // Free custom data (called when value is freed)
    void (*free_data)(void* custom_data);

    // Copy custom data (for tc_value_copy)
    void* (*copy_data)(const void* custom_data);

    // Convert for setter (e.g., None → empty handle)
    // Can return same value if no conversion needed
    tc_value (*convert)(const tc_value* v);
} tc_custom_type_handler;

// Register a custom type handler
TC_API void tc_custom_type_register(const tc_custom_type_handler* handler);

// Unregister a custom type handler
TC_API void tc_custom_type_unregister(const char* kind);

// Get handler for a custom type (returns NULL if not registered)
TC_API const tc_custom_type_handler* tc_custom_type_get(const char* kind);

// Check if custom type is registered
TC_API bool tc_custom_type_exists(const char* kind);

// ============================================================================
// Language slots for field access
// Each language registers its getter/setter in dedicated slot
// ============================================================================

typedef enum tc_inspect_lang {
    TC_INSPECT_LANG_C = 0,
    TC_INSPECT_LANG_CPP = 1,
    TC_INSPECT_LANG_PYTHON = 2,
    TC_INSPECT_LANG_COUNT = 3
} tc_inspect_lang;

// Forward declaration
typedef struct tc_field_desc tc_field_desc;

// Per-field vtable for one language
typedef tc_value (*tc_field_getter)(void* obj, const tc_field_desc* field, void* user_data);
typedef void (*tc_field_setter)(void* obj, const tc_field_desc* field, tc_value value, void* user_data);
typedef void (*tc_field_action)(void* obj, const tc_field_desc* field, void* user_data);

typedef struct tc_field_vtable {
    tc_field_getter get;
    tc_field_setter set;
    tc_field_action action;
    void* user_data;
} tc_field_vtable;

// ============================================================================
// Field descriptor - metadata for one inspectable field
// Kind is a string, not enum - allows extension
// ============================================================================

typedef struct tc_enum_choice {
    int value;
    const char* label;
} tc_enum_choice;

struct tc_field_desc {
    const char* path;           // Field path ("mesh", "transform.position")
    const char* label;          // Display label
    const char* kind;           // "bool", "float", "mesh_handle", "list[entity_handle]"

    // Numeric constraints (for "int", "float", "double")
    double min;
    double max;
    double step;

    // Flags
    bool is_serializable;   // Include in serialization (default true)
    bool is_inspectable;    // Show in inspector (default true)

    // For enum fields
    const tc_enum_choice* choices;
    size_t choice_count;

    // Per-field language-specific access
    // Each language registers its getter/setter here
    tc_field_vtable lang[TC_INSPECT_LANG_COUNT];
};

// ============================================================================
// Type descriptor - all fields for one component type
// Note: vtable is now per-field (in tc_field_desc.lang[])
// ============================================================================

typedef struct tc_type_desc {
    const char* type_name;
    const char* base_type;      // Parent type for field inheritance
} tc_type_desc;

// ============================================================================
// Type Registry API
// ============================================================================

// Register a type (creates empty type, fields added separately)
TC_API void tc_inspect_register_type(const char* type_name, const char* base_type);

// Unregister a type and all its fields
TC_API void tc_inspect_unregister_type(const char* type_name);

// Check if type exists
TC_API bool tc_inspect_has_type(const char* type_name);

// Get base type (returns NULL if no base)
TC_API const char* tc_inspect_get_base_type(const char* type_name);

// Iterate registered types
TC_API size_t tc_inspect_type_count(void);
TC_API const char* tc_inspect_type_at(size_t index);

// ============================================================================
// Field Registry API
// ============================================================================

// Add a field to a type (copies the descriptor, type must exist)
TC_API void tc_inspect_add_field(const char* type_name, const tc_field_desc* field);

// Set vtable for a specific field and language
TC_API void tc_inspect_set_field_vtable(
    const char* type_name,
    const char* field_path,
    tc_inspect_lang lang,
    const tc_field_vtable* vtable
);

// Get vtable for a specific field and language (returns NULL if not set)
TC_API const tc_field_vtable* tc_inspect_get_field_vtable(
    const char* type_name,
    const char* field_path,
    tc_inspect_lang lang
);

// ============================================================================
// Field queries (includes inherited fields from base_type)
// ============================================================================

// Count all fields including inherited
TC_API size_t tc_inspect_field_count(const char* type_name);

// Get field by index (base fields first, then own fields)
TC_API const tc_field_desc* tc_inspect_field_at(const char* type_name, size_t index);

// Find field by path (searches own fields first, then base)
TC_API tc_field_desc* tc_inspect_find_field(const char* type_name, const char* path);

// ============================================================================
// Field access (uses per-field vtable)
// ============================================================================

// Get/set using first available language vtable
TC_API tc_value tc_inspect_get(void* obj, const char* type_name, const char* path);
TC_API void tc_inspect_set(void* obj, const char* type_name, const char* path, tc_value value);
TC_API void tc_inspect_action(void* obj, const char* type_name, const char* path);

// Get/set using specific language vtable
TC_API tc_value tc_inspect_get_lang(void* obj, const char* type_name, const char* path, tc_inspect_lang lang);
TC_API void tc_inspect_set_lang(void* obj, const char* type_name, const char* path, tc_value value, tc_inspect_lang lang);
TC_API void tc_inspect_action_lang(void* obj, const char* type_name, const char* path, tc_inspect_lang lang);

// ============================================================================
// Serialization
// ============================================================================

// Forward declaration for scene (needed for deserialization with scene context)
struct tc_scene;
typedef struct tc_scene tc_scene;

// Serialize all fields to dict (only is_serializable fields)
TC_API tc_value tc_inspect_serialize(void* obj, const char* type_name);

// Deserialize from dict
TC_API void tc_inspect_deserialize(void* obj, const char* type_name, const tc_value* data);

// Deserialize from dict with scene context (for entity_handle deserialization)
TC_API void tc_inspect_deserialize_with_scene(void* obj, const char* type_name, const tc_value* data, tc_scene* scene);

// ============================================================================
// Parameterized kinds (e.g., "list[entity_handle]")
// ============================================================================

// Parse "list[T]" → ("list", "T"), returns false if not parameterized
TC_API bool tc_kind_parse(const char* kind, char* container, size_t container_size,
                          char* element, size_t element_size);

// ============================================================================
// JSON interop
// ============================================================================

TC_API char* tc_value_to_json(const tc_value* v);
TC_API tc_value tc_value_from_json(const char* json);

// ============================================================================
// Cleanup
// ============================================================================

TC_API void tc_inspect_cleanup(void);

#ifdef __cplusplus
}
#endif

#endif // TC_INSPECT_H
