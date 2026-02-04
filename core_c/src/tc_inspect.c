// tc_inspect.c - Field inspection/serialization implementation
// C is a dispatcher only - routes calls to language-specific vtables
#include "inspect/tc_inspect.h"
#include "inspect/tc_kind.h"
#include "tc_log.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

// Cross-platform strdup
#ifdef _WIN32
#define tc_strdup _strdup
#else
#define tc_strdup strdup
#endif

// ============================================================================
// Value constructors
// ============================================================================

tc_value tc_value_nil(void) {
    return (tc_value){.type = TC_VALUE_NIL};
}

tc_value tc_value_bool(bool v) {
    tc_value val = {.type = TC_VALUE_BOOL};
    val.data.b = v;
    return val;
}

tc_value tc_value_int(int64_t v) {
    tc_value val = {.type = TC_VALUE_INT};
    val.data.i = v;
    return val;
}

tc_value tc_value_float(float v) {
    tc_value val = {.type = TC_VALUE_FLOAT};
    val.data.f = v;
    return val;
}

tc_value tc_value_double(double v) {
    tc_value val = {.type = TC_VALUE_DOUBLE};
    val.data.d = v;
    return val;
}

tc_value tc_value_string(const char* s) {
    tc_value val = {.type = TC_VALUE_STRING};
    val.data.s = s ? tc_strdup(s) : NULL;
    return val;
}

tc_value tc_value_vec3(tc_vec3 v) {
    tc_value val = {.type = TC_VALUE_VEC3};
    val.data.v3 = v;
    return val;
}

tc_value tc_value_quat(tc_quat q) {
    tc_value val = {.type = TC_VALUE_QUAT};
    val.data.q = q;
    return val;
}

tc_value tc_value_list_new(void) {
    tc_value val = {.type = TC_VALUE_LIST};
    val.data.list.items = NULL;
    val.data.list.count = 0;
    val.data.list.capacity = 0;
    return val;
}

tc_value tc_value_dict_new(void) {
    tc_value val = {.type = TC_VALUE_DICT};
    val.data.dict.entries = NULL;
    val.data.dict.count = 0;
    val.data.dict.capacity = 0;
    return val;
}

// ============================================================================
// Value operations
// ============================================================================

void tc_value_free(tc_value* v) {
    if (!v) return;

    switch (v->type) {
    case TC_VALUE_STRING:
        free(v->data.s);
        v->data.s = NULL;
        break;

    case TC_VALUE_LIST:
        for (size_t i = 0; i < v->data.list.count; i++) {
            tc_value_free(&v->data.list.items[i]);
        }
        free(v->data.list.items);
        v->data.list.items = NULL;
        v->data.list.count = 0;
        v->data.list.capacity = 0;
        break;

    case TC_VALUE_DICT:
        for (size_t i = 0; i < v->data.dict.count; i++) {
            free(v->data.dict.entries[i].key);
            tc_value_free(v->data.dict.entries[i].value);
            free(v->data.dict.entries[i].value);
        }
        free(v->data.dict.entries);
        v->data.dict.entries = NULL;
        v->data.dict.count = 0;
        v->data.dict.capacity = 0;
        break;

    default:
        break;
    }

    v->type = TC_VALUE_NIL;
}

tc_value tc_value_copy(const tc_value* v) {
    if (!v) return tc_value_nil();

    tc_value copy = *v;

    switch (v->type) {
    case TC_VALUE_STRING:
        copy.data.s = v->data.s ? tc_strdup(v->data.s) : NULL;
        break;

    case TC_VALUE_LIST:
        if (v->data.list.count > 0) {
            copy.data.list.items = malloc(v->data.list.count * sizeof(tc_value));
            copy.data.list.capacity = v->data.list.count;
            for (size_t i = 0; i < v->data.list.count; i++) {
                copy.data.list.items[i] = tc_value_copy(&v->data.list.items[i]);
            }
        }
        break;

    case TC_VALUE_DICT:
        if (v->data.dict.count > 0) {
            copy.data.dict.entries = malloc(v->data.dict.count * sizeof(tc_value_dict_entry));
            copy.data.dict.capacity = v->data.dict.count;
            for (size_t i = 0; i < v->data.dict.count; i++) {
                copy.data.dict.entries[i].key = tc_strdup(v->data.dict.entries[i].key);
                copy.data.dict.entries[i].value = malloc(sizeof(tc_value));
                *copy.data.dict.entries[i].value = tc_value_copy(v->data.dict.entries[i].value);
            }
        }
        break;

    default:
        break;
    }

    return copy;
}

