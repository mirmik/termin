// tc_core.c - Library initialization, utilities, version info
#include "../include/termin_core.h"
#include <stdlib.h>
#include <string.h>
#include <time.h>

#ifdef _WIN32
#include <windows.h>
#else
#include <sys/time.h>
#include <unistd.h>
#endif

// ============================================================================
// Version
// ============================================================================

#define TC_VERSION_MAJOR 0
#define TC_VERSION_MINOR 1
#define TC_VERSION_PATCH 0
#define TC_VERSION_STRING "0.1.0"

const char* tc_version(void) {
    return TC_VERSION_STRING;
}

int tc_version_major(void) {
    return TC_VERSION_MAJOR;
}

int tc_version_minor(void) {
    return TC_VERSION_MINOR;
}

int tc_version_patch(void) {
    return TC_VERSION_PATCH;
}

// ============================================================================
// String Interning
// ============================================================================

#define TC_INTERN_INITIAL_CAPACITY 256
#define TC_INTERN_BUCKET_COUNT 64

typedef struct tc_intern_entry {
    char* str;
    struct tc_intern_entry* next;
} tc_intern_entry;

static tc_intern_entry* g_intern_buckets[TC_INTERN_BUCKET_COUNT] = {0};

static uint32_t tc_string_hash(const char* s) {
    uint32_t hash = 5381;
    int c;
    while ((c = *s++)) {
        hash = ((hash << 5) + hash) + c;
    }
    return hash;
}

const char* tc_intern_string(const char* s) {
    if (!s) return NULL;

    uint32_t bucket = tc_string_hash(s) % TC_INTERN_BUCKET_COUNT;

    // Search existing
    tc_intern_entry* entry = g_intern_buckets[bucket];
    while (entry) {
        if (strcmp(entry->str, s) == 0) {
            return entry->str;
        }
        entry = entry->next;
    }

    // Create new
    size_t len = strlen(s);
    tc_intern_entry* new_entry = (tc_intern_entry*)malloc(sizeof(tc_intern_entry));
    if (!new_entry) return NULL;

    new_entry->str = (char*)malloc(len + 1);
    if (!new_entry->str) {
        free(new_entry);
        return NULL;
    }

    memcpy(new_entry->str, s, len + 1);
    new_entry->next = g_intern_buckets[bucket];
    g_intern_buckets[bucket] = new_entry;

    return new_entry->str;
}

static void tc_intern_cleanup(void) {
    for (int i = 0; i < TC_INTERN_BUCKET_COUNT; i++) {
        tc_intern_entry* entry = g_intern_buckets[i];
        while (entry) {
            tc_intern_entry* next = entry->next;
            free(entry->str);
            free(entry);
            entry = next;
        }
        g_intern_buckets[i] = NULL;
    }
}

// ============================================================================
// UUID Generation (v4)
// ============================================================================

static bool g_random_seeded = false;

static void tc_ensure_random_seeded(void) {
    if (g_random_seeded) return;

#ifdef _WIN32
    LARGE_INTEGER counter;
    QueryPerformanceCounter(&counter);
    srand((unsigned int)(counter.QuadPart ^ GetCurrentProcessId()));
#else
    struct timeval tv;
    gettimeofday(&tv, NULL);
    srand((unsigned int)(tv.tv_sec ^ tv.tv_usec ^ getpid()));
#endif

    g_random_seeded = true;
}

static uint8_t tc_random_byte(void) {
    return (uint8_t)(rand() & 0xFF);
}

void tc_generate_uuid(char* out) {
    if (!out) return;

    tc_ensure_random_seeded();

    uint8_t bytes[16];
    for (int i = 0; i < 16; i++) {
        bytes[i] = tc_random_byte();
    }

    // Set version (4) and variant (RFC 4122)
    bytes[6] = (bytes[6] & 0x0F) | 0x40;  // Version 4
    bytes[8] = (bytes[8] & 0x3F) | 0x80;  // Variant RFC 4122

    // Format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
    static const char hex[] = "0123456789abcdef";
    int p = 0;

    for (int i = 0; i < 4; i++) {
        out[p++] = hex[(bytes[i] >> 4) & 0xF];
        out[p++] = hex[bytes[i] & 0xF];
    }
    out[p++] = '-';

    for (int i = 4; i < 6; i++) {
        out[p++] = hex[(bytes[i] >> 4) & 0xF];
        out[p++] = hex[bytes[i] & 0xF];
    }
    out[p++] = '-';

    for (int i = 6; i < 8; i++) {
        out[p++] = hex[(bytes[i] >> 4) & 0xF];
        out[p++] = hex[bytes[i] & 0xF];
    }
    out[p++] = '-';

    for (int i = 8; i < 10; i++) {
        out[p++] = hex[(bytes[i] >> 4) & 0xF];
        out[p++] = hex[bytes[i] & 0xF];
    }
    out[p++] = '-';

    for (int i = 10; i < 16; i++) {
        out[p++] = hex[(bytes[i] >> 4) & 0xF];
        out[p++] = hex[bytes[i] & 0xF];
    }

    out[p] = '\0';
}

// ============================================================================
// Runtime ID computation (FNV-1a hash)
// ============================================================================

uint64_t tc_compute_runtime_id(const char* uuid) {
    if (!uuid) return 0;

    uint64_t hash = 14695981039346656037ULL;  // FNV offset basis
    const uint64_t prime = 1099511628211ULL;  // FNV prime

    while (*uuid) {
        hash ^= (uint64_t)(unsigned char)*uuid++;
        hash *= prime;
    }

    return hash;
}

// ============================================================================
// Library Initialization
// ============================================================================

static bool g_initialized = false;

// Forward declarations for cleanup functions
extern void tc_component_registry_cleanup(void);
extern void tc_inspect_cleanup(void);
extern void tc_kind_cleanup(void);

void tc_init(void) {
    if (g_initialized) return;

    tc_ensure_random_seeded();
    tc_mesh_init();
    tc_texture_init();
    tc_shader_init();
    tc_skeleton_init();
    tc_animation_init();
    tc_material_init();
    tc_scene_registry_init();
    g_initialized = true;
}

void tc_shutdown(void) {
    if (!g_initialized) return;

    // Cleanup in reverse order of dependency
    tc_scene_registry_shutdown();
    tc_material_shutdown();
    tc_animation_shutdown();
    tc_skeleton_shutdown();
    tc_shader_shutdown();
    tc_texture_shutdown();
    tc_mesh_shutdown();
    tc_component_registry_cleanup();
    tc_inspect_cleanup();
    tc_kind_cleanup();
    tc_intern_cleanup();

    g_initialized = false;
}
