// tc_inspect.c - Field inspection/serialization implementation
#include "../include/tc_inspect.h"
#include "../include/tc_kind.h"
#include "../include/tc_log.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

// ============================================================================
// Value constructors
// ============================================================================

tc_value tc_value_nil(void) {
    return (tc_value){.type = TC_VALUE_NIL, .kind = NULL};
}

tc_value tc_value_bool(bool v) {
    tc_value val = {.type = TC_VALUE_BOOL, .kind = NULL};
    val.data.b = v;
    return val;
}

tc_value tc_value_int(int64_t v) {
    tc_value val = {.type = TC_VALUE_INT, .kind = NULL};
    val.data.i = v;
    return val;
}

tc_value tc_value_float(float v) {
    tc_value val = {.type = TC_VALUE_FLOAT, .kind = NULL};
    val.data.f = v;
    return val;
}

tc_value tc_value_double(double v) {
    tc_value val = {.type = TC_VALUE_DOUBLE, .kind = NULL};
    val.data.d = v;
    return val;
}

tc_value tc_value_string(const char* s) {
    tc_value val = {.type = TC_VALUE_STRING, .kind = NULL};
    val.data.s = s ? strdup(s) : NULL;
    return val;
}

tc_value tc_value_vec3(tc_vec3 v) {
    tc_value val = {.type = TC_VALUE_VEC3, .kind = NULL};
    val.data.v3 = v;
    return val;
}

tc_value tc_value_quat(tc_quat q) {
    tc_value val = {.type = TC_VALUE_QUAT, .kind = NULL};
    val.data.q = q;
    return val;
}

tc_value tc_value_list_new(void) {
    tc_value val = {.type = TC_VALUE_LIST, .kind = NULL};
    val.data.list.items = NULL;
    val.data.list.count = 0;
    val.data.list.capacity = 0;
    return val;
}

tc_value tc_value_dict_new(void) {
    tc_value val = {.type = TC_VALUE_DICT, .kind = NULL};
    val.data.dict.entries = NULL;
    val.data.dict.count = 0;
    val.data.dict.capacity = 0;
    return val;
}

tc_value tc_value_custom(const char* kind, void* data) {
    tc_value val = {.type = TC_VALUE_CUSTOM};
    val.kind = kind;  // Assumed interned
    val.data.custom = data;
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

    case TC_VALUE_CUSTOM: {
        const tc_custom_type_handler* h = tc_custom_type_get(v->kind);
        if (h && h->free_data) {
            h->free_data(v->data.custom);
        }
        v->data.custom = NULL;
        break;
    }

    default:
        break;
    }

    v->type = TC_VALUE_NIL;
    v->kind = NULL;
}

tc_value tc_value_copy(const tc_value* v) {
    if (!v) return tc_value_nil();

    tc_value copy = *v;

    switch (v->type) {
    case TC_VALUE_STRING:
        copy.data.s = v->data.s ? strdup(v->data.s) : NULL;
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
                copy.data.dict.entries[i].key = strdup(v->data.dict.entries[i].key);
                copy.data.dict.entries[i].value = malloc(sizeof(tc_value));
                *copy.data.dict.entries[i].value = tc_value_copy(v->data.dict.entries[i].value);
            }
        }
        break;

    case TC_VALUE_CUSTOM: {
        const tc_custom_type_handler* h = tc_custom_type_get(v->kind);
        if (h && h->copy_data) {
            copy.data.custom = h->copy_data(v->data.custom);
        } else {
            copy.data.custom = v->data.custom;  // Shallow copy
        }
        break;
    }

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
    e->key = strdup(key);
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

// ============================================================================
// Custom type handler registry (for TC_VALUE_CUSTOM memory management)
// ============================================================================

#define MAX_CUSTOM_TYPE_HANDLERS 64

static struct {
    tc_custom_type_handler handlers[MAX_CUSTOM_TYPE_HANDLERS];
    size_t count;
} g_custom_type_registry = {{{0}}, 0};

void tc_custom_type_register(const tc_custom_type_handler* handler) {
    if (!handler || !handler->kind) return;
    if (g_custom_type_registry.count >= MAX_CUSTOM_TYPE_HANDLERS) return;

    // Check if already registered
    for (size_t i = 0; i < g_custom_type_registry.count; i++) {
        if (strcmp(g_custom_type_registry.handlers[i].kind, handler->kind) == 0) {
            g_custom_type_registry.handlers[i] = *handler;
            return;
        }
    }

    g_custom_type_registry.handlers[g_custom_type_registry.count++] = *handler;
}

