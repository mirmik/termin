// termin_core.h - Main header for Termin Core C library
//
// This is a pure C library that provides the core Entity-Component system.
// It can be used from C, C++, Rust, Python, or any language with C FFI.
//
// Usage:
//   #include <termin_core.h>
//
// Modules:
//   - tc_types.h    - Basic types (Vec3, Quat, Pose, etc.)
//   - tc_vec3.h     - Vec3 operations (inline)
//   - tc_quat.h     - Quaternion operations (inline)
//   - tc_pose.h     - Pose operations (inline)
//   - tc_component.h - Component base and vtable
//   - tc_entity_pool.h - Entity pool with generational indices
//   - tc_scene.h     - Scene (owns pool + component scheduler)
//   - tc_inspect.h   - Field inspection/serialization
//

#ifndef TERMIN_CORE_H
#define TERMIN_CORE_H

#include "tc_version.h"
#include "tc_types.h"
#include "tc_vec3.h"
#include "tc_quat.h"
#include "tc_pose.h"
#include "tc_component.h"
#include "tc_entity_pool.h"
#include "tc_entity_pool_registry.h"
#include "tc_scene.h"
#include "tc_inspect.h"
#include "tc_mesh.h"
#include "tc_mesh_registry.h"
#include "tc_texture.h"
#include "tc_texture_registry.h"
#include "tc_shader.h"
#include "tc_shader_registry.h"
#include "tc_skeleton.h"
#include "tc_skeleton_registry.h"
#include "tc_animation.h"
#include "tc_animation_registry.h"
#include "tc_material.h"
#include "tc_material_registry.h"
#include "tc_scene_registry.h"
#include "tc_project_settings.h"
#include "render/tc_viewport.h"
#include "tc_gpu.h"

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// Library initialization / cleanup
// ============================================================================

// Initialize the library (call once at startup)
TC_API void tc_init(void);

// Cleanup the library (call once at shutdown)
TC_API void tc_shutdown(void);

// ============================================================================
// Utility functions
// ============================================================================

// Generate UUID v4 string (output must be at least 40 bytes)
TC_API void tc_generate_uuid(char* out);

// Compute runtime ID from UUID string
TC_API uint64_t tc_compute_runtime_id(const char* uuid);

// String interning (returns pointer that's valid for library lifetime)
TC_API const char* tc_intern_string(const char* s);

// ============================================================================
// Version info
// ============================================================================

TC_API const char* tc_version(void);
TC_API int tc_version_major(void);
TC_API int tc_version_minor(void);
TC_API int tc_version_patch(void);
TC_API int tc_version_int(void);  // TC_VERSION as runtime value

#ifdef __cplusplus
}
#endif

#endif // TERMIN_CORE_H
