# Graphics package composition for the repository-level build.
#
# This file is intentionally not a standalone CMake project. Global build
# policy, SDK profiles, dependencies, and installation are owned by the
# repository root.

if(TERMIN_PLATFORM_WEB)
    set(TERMIN_ENABLE_OPENGL OFF CACHE BOOL
        "Enable desktop OpenGL-dependent graphics/render targets" FORCE)
    set(TERMIN_ENABLE_VULKAN OFF CACHE BOOL "Enable Vulkan support" FORCE)
    set(TERMIN_ENABLE_SDL OFF CACHE BOOL "Enable SDL support" FORCE)
    set(TERMIN_BUILD_TGFX2_TESTS OFF CACHE BOOL
        "Build tgfx2 C/C++ tests" FORCE)
    set(TERMIN_BUILD_WINDOW_TESTS OFF CACHE BOOL
        "Build tests that require a windowing system" FORCE)
    set(TERMIN_IMAGE_BUILD_SHARED OFF CACHE BOOL
        "Build termin-image as a shared library" FORCE)
    set(TERMIN_MESH_BUILD_SHARED OFF CACHE BOOL
        "Build termin-mesh as a shared library" FORCE)
    set(TERMIN_SKELETON_BUILD_SHARED OFF CACHE BOOL
        "Build termin-skeleton as a shared library" FORCE)
    set(TERMIN_MATERIALS_BUILD_SHARED OFF CACHE BOOL
        "Build termin-materials as a shared library" FORCE)
    set(TERMIN_RENDER_CORE_BUILD_SHARED OFF CACHE BOOL
        "Build termin-render-core as a shared library" FORCE)
elseif(TERMIN_PLATFORM_ANDROID)
    set(TERMIN_ENABLE_OPENGL OFF CACHE BOOL
        "Enable desktop OpenGL-dependent graphics/render targets" FORCE)
    set(TERMIN_ENABLE_VULKAN ON CACHE BOOL "Enable Vulkan support" FORCE)
    set(TERMIN_ENABLE_SDL OFF CACHE BOOL "Enable SDL support" FORCE)
    set(TERMIN_BUILD_TGFX2_TESTS OFF CACHE BOOL
        "Build tgfx2 C/C++ tests" FORCE)
    set(TERMIN_BUILD_WINDOW_TESTS OFF CACHE BOOL
        "Build tests that require a windowing system" FORCE)
endif()

# The repository-level backend switches are the source of truth for the
# composed Graphics target graph.  termin-graphics also exposes package-local
# cache options, so they must be refreshed on every configure: CMake option()
# only uses its default for a new cache and would otherwise retain a backend
# enabled by an earlier build in the same build directory.
set(TGFX2_ENABLE_OPENGL "${TERMIN_ENABLE_OPENGL}" CACHE BOOL
    "Enable OpenGL backend for tgfx2" FORCE)
set(TGFX2_ENABLE_WEBGL2 "${TERMIN_ENABLE_WEBGL2}" CACHE BOOL
    "Enable WebGL 2 through the shared constrained-GL backend" FORCE)
set(TGFX2_ENABLE_VULKAN "${TERMIN_ENABLE_VULKAN}" CACHE BOOL
    "Enable Vulkan backend for tgfx2" FORCE)

if(TERMIN_SDK_PROFILE STREQUAL "graphics")
    set(TERMIN_VISUAL_SCENE_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
    set(TERMIN_GUI_NATIVE_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
    message(STATUS
        "Termin: graphics SDK profile enabled (widgets, visual scene, 2D/3D charts)")
elseif(TERMIN_PLATFORM_ANDROID OR TERMIN_PLATFORM_WEB)
    set(TERMIN_VISUAL_SCENE_BUILD_EXAMPLES OFF CACHE BOOL
        "Build termin-visual-scene examples" FORCE)
endif()

if(NOT TERMIN_ENABLE_OPENGL)
    message(STATUS "Termin Graphics: desktop OpenGL backend disabled")
endif()
if(TERMIN_ENABLE_WEBGL2)
    message(STATUS "Termin Graphics: WebGL 2 constrained-GL backend enabled")
endif()

add_subdirectory(termin-image)
add_subdirectory(termin-mesh)
add_subdirectory(termin-skeleton)

if(NOT TERMIN_PLATFORM_WEB)
    add_subdirectory(termin-animation)
    add_subdirectory(termin-glb)
endif()

add_subdirectory(termin-graphics)

if(NOT TERMIN_PLATFORM_ANDROID AND NOT TERMIN_PLATFORM_WEB)
    add_subdirectory(termin-window)
endif()

add_subdirectory(termin-visual-scene)
add_subdirectory(termin-materials)
add_subdirectory(termin-render-core)

if(NOT TERMIN_PLATFORM_WEB)
    add_subdirectory(termin-gui-native)
endif()

if(NOT TERMIN_PLATFORM_ANDROID AND NOT TERMIN_PLATFORM_WEB)
    add_subdirectory(termin-nodegraph)
    add_subdirectory(tcplot)
    add_subdirectory(tcplot-gui-native)
endif()