// ============================================================================
// List operations
// ============================================================================

static void list_ensure_capacity(tc_value_list* list, size_t needed) {
    if (list->capacity >= needed) return;

    size_t new_cap = list->capacity == 0 ? 4 : list->capacity * 2;
    while (new_cap < needed) new_cap *= 2;

    tc_value* new_items = realloc(list->items, new_cap * sizeof(tc_value));
    if (!new_items) return;

    list->items = new_items;
    list->capacity = new_cap;
}

void tc_value_list_push(tc_value* list, tc_value item) {
    if (!list || list->type != TC_VALUE_LIST) return;

    list_ensure_capacity(&list->data.list, list->data.list.count + 1);
    list->data.list.items[list->data.list.count++] = item;
}

tc_value* tc_value_list_get(tc_value* list, size_t index) {
    if (!list || list->type != TC_VALUE_LIST) return NULL;
    if (index >= list->data.list.count) return NULL;
    return &list->data.list.items[index];
}

size_t tc_value_list_count(const tc_value* list) {
    if (!list || list->type != TC_VALUE_LIST) return 0;
    return list->data.list.count;
}

// ============================================================================
// Dict operations
// ============================================================================

static void dict_ensure_capacity(tc_value_dict* dict, size_t needed) {
    if (dict->capacity >= needed) return;

    size_t new_cap = dict->capacity == 0 ? 8 : dict->capacity * 2;
    while (new_cap < needed) new_cap *= 2;

    tc_value_dict_entry* new_entries = realloc(dict->entries, new_cap * sizeof(tc_value_dict_entry));
    if (!new_entries) return;

    dict->entries = new_entries;
    dict->capacity = new_cap;
}

void tc_value_dict_set(tc_value* dict, const char* key, tc_value item) {
    if (!dict || dict->type != TC_VALUE_DICT || !key) return;

    // Check if key exists
    for (size_t i = 0; i < dict->data.dict.count; i++) {
        if (strcmp(dict->data.dict.entries[i].key, key) == 0) {
            tc_value_free(dict->data.dict.entries[i].value);
            *dict->data.dict.entries[i].value = item;
            return;
        }
    }

    // Add new entry
    dict_ensure_capacity(&dict->data.dict, dict->data.dict.count + 1);
    tc_value_dict_entry* e = &dict->data.dict.entries[dict->data.dict.count++];
    e->key = tc_strdup(key);
    e->value = malloc(sizeof(tc_value));
    *e->value = item;
}

tc_value* tc_value_dict_get(tc_value* dict, const char* key) {
    if (!dict || dict->type != TC_VALUE_DICT || !key) return NULL;

    for (size_t i = 0; i < dict->data.dict.count; i++) {
        if (strcmp(dict->data.dict.entries[i].key, key) == 0) {
            return dict->data.dict.entries[i].value;
        }
    }
    return NULL;
}

bool tc_value_dict_has(const tc_value* dict, const char* key) {
    if (!dict || dict->type != TC_VALUE_DICT || !key) return false;

    for (size_t i = 0; i < dict->data.dict.count; i++) {
        if (strcmp(dict->data.dict.entries[i].key, key) == 0) {
            return true;
        }
    }
    return false;
}

size_t tc_value_list_size(const tc_value* list) {
    if (!list || list->type != TC_VALUE_LIST) return 0;
    return list->data.list.count;
}

size_t tc_value_dict_size(const tc_value* dict) {
    if (!dict || dict->type != TC_VALUE_DICT) return 0;
    return dict->data.dict.count;
}

tc_value* tc_value_dict_get_at(tc_value* dict, size_t index, const char** out_key) {
    if (!dict || dict->type != TC_VALUE_DICT) return NULL;
    if (index >= dict->data.dict.count) return NULL;
    if (out_key) *out_key = dict->data.dict.entries[index].key;
    return dict->data.dict.entries[index].value;
}

// ============================================================================
// Parse parameterized kind
// ============================================================================

