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