void tc_custom_type_unregister(const char* kind) {
    if (!kind) return;

    for (size_t i = 0; i < g_custom_type_registry.count; i++) {
        if (strcmp(g_custom_type_registry.handlers[i].kind, kind) == 0) {
            // Shift remaining
            for (size_t j = i; j < g_custom_type_registry.count - 1; j++) {
                g_custom_type_registry.handlers[j] = g_custom_type_registry.handlers[j + 1];
            }
            g_custom_type_registry.count--;
            return;
        }
    }
}

const tc_custom_type_handler* tc_custom_type_get(const char* kind) {
    if (!kind) return NULL;

    for (size_t i = 0; i < g_custom_type_registry.count; i++) {
        if (strcmp(g_custom_type_registry.handlers[i].kind, kind) == 0) {
            return &g_custom_type_registry.handlers[i];
        }
    }
    return NULL;
}

bool tc_custom_type_exists(const char* kind) {
    return tc_custom_type_get(kind) != NULL;
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
// Type registry
// ============================================================================

#define MAX_TYPES 128
#define MAX_FIELDS_PER_TYPE 64

typedef struct {
    char type_name[128];
    char base_type[128];
    tc_field_desc fields[MAX_FIELDS_PER_TYPE];
    size_t field_count;
} tc_type_entry;

static struct {
    tc_type_entry types[MAX_TYPES];
    size_t count;
} g_type_registry = {{{0}}, 0};

// Find type entry (internal)
static tc_type_entry* find_type_entry(const char* type_name) {
    if (!type_name) return NULL;
    for (size_t i = 0; i < g_type_registry.count; i++) {
        if (strcmp(g_type_registry.types[i].type_name, type_name) == 0) {
            return &g_type_registry.types[i];
        }
    }
    return NULL;
}

void tc_inspect_register_type(const char* type_name, const char* base_type) {
    if (!type_name) return;
    if (g_type_registry.count >= MAX_TYPES) return;

    // Check if already exists
    tc_type_entry* existing = find_type_entry(type_name);
    if (existing) {
        // Update base_type
        if (base_type) {
            strncpy(existing->base_type, base_type, sizeof(existing->base_type) - 1);
        } else {
            existing->base_type[0] = '\0';
        }
        return;
    }

    // Create new entry
    tc_type_entry* entry = &g_type_registry.types[g_type_registry.count++];
    memset(entry, 0, sizeof(tc_type_entry));
    strncpy(entry->type_name, type_name, sizeof(entry->type_name) - 1);
    if (base_type) {
        strncpy(entry->base_type, base_type, sizeof(entry->base_type) - 1);
    }
}

void tc_inspect_unregister_type(const char* type_name) {
    if (!type_name) return;

    for (size_t i = 0; i < g_type_registry.count; i++) {
        if (strcmp(g_type_registry.types[i].type_name, type_name) == 0) {
            // Shift remaining
            for (size_t j = i; j < g_type_registry.count - 1; j++) {
                g_type_registry.types[j] = g_type_registry.types[j + 1];
            }
            g_type_registry.count--;
            return;
        }
    }
}

bool tc_inspect_has_type(const char* type_name) {
    return find_type_entry(type_name) != NULL;
}

const char* tc_inspect_get_base_type(const char* type_name) {
    tc_type_entry* entry = find_type_entry(type_name);
    if (!entry || entry->base_type[0] == '\0') return NULL;
    return entry->base_type;
}

size_t tc_inspect_type_count(void) {
    return g_type_registry.count;
}

const char* tc_inspect_type_at(size_t index) {
    if (index >= g_type_registry.count) return NULL;
    return g_type_registry.types[index].type_name;
}

// ============================================================================
// Field registry
// ============================================================================

void tc_inspect_add_field(const char* type_name, const tc_field_desc* field) {
    if (!type_name || !field || !field->path) return;

    tc_type_entry* entry = find_type_entry(type_name);
    if (!entry) {
        // Auto-create type if not exists
        tc_inspect_register_type(type_name, NULL);
        entry = find_type_entry(type_name);
    }
    if (!entry || entry->field_count >= MAX_FIELDS_PER_TYPE) return;

    // Check if field already exists
    for (size_t i = 0; i < entry->field_count; i++) {
        if (strcmp(entry->fields[i].path, field->path) == 0) {
            // Update existing field (preserve vtables)
            tc_field_vtable saved_vtables[TC_INSPECT_LANG_COUNT];
            memcpy(saved_vtables, entry->fields[i].lang, sizeof(saved_vtables));
            entry->fields[i] = *field;
            memcpy(entry->fields[i].lang, saved_vtables, sizeof(saved_vtables));
            return;
        }
    }

    // Add new field
    entry->fields[entry->field_count++] = *field;
}

void tc_inspect_set_field_vtable(
    const char* type_name,
    const char* field_path,
    tc_inspect_lang lang,
    const tc_field_vtable* vtable
) {
    if (!type_name || !field_path || lang < 0 || lang >= TC_INSPECT_LANG_COUNT) return;

    tc_field_desc* field = tc_inspect_find_field(type_name, field_path);
    if (!field) return;

    if (vtable) {
        field->lang[lang] = *vtable;
    } else {
        memset(&field->lang[lang], 0, sizeof(tc_field_vtable));
    }
}

const tc_field_vtable* tc_inspect_get_field_vtable(
    const char* type_name,
    const char* field_path,
    tc_inspect_lang lang
) {
    if (lang < 0 || lang >= TC_INSPECT_LANG_COUNT) return NULL;

    tc_field_desc* field = tc_inspect_find_field(type_name, field_path);
    if (!field) return NULL;

    if (field->lang[lang].get || field->lang[lang].set) {
        return &field->lang[lang];
    }
    return NULL;
}

// ============================================================================
// Field queries (with inheritance)
// ============================================================================

// Count own fields (not inherited)
static size_t count_own_fields(const char* type_name) {
    tc_type_entry* entry = find_type_entry(type_name);
    return entry ? entry->field_count : 0;
}

size_t tc_inspect_field_count(const char* type_name) {
    tc_type_entry* entry = find_type_entry(type_name);
    if (!entry) return 0;

    size_t count = entry->field_count;

    // Add base type fields
    if (entry->base_type[0] != '\0') {
        count += tc_inspect_field_count(entry->base_type);
    }

    return count;
}

const tc_field_desc* tc_inspect_field_at(const char* type_name, size_t index) {
    tc_type_entry* entry = find_type_entry(type_name);
    if (!entry) return NULL;

    // First return base type fields
    if (entry->base_type[0] != '\0') {
        size_t base_count = tc_inspect_field_count(entry->base_type);
        if (index < base_count) {
            return tc_inspect_field_at(entry->base_type, index);
        }
        index -= base_count;
    }

    // Then own fields
    if (index < entry->field_count) {
        return &entry->fields[index];
    }

    return NULL;
}

tc_field_desc* tc_inspect_find_field(const char* type_name, const char* path) {
    if (!type_name || !path) return NULL;

    tc_type_entry* entry = find_type_entry(type_name);
    if (!entry) return NULL;

    // Search own fields first
    for (size_t i = 0; i < entry->field_count; i++) {
        if (strcmp(entry->fields[i].path, path) == 0) {
            return &entry->fields[i];
        }
    }

    // Search base type
    if (entry->base_type[0] != '\0') {
        return tc_inspect_find_field(entry->base_type, path);
    }

    return NULL;
}

// ============================================================================
// Field access (per-field vtable)
// ============================================================================

// Find first available vtable for a field
static const tc_field_vtable* find_any_vtable(const tc_field_desc* field) {
    if (!field) return NULL;
    for (int lang = 0; lang < TC_INSPECT_LANG_COUNT; lang++) {
        if (field->lang[lang].get || field->lang[lang].set) {
            return &field->lang[lang];
        }
    }
    return NULL;
}

tc_value tc_inspect_get(void* obj, const char* type_name, const char* path) {
    tc_field_desc* field = tc_inspect_find_field(type_name, path);
    if (!field) return tc_value_nil();

    const tc_field_vtable* vtable = find_any_vtable(field);
    if (!vtable || !vtable->get) return tc_value_nil();

    return vtable->get(obj, field, vtable->user_data);
}

void tc_inspect_set(void* obj, const char* type_name, const char* path, tc_value value, tc_scene* scene) {
    tc_field_desc* field = tc_inspect_find_field(type_name, path);
    if (!field) {
        tc_log(TC_LOG_WARN, "[tc_inspect_set] field not found: %s.%s", type_name, path);
        return;
    }

    const tc_field_vtable* vtable = find_any_vtable(field);
    if (!vtable || !vtable->set) {
        tc_log(TC_LOG_WARN, "[tc_inspect_set] no vtable/setter for %s.%s", type_name, path);
        return;
    }

    // Apply convert if custom type handler exists
    const tc_custom_type_handler* h = tc_custom_type_get(field->kind);
    if (h && h->convert) {
        tc_value converted = h->convert(&value);
        vtable->set(obj, field, converted, vtable->user_data, scene);
        if (converted.type != value.type || converted.data.custom != value.data.custom) {
            tc_value_free(&converted);
        }
    } else {
        vtable->set(obj, field, value, vtable->user_data, scene);
    }
}

void tc_inspect_action(void* obj, const char* type_name, const char* path) {
    tc_field_desc* field = tc_inspect_find_field(type_name, path);
    if (!field) return;

    const tc_field_vtable* vtable = find_any_vtable(field);
    if (!vtable || !vtable->action) return;

    vtable->action(obj, field, vtable->user_data);
}

// Language-specific access
tc_value tc_inspect_get_lang(void* obj, const char* type_name, const char* path, tc_inspect_lang lang) {
    if (lang < 0 || lang >= TC_INSPECT_LANG_COUNT) return tc_value_nil();

    tc_field_desc* field = tc_inspect_find_field(type_name, path);
    if (!field) return tc_value_nil();

    const tc_field_vtable* vtable = &field->lang[lang];
    if (!vtable->get) return tc_value_nil();

    return vtable->get(obj, field, vtable->user_data);
}

void tc_inspect_set_lang(void* obj, const char* type_name, const char* path, tc_value value, tc_inspect_lang lang, tc_scene* scene) {
    if (lang < 0 || lang >= TC_INSPECT_LANG_COUNT) return;

    tc_field_desc* field = tc_inspect_find_field(type_name, path);
    if (!field) return;

    const tc_field_vtable* vtable = &field->lang[lang];
    if (!vtable->set) return;

    // Apply convert if custom type handler exists
    const tc_custom_type_handler* h = tc_custom_type_get(field->kind);
    if (h && h->convert) {
        tc_value converted = h->convert(&value);
        vtable->set(obj, field, converted, vtable->user_data, scene);
        if (converted.type != value.type || converted.data.custom != value.data.custom) {
            tc_value_free(&converted);
        }
    } else {
        vtable->set(obj, field, value, vtable->user_data, scene);
    }
}

void tc_inspect_action_lang(void* obj, const char* type_name, const char* path, tc_inspect_lang lang) {
    if (lang < 0 || lang >= TC_INSPECT_LANG_COUNT) return;

    tc_field_desc* field = tc_inspect_find_field(type_name, path);
    if (!field) return;

    const tc_field_vtable* vtable = &field->lang[lang];
    if (!vtable->action) return;

    vtable->action(obj, field, vtable->user_data);
}

// ============================================================================
// Serialization
// ============================================================================

tc_value tc_inspect_serialize(void* obj, const char* type_name) {
    tc_value result = tc_value_dict_new();

    size_t count = tc_inspect_field_count(type_name);
    for (size_t i = 0; i < count; i++) {
        const tc_field_desc* f = tc_inspect_field_at(type_name, i);
        if (!f || !f->is_serializable) continue;

        tc_value val = tc_inspect_get(obj, type_name, f->path);
        if (val.type == TC_VALUE_NIL) continue;

        // Try tc_kind serialization first (language-agnostic)
        if (tc_kind_exists(f->kind)) {
            tc_value serialized = tc_kind_serialize_any(f->kind, &val);
            if (serialized.type != TC_VALUE_NIL) {
                tc_value_dict_set(&result, f->path, serialized);
                tc_value_free(&val);
                continue;
            }
        }

        // Fallback to tc_custom_type_handler (for TC_VALUE_CUSTOM memory management)
        const tc_custom_type_handler* h = tc_custom_type_get(f->kind);
        if (h && h->serialize) {
            tc_value serialized = h->serialize(&val);
            tc_value_dict_set(&result, f->path, serialized);
            tc_value_free(&val);
        } else {
            // No serializer - store value as-is
            tc_value_dict_set(&result, f->path, val);
        }
    }

    return result;
}

void tc_inspect_deserialize(void* obj, const char* type_name, const tc_value* data) {
    tc_inspect_deserialize_with_scene(obj, type_name, data, NULL);
}

void tc_inspect_deserialize_with_scene(void* obj, const char* type_name, const tc_value* data, tc_scene* scene) {
    if (!data || data->type != TC_VALUE_DICT) return;

    size_t count = tc_inspect_field_count(type_name);
    for (size_t i = 0; i < count; i++) {
        const tc_field_desc* f = tc_inspect_field_at(type_name, i);
        if (!f || !f->is_serializable) continue;

        tc_value* field_data = tc_value_dict_get((tc_value*)data, f->path);
        if (!field_data || field_data->type == TC_VALUE_NIL) continue;

        // Try tc_kind deserialization first (language-agnostic)
        if (tc_kind_exists(f->kind)) {
            tc_value deserialized = tc_kind_deserialize_any(f->kind, field_data, scene);
            if (deserialized.type != TC_VALUE_NIL) {
                tc_inspect_set(obj, type_name, f->path, deserialized, scene);
                tc_value_free(&deserialized);
                continue;
            }
        }

        // Fallback to tc_custom_type_handler
        const tc_custom_type_handler* h = tc_custom_type_get(f->kind);
        if (h && h->deserialize) {
            tc_value deserialized = h->deserialize(field_data);
            tc_inspect_set(obj, type_name, f->path, deserialized, scene);
            tc_value_free(&deserialized);
        } else {
            // No deserializer - set value as-is
            tc_inspect_set(obj, type_name, f->path, *field_data, scene);
        }
    }
}

// ============================================================================
// Cleanup
// ============================================================================

void tc_inspect_cleanup(void) {
    g_type_registry.count = 0;
}
