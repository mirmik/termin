// tc_types.h - Basic types for Termin Core
#ifndef TC_TYPES_H
#define TC_TYPES_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

// Export macro
#ifdef _WIN32
    #ifdef TC_EXPORTS
        #define TC_API __declspec(dllexport)
    #else
        #define TC_API __declspec(dllimport)
    #endif
#else
    #define TC_API
#endif

// ============================================================================
// Geometry Types
// ============================================================================

typedef struct tc_vec3 {
    double x, y, z;
} tc_vec3;

typedef struct tc_quat {
    double x, y, z, w;
} tc_quat;

typedef struct tc_vec3f {
    float x, y, z;
} tc_vec3f;

typedef struct tc_quatf {
    float x, y, z, w;
} tc_quatf;

// Layout matches C++ Pose3/GeneralPose3 for zero-cost interop
typedef struct tc_pose3 {
    tc_quat rotation;
    tc_vec3 position;
} tc_pose3;

typedef struct tc_general_pose3 {
    tc_quat rotation;
    tc_vec3 position;
    tc_vec3 scale;
} tc_general_pose3;

typedef struct tc_mat44 {
    double m[16];  // column-major (OpenGL convention)
} tc_mat44;

// ============================================================================
// Forward Declarations
// ============================================================================

typedef struct tc_transform tc_transform;
typedef struct tc_entity tc_entity;
typedef struct tc_component tc_component;
typedef struct tc_component_vtable tc_component_vtable;
typedef struct tc_drawable_vtable tc_drawable_vtable;
typedef struct tc_input_vtable tc_input_vtable;
typedef struct tc_scene tc_scene;

// ============================================================================
// Handle Types
// ============================================================================

typedef struct tc_entity_handle {
    char uuid[40];
} tc_entity_handle;

#ifdef __cplusplus
}
#endif

#endif // TC_TYPES_H
