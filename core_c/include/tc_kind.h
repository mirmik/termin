// tc_kind.h - Language-agnostic kind serialization system
// Each language (C, C++, Python, Rust) registers its handlers in dedicated slots.
#pragma once

#include "tc_types.h"
#include "tc_inspect.h"

#ifdef __cplusplus
extern "C" {
#endif

// Language slots
typedef enum {
    TC_KIND_LANG_C = 0,
    TC_KIND_LANG_CPP = 1,
    TC_KIND_LANG_PYTHON = 2,
    TC_KIND_LANG_RUST = 3,
    TC_KIND_LANG_COUNT = 4
} tc_kind_lang;

// Callback signatures - work with tc_value as universal format
typedef tc_value (*tc_kind_serialize_fn)(const tc_value* input, void* user_data);
typedef tc_value (*tc_kind_deserialize_fn)(const tc_value* input, tc_scene* scene, void* user_data);

// Vtable for one language
typedef struct {
    tc_kind_serialize_fn serialize;
    tc_kind_deserialize_fn deserialize;
    void* user_data;
} tc_kind_lang_vtable;

// Kind entry - has slots for each language
typedef struct {
    char name[64];
    tc_kind_lang_vtable lang[TC_KIND_LANG_COUNT];
} tc_kind_entry;

// ============================================================================
// Registry API
// ============================================================================

// Register handler for a kind+language combination
TC_API void tc_kind_register(
    const char* name,
    tc_kind_lang lang,
    tc_kind_serialize_fn serialize,
    tc_kind_deserialize_fn deserialize,
    void* user_data
);

// Unregister handler for a kind+language
TC_API void tc_kind_unregister(const char* name, tc_kind_lang lang);

// Get kind entry (returns NULL if not found)
TC_API tc_kind_entry* tc_kind_get(const char* name);

// Get or create kind entry
TC_API tc_kind_entry* tc_kind_get_or_create(const char* name);

// Check if kind exists (any language)
TC_API bool tc_kind_exists(const char* name);

// Check if kind has handler for specific language
TC_API bool tc_kind_has_lang(const char* name, tc_kind_lang lang);

// Get all registered kind names
TC_API size_t tc_kind_list(const char** out_names, size_t max_count);

// Cleanup all kinds
TC_API void tc_kind_cleanup(void);

// ============================================================================
// Convenience functions
// ============================================================================

// Serialize using specified language's handler
TC_API tc_value tc_kind_serialize(const char* name, tc_kind_lang lang, const tc_value* input);

// Deserialize using specified language's handler
TC_API tc_value tc_kind_deserialize(const char* name, tc_kind_lang lang, const tc_value* input, tc_scene* scene);

// Find first available language handler and serialize
TC_API tc_value tc_kind_serialize_any(const char* name, const tc_value* input);

// Find first available language handler and deserialize
TC_API tc_value tc_kind_deserialize_any(const char* name, const tc_value* input, tc_scene* scene);

#ifdef __cplusplus
}
#endif
