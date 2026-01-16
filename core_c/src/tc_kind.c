// tc_kind.c - Kind registry implementation
#include "tc_kind.h"
#include "tc_log.h"
#include <string.h>
#include <stdlib.h>

// Simple hash map for kinds
#define TC_KIND_MAX_ENTRIES 256

static tc_kind_entry g_kinds[TC_KIND_MAX_ENTRIES];
static size_t g_kind_count = 0;

// Find kind by name (returns NULL if not found)
static tc_kind_entry* find_kind(const char* name) {
    for (size_t i = 0; i < g_kind_count; i++) {
        if (strcmp(g_kinds[i].name, name) == 0) {
            return &g_kinds[i];
        }
    }
    return NULL;
}

// Find or create kind entry
static tc_kind_entry* find_or_create_kind(const char* name) {
    tc_kind_entry* entry = find_kind(name);
    if (entry) {
        return entry;
    }

    if (g_kind_count >= TC_KIND_MAX_ENTRIES) {
        tc_log(TC_LOG_ERROR, "[tc_kind] Max entries reached (%d)", TC_KIND_MAX_ENTRIES);
        return NULL;
    }

    entry = &g_kinds[g_kind_count++];
    memset(entry, 0, sizeof(tc_kind_entry));
    strncpy(entry->name, name, sizeof(entry->name) - 1);
    entry->name[sizeof(entry->name) - 1] = '\0';

    return entry;
}

void tc_kind_register(
    const char* name,
    tc_kind_lang lang,
    tc_kind_serialize_fn serialize,
    tc_kind_deserialize_fn deserialize,
    void* user_data
) {
    if (!name || lang < 0 || lang >= TC_KIND_LANG_COUNT) {
        tc_log(TC_LOG_ERROR, "[tc_kind] Invalid arguments to tc_kind_register");
        return;
    }

    tc_kind_entry* entry = find_or_create_kind(name);
    if (!entry) {
        return;
    }

    entry->lang[lang].serialize = serialize;
    entry->lang[lang].deserialize = deserialize;
    entry->lang[lang].user_data = user_data;
}

void tc_kind_unregister(const char* name, tc_kind_lang lang) {
    if (!name || lang < 0 || lang >= TC_KIND_LANG_COUNT) {
        return;
    }

    tc_kind_entry* entry = find_kind(name);
    if (!entry) {
        return;
    }

    entry->lang[lang].serialize = NULL;
    entry->lang[lang].deserialize = NULL;
    entry->lang[lang].user_data = NULL;
}

tc_kind_entry* tc_kind_get(const char* name) {
    if (!name) return NULL;
    return find_kind(name);
}

tc_kind_entry* tc_kind_get_or_create(const char* name) {
    if (!name) return NULL;
    return find_or_create_kind(name);
}

bool tc_kind_exists(const char* name) {
    return find_kind(name) != NULL;
}

bool tc_kind_has_lang(const char* name, tc_kind_lang lang) {
    if (lang < 0 || lang >= TC_KIND_LANG_COUNT) {
        return false;
    }

    tc_kind_entry* entry = find_kind(name);
    if (!entry) {
        return false;
    }

    return entry->lang[lang].serialize != NULL || entry->lang[lang].deserialize != NULL;
}

size_t tc_kind_list(const char** out_names, size_t max_count) {
    size_t count = g_kind_count < max_count ? g_kind_count : max_count;
    if (out_names) {
        for (size_t i = 0; i < count; i++) {
            out_names[i] = g_kinds[i].name;
        }
    }
    return g_kind_count;
}

void tc_kind_cleanup(void) {
    memset(g_kinds, 0, sizeof(g_kinds));
    g_kind_count = 0;
}

tc_value tc_kind_serialize(const char* name, tc_kind_lang lang, const tc_value* input) {
    if (!name || !input || lang < 0 || lang >= TC_KIND_LANG_COUNT) {
        return tc_value_nil();
    }

    tc_kind_entry* entry = find_kind(name);
    if (!entry || !entry->lang[lang].serialize) {
        return tc_value_nil();
    }

    return entry->lang[lang].serialize(input, entry->lang[lang].user_data);
}

tc_value tc_kind_deserialize(const char* name, tc_kind_lang lang, const tc_value* input, tc_scene* scene) {
    if (!name || !input || lang < 0 || lang >= TC_KIND_LANG_COUNT) {
        return tc_value_nil();
    }

    tc_kind_entry* entry = find_kind(name);
    if (!entry || !entry->lang[lang].deserialize) {
        return tc_value_nil();
    }

    return entry->lang[lang].deserialize(input, scene, entry->lang[lang].user_data);
}

tc_value tc_kind_serialize_any(const char* name, const tc_value* input) {
    if (!input) {
        return tc_value_nil();
    }

    tc_kind_entry* entry = find_kind(name);
    if (!entry) {
        return tc_value_nil();
    }

    // Try languages in order: C, C++, Python, Rust
    for (int lang = 0; lang < TC_KIND_LANG_COUNT; lang++) {
        if (entry->lang[lang].serialize) {
            return entry->lang[lang].serialize(input, entry->lang[lang].user_data);
        }
    }

    return tc_value_nil();
}

tc_value tc_kind_deserialize_any(const char* name, const tc_value* input, tc_scene* scene) {
    if (!input) {
        return tc_value_nil();
    }

    tc_kind_entry* entry = find_kind(name);
    if (!entry) {
        return tc_value_nil();
    }

    // Try languages in order: C, C++, Python, Rust
    for (int lang = 0; lang < TC_KIND_LANG_COUNT; lang++) {
        if (entry->lang[lang].deserialize) {
            return entry->lang[lang].deserialize(input, scene, entry->lang[lang].user_data);
        }
    }

    return tc_value_nil();
}
