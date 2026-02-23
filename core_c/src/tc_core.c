// tc_core.c - Library initialization, utilities, version info
#include "termin_core.h"
#include <tgfx/tgfx_intern_string.h>
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
// Version (defined in termin_core.h)
// ============================================================================

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

int tc_version_int(void) {
    return TC_VERSION;
}

// ============================================================================
// String Interning — delegates to tgfx_intern_string
// ============================================================================

const char* tc_intern_string(const char* s) {
    return tgfx_intern_string(s);
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
extern void tc_pass_registry_cleanup(void);
extern void tc_inspect_cleanup(void);
extern void tc_kind_cleanup(void);
extern void tc_viewport_pool_shutdown(void);

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
    tc_viewport_pool_shutdown();
    tc_scene_registry_shutdown();
    tc_material_shutdown();
    tc_animation_shutdown();
    tc_skeleton_shutdown();
    tc_shader_shutdown();
    tc_texture_shutdown();
    tc_mesh_shutdown();
    tc_component_registry_cleanup();
    tc_pass_registry_cleanup();
    tc_inspect_cleanup();
    tc_kind_cleanup();
    tgfx_intern_cleanup();

    g_initialized = false;
}