bool tc_kind_parse(const char* kind, char* container, size_t container_size,
                   char* element, size_t element_size) {
    if (!kind) return false;

    const char* bracket = strchr(kind, '[');
    if (!bracket) return false;

    const char* end_bracket = strrchr(kind, ']');
    if (!end_bracket || end_bracket <= bracket) return false;

    size_t container_len = bracket - kind;
    size_t element_len = end_bracket - bracket - 1;

    if (container_len >= container_size || element_len >= element_size) return false;

    strncpy(container, kind, container_len);
    container[container_len] = '\0';

    strncpy(element, bracket + 1, element_len);
    element[element_len] = '\0';

    return true;
}

// ============================================================================
// Language vtable dispatcher
// ============================================================================

static tc_inspect_lang_vtable g_vtables[TC_INSPECT_LANG_COUNT] = {0};

void tc_inspect_set_lang_vtable(tc_inspect_lang lang, const tc_inspect_lang_vtable* vtable) {
    if (lang >= 0 && lang < TC_INSPECT_LANG_COUNT && vtable) {
        g_vtables[lang] = *vtable;
    }
}

const tc_inspect_lang_vtable* tc_inspect_get_lang_vtable(tc_inspect_lang lang) {
    if (lang >= 0 && lang < TC_INSPECT_LANG_COUNT) {
        if (g_vtables[lang].has_type) {
            return &g_vtables[lang];
        }
    }
    return NULL;
}

// ============================================================================
// Type queries
// ============================================================================

bool tc_inspect_has_type(const char* type_name) {
    if (!type_name) return false;
    for (int i = 0; i < TC_INSPECT_LANG_COUNT; i++) {
        if (g_vtables[i].has_type && g_vtables[i].has_type(type_name, g_vtables[i].ctx)) {
            return true;
        }
    }
    return false;
}

tc_inspect_lang tc_inspect_type_lang(const char* type_name) {
    if (!type_name) return TC_INSPECT_LANG_COUNT;
    for (int i = 0; i < TC_INSPECT_LANG_COUNT; i++) {
        if (g_vtables[i].has_type && g_vtables[i].has_type(type_name, g_vtables[i].ctx)) {
            return (tc_inspect_lang)i;
        }
    }
    return TC_INSPECT_LANG_COUNT;
}

const char* tc_inspect_get_base_type(const char* type_name) {
    tc_inspect_lang lang = tc_inspect_type_lang(type_name);
    if (lang < TC_INSPECT_LANG_COUNT && g_vtables[lang].get_parent) {
        return g_vtables[lang].get_parent(type_name, g_vtables[lang].ctx);
    }
    return NULL;
}

// ============================================================================
// Field queries
// ============================================================================

size_t tc_inspect_field_count(const char* type_name) {
    tc_inspect_lang lang = tc_inspect_type_lang(type_name);
    if (lang < TC_INSPECT_LANG_COUNT && g_vtables[lang].field_count) {
        return g_vtables[lang].field_count(type_name, g_vtables[lang].ctx);
    }
    return 0;
}

bool tc_inspect_get_field_info(const char* type_name, size_t index, tc_field_info* out) {
    if (!out) return false;
    tc_inspect_lang lang = tc_inspect_type_lang(type_name);
    if (lang < TC_INSPECT_LANG_COUNT && g_vtables[lang].get_field) {
        return g_vtables[lang].get_field(type_name, index, out, g_vtables[lang].ctx);
    }
    return false;
}

bool tc_inspect_find_field_info(const char* type_name, const char* path, tc_field_info* out) {
    if (!out) return false;
    tc_inspect_lang lang = tc_inspect_type_lang(type_name);
    if (lang < TC_INSPECT_LANG_COUNT && g_vtables[lang].find_field) {
        return g_vtables[lang].find_field(type_name, path, out, g_vtables[lang].ctx);
    }
    return false;
}

// ============================================================================
// Field access
// ============================================================================

tc_value tc_inspect_get(void* obj, const char* type_name, const char* path) {
    tc_inspect_lang lang = tc_inspect_type_lang(type_name);
    if (lang >= TC_INSPECT_LANG_COUNT) {
        tc_log(TC_LOG_WARN, "[Inspect] tc_inspect_get: type '%s' not found in any language vtable", type_name ? type_name : "null");
        return tc_value_nil();
    }
    if (!g_vtables[lang].get) {
        tc_log(TC_LOG_WARN, "[Inspect] tc_inspect_get: no getter for type '%s' (lang=%d)", type_name ? type_name : "null", lang);
        return tc_value_nil();
    }
    return g_vtables[lang].get(obj, type_name, path, g_vtables[lang].ctx);
}

void tc_inspect_set(void* obj, const char* type_name, const char* path, tc_value value, tc_scene_handle scene) {
    tc_inspect_lang lang = tc_inspect_type_lang(type_name);
    if (lang >= TC_INSPECT_LANG_COUNT) {
        tc_log(TC_LOG_WARN, "[Inspect] tc_inspect_set: type '%s' not found in any language vtable", type_name ? type_name : "null");
        return;
    }
    if (!g_vtables[lang].set) {
        tc_log(TC_LOG_WARN, "[Inspect] tc_inspect_set: no setter for type '%s' (lang=%d)", type_name ? type_name : "null", lang);
        return;
    }
    g_vtables[lang].set(obj, type_name, path, value, scene, g_vtables[lang].ctx);
}

void tc_inspect_action(void* obj, const char* type_name, const char* path) {
    tc_inspect_lang lang = tc_inspect_type_lang(type_name);
    if (lang < TC_INSPECT_LANG_COUNT && g_vtables[lang].action) {
        g_vtables[lang].action(obj, type_name, path, g_vtables[lang].ctx);
    }
}

// ============================================================================
// Serialization
// ============================================================================

tc_value tc_inspect_serialize(void* obj, const char* type_name) {
    tc_value result = tc_value_dict_new();

    size_t count = tc_inspect_field_count(type_name);
    for (size_t i = 0; i < count; i++) {
        tc_field_info f;
        if (!tc_inspect_get_field_info(type_name, i, &f)) continue;
        if (!f.is_serializable) continue;

        tc_value val = tc_inspect_get(obj, type_name, f.path);
        if (val.type == TC_VALUE_NIL) continue;

        // Try tc_kind serialization
        if (tc_kind_exists(f.kind)) {
            tc_value serialized = tc_kind_serialize_any(f.kind, &val);
            if (serialized.type != TC_VALUE_NIL) {
                tc_value_dict_set(&result, f.path, serialized);
                tc_value_free(&val);
                continue;
            }
        }

        // No serializer - store value as-is
        tc_value_dict_set(&result, f.path, val);
    }

    return result;
}

void tc_inspect_deserialize(void* obj, const char* type_name, const tc_value* data, tc_scene_handle scene) {
    if (!obj) {
        tc_log(TC_LOG_WARN, "[Inspect] tc_inspect_deserialize: obj is NULL for type '%s'", type_name ? type_name : "unknown");
        return;
    }
    if (!type_name) {
        tc_log(TC_LOG_WARN, "[Inspect] tc_inspect_deserialize: type_name is NULL");
        return;
    }
    if (!data) {
        tc_log(TC_LOG_WARN, "[Inspect] tc_inspect_deserialize: data is NULL for type '%s'", type_name);
        return;
    }
    if (data->type != TC_VALUE_DICT) {
        tc_log(TC_LOG_WARN, "[Inspect] tc_inspect_deserialize: data is not a dict for type '%s' (got type %d)", type_name, data->type);
        return;
    }

    size_t count = tc_inspect_field_count(type_name);
    if (count == 0) {
        tc_log(TC_LOG_WARN, "[Inspect] tc_inspect_deserialize: no fields registered for type '%s'", type_name);
        return;
    }

    for (size_t i = 0; i < count; i++) {
        tc_field_info f;
        if (!tc_inspect_get_field_info(type_name, i, &f)) continue;
        if (!f.is_serializable) continue;

        tc_value* field_data = tc_value_dict_get((tc_value*)data, f.path);
        if (!field_data || field_data->type == TC_VALUE_NIL) continue;

        // Try tc_kind deserialization
        if (tc_kind_exists(f.kind)) {
            tc_value deserialized = tc_kind_deserialize_any(f.kind, field_data, scene);
            if (deserialized.type != TC_VALUE_NIL) {
                tc_inspect_set(obj, type_name, f.path, deserialized, scene);
                tc_value_free(&deserialized);
                continue;
            }
        }

        // No deserializer - set value as-is
        tc_inspect_set(obj, type_name, f.path, *field_data, scene);
    }
}

// ============================================================================
// Cleanup
// ============================================================================

void tc_inspect_cleanup(void) {
    // Nothing to clean up - languages manage their own storage
    memset(g_vtables, 0, sizeof(g_vtables));
}
