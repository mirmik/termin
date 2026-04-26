cmake_minimum_required(VERSION 3.14)
project(termin_display VERSION 0.1.0 LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

option(TERMIN_DISPLAY_BUILD_SHARED "Build shared library" ON)
option(TERMIN_BUILD_PYTHON "Build Python bindings for termin-display" OFF)

find_package(termin_base REQUIRED)
find_package(termin_graphics REQUIRED)
find_package(termin_scene REQUIRED)
find_package(termin_input REQUIRED)
find_package(termin_render REQUIRED)

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_LIST_DIR}/../cmake")
include(TerminRpath)

# ── SDL2 (optional) ──
option(USE_SYSTEM_SDL2 "Use system SDL2 library" ON)
set(TERMIN_DISPLAY_HAS_SDL OFF)

if(USE_SYSTEM_SDL2)
    if(WIN32)
        set(SDL2_SEARCH_PATHS
            "C:/SDL2"
            "$ENV{SDL2_DIR}"
            "$ENV{PROGRAMFILES}/SDL2"
        )
        find_path(SDL2_INCLUDE_DIRS SDL2/SDL.h
            PATH_SUFFIXES include
            PATHS ${SDL2_SEARCH_PATHS}
        )
        find_library(SDL2_LIBRARY
            NAMES SDL2
            PATH_SUFFIXES lib
            PATHS ${SDL2_SEARCH_PATHS}
        )
        if(SDL2_INCLUDE_DIRS AND SDL2_LIBRARY)
            set(SDL2_FOUND TRUE)
            set(SDL2_LIBRARIES ${SDL2_LIBRARY})
            get_filename_component(SDL2_LIB_DIR ${SDL2_LIBRARY} DIRECTORY)
            find_file(SDL2_DLL
                NAMES SDL2.dll
                PATHS ${SDL2_LIB_DIR} ${SDL2_LIB_DIR}/../bin ${SDL2_LIB_DIR}/..
            )
        else()
            set(SDL2_FOUND FALSE)
        endif()
    else()
        find_package(SDL2 QUIET)
        if(NOT SDL2_FOUND)
            find_package(PkgConfig QUIET)
            if(PkgConfig_FOUND)
                pkg_check_modules(SDL2 QUIET sdl2)
            endif()
        endif()
    endif()
else()
    set(SDL2_FOUND FALSE)
endif()

if(SDL2_FOUND)
    set(TERMIN_DISPLAY_HAS_SDL ON)
    message(STATUS "termin-display: SDL2 found, building SDL support")
else()
    message(STATUS "termin-display: SDL2 not found, SDL support disabled")
endif()

set(TERMIN_DISPLAY_SOURCES
    ${CMAKE_CURRENT_LIST_DIR}/src/tc_viewport.c
    ${CMAKE_CURRENT_LIST_DIR}/src/tc_display.c
    ${CMAKE_CURRENT_LIST_DIR}/src/tc_input_manager.c
    ${CMAKE_CURRENT_LIST_DIR}/src/tc_display_input_router.c
    ${CMAKE_CURRENT_LIST_DIR}/src/tc_viewport_input_manager.c
    ${CMAKE_CURRENT_LIST_DIR}/src/tc_render_surface.c
    ${CMAKE_CURRENT_LIST_DIR}/src/platform/offscreen_render_surface.cpp
)

if(TERMIN_DISPLAY_HAS_SDL)
    list(APPEND TERMIN_DISPLAY_SOURCES
        ${CMAKE_CURRENT_LIST_DIR}/src/platform/sdl_render_surface.cpp
        ${CMAKE_CURRENT_LIST_DIR}/src/platform/backend_window.cpp
    )
endif()

# Optional Vulkan path for BackendWindow. When enabled, BackendWindow
# reads TERMIN_BACKEND=vulkan and creates a VulkanRenderDevice + swapchain;
# without this flag it only supports the OpenGL backend (TERMIN_BACKEND=vulkan
# then throws "Vulkan backend not compiled" at ctor time).
#
# Default: auto-enable if Vulkan is discoverable on the host. This way
# pip-installed binaries Just Work under TERMIN_BACKEND=vulkan — no
# explicit build-time flag required, and the OpenGL path is unchanged
# when Vulkan is absent.
find_package(Vulkan QUIET)
if(Vulkan_FOUND)
    option(TGFX2_ENABLE_VULKAN "Enable Vulkan path in BackendWindow" ON)
else()
    option(TGFX2_ENABLE_VULKAN "Enable Vulkan path in BackendWindow" OFF)
endif()
if(TGFX2_ENABLE_VULKAN AND NOT Vulkan_FOUND)
    find_package(Vulkan REQUIRED)
endif()

if(TERMIN_DISPLAY_BUILD_SHARED)
    add_library(termin_display SHARED ${TERMIN_DISPLAY_SOURCES})
    target_compile_definitions(termin_display PRIVATE TERMIN_DISPLAY_EXPORTS TC_EXPORTS)
else()
    add_library(termin_display STATIC ${TERMIN_DISPLAY_SOURCES})
endif()

add_library(termin_display::termin_display ALIAS termin_display)

set_target_properties(termin_display PROPERTIES
    POSITION_INDEPENDENT_CODE ON
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
)
termin_set_rpath_lib(termin_display)

target_include_directories(termin_display
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_LIST_DIR}/include>
        $<BUILD_INTERFACE:${CMAKE_CURRENT_LIST_DIR}/../termin-app/core_c/include>
        $<BUILD_INTERFACE:${CMAKE_CURRENT_LIST_DIR}/../termin-render/include>
        $<INSTALL_INTERFACE:include>
    PRIVATE
        ${CMAKE_CURRENT_LIST_DIR}/include
        ${CMAKE_CURRENT_LIST_DIR}/../termin-app/core_c/include
        ${CMAKE_CURRENT_LIST_DIR}/../termin-render/include
)

if(TERMIN_DISPLAY_HAS_SDL)
    target_include_directories(termin_display PRIVATE ${SDL2_INCLUDE_DIRS})
endif()

target_link_libraries(termin_display
    PUBLIC
        tcbase::termin_base
        tgfx::termin_graphics
        tgfx::termin_graphics2
        termin_scene::termin_scene
        termin_input::termin_input
        termin_render::termin_render
)

if(TERMIN_DISPLAY_HAS_SDL)
    target_link_libraries(termin_display PRIVATE ${SDL2_LIBRARIES})
endif()

if(TGFX2_ENABLE_VULKAN)
    target_compile_definitions(termin_display PRIVATE TGFX2_HAS_VULKAN)
    target_link_libraries(termin_display PRIVATE Vulkan::Vulkan)
endif()

if(UNIX AND NOT APPLE)
    target_link_libraries(termin_display PRIVATE m)
endif()

if(MSVC)
    target_compile_options(termin_display PRIVATE /W3 /wd4251 /wd4275)
    target_compile_definitions(termin_display PRIVATE _CRT_SECURE_NO_WARNINGS)
else()
    target_compile_options(termin_display PRIVATE -Wall -Wextra -Wno-stringop-truncation)
endif()

if(TERMIN_BUILD_PYTHON)
    find_package(Python 3.8 COMPONENTS Interpreter Development REQUIRED)
    find_package(nanobind CONFIG REQUIRED)

    nanobind_add_module(_display_native NB_SHARED
        python/display_module.cpp
        bindings/render/tc_display_bindings.cpp
        bindings/render/tc_input_manager_bindings.cpp
        bindings/render/tc_render_surface_bindings.cpp
        bindings/input/display_input_router_bindings.cpp
        bindings/platform/offscreen_render_surface_bindings.cpp
    )
    target_link_libraries(_display_native PRIVATE termin_display)
    target_include_directories(_display_native PRIVATE
        ${CMAKE_CURRENT_LIST_DIR}/include
        ${CMAKE_CURRENT_LIST_DIR}/../termin-app/core_c/include
        ${CMAKE_CURRENT_LIST_DIR}/../termin-render/include
    )
    termin_set_rpath_python(_display_native)
    install(TARGETS _display_native DESTINATION lib/python/termin/display)

    nanobind_add_module(_viewport_native NB_SHARED
        bindings/viewport/viewport_module.cpp
    )
    target_link_libraries(_viewport_native PRIVATE termin_display termin_scene::termin_scene)
    target_include_directories(_viewport_native PRIVATE
        ${CMAKE_CURRENT_LIST_DIR}/include
        ${CMAKE_CURRENT_LIST_DIR}/../termin-app/core_c/include
        ${CMAKE_CURRENT_LIST_DIR}/../termin-render/include
    )
    termin_set_rpath_python(_viewport_native)
    install(TARGETS _viewport_native DESTINATION lib/python/termin/viewport)

    if(TERMIN_DISPLAY_HAS_SDL)
        nanobind_add_module(_platform_native NB_SHARED
            bindings/platform/platform_module.cpp
            bindings/platform/sdl_bindings.cpp
        )
        target_link_libraries(_platform_native PRIVATE termin_display ${SDL2_LIBRARIES})
        target_include_directories(_platform_native PRIVATE
            ${CMAKE_CURRENT_LIST_DIR}/include
            ${CMAKE_CURRENT_LIST_DIR}/../termin-app/core_c/include
            ${CMAKE_CURRENT_LIST_DIR}/../termin-render/include
            ${CMAKE_CURRENT_LIST_DIR}/bindings/platform
            ${SDL2_INCLUDE_DIRS}
        )
        termin_set_rpath_python(_platform_native)
        install(TARGETS _platform_native DESTINATION lib/python/termin/display)
    endif()

    install(DIRECTORY ${CMAKE_CURRENT_LIST_DIR}/python/termin/display/
            DESTINATION lib/python/termin/display
            FILES_MATCHING PATTERN "*.py")
    install(DIRECTORY ${CMAKE_CURRENT_LIST_DIR}/python/termin/viewport/
            DESTINATION lib/python/termin/viewport
            FILES_MATCHING PATTERN "*.py")
endif()

install(TARGETS termin_display
    EXPORT termin_displayTargets
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
    RUNTIME DESTINATION bin
)

install(FILES
    ${CMAKE_CURRENT_LIST_DIR}/include/render/termin_display_api.h
    ${CMAKE_CURRENT_LIST_DIR}/include/render/tc_viewport.h
    ${CMAKE_CURRENT_LIST_DIR}/include/render/tc_viewport_pool.h
    ${CMAKE_CURRENT_LIST_DIR}/include/render/tc_display.h
    ${CMAKE_CURRENT_LIST_DIR}/include/render/tc_input_manager.h
    ${CMAKE_CURRENT_LIST_DIR}/include/render/tc_display_input_router.h
    ${CMAKE_CURRENT_LIST_DIR}/include/render/tc_viewport_input_manager.h
    ${CMAKE_CURRENT_LIST_DIR}/include/render/tc_render_surface.h
    DESTINATION include/render
)

install(FILES
    ${CMAKE_CURRENT_LIST_DIR}/include/termin/viewport/tc_viewport_handle.hpp
    DESTINATION include/termin/viewport
)

install(FILES
    ${CMAKE_CURRENT_LIST_DIR}/include/termin/render/tc_display_handle.hpp
    DESTINATION include/termin/render
)

install(FILES
    ${CMAKE_CURRENT_LIST_DIR}/include/termin/input/display_input_router.hpp
    DESTINATION include/termin/input
)

install(FILES
    ${CMAKE_CURRENT_LIST_DIR}/include/termin/platform/offscreen_render_surface.hpp
    DESTINATION include/termin/platform
)

if(TERMIN_DISPLAY_HAS_SDL)
    install(FILES
        ${CMAKE_CURRENT_LIST_DIR}/include/termin/platform/sdl_window.hpp
        ${CMAKE_CURRENT_LIST_DIR}/include/termin/platform/sdl_render_surface.hpp
        ${CMAKE_CURRENT_LIST_DIR}/include/termin/platform/backend_window.hpp
        DESTINATION include/termin/platform
    )
    if(WIN32 AND SDL2_DLL)
        install(FILES ${SDL2_DLL} DESTINATION bin)
    endif()

    # Standalone smoke test: the same triangle code running on either
    # backend. Built when tests are enabled.
    option(TERMIN_DISPLAY_BUILD_TESTS "Build termin-display smoke tests" OFF)
    if(TERMIN_DISPLAY_BUILD_TESTS)
        add_executable(backend_window_triangle tests/test_backend_window_triangle.cpp)
        target_link_libraries(backend_window_triangle
            PRIVATE termin_display ${SDL2_LIBRARIES})
        target_include_directories(backend_window_triangle
            PRIVATE ${SDL2_INCLUDE_DIRS})
    endif()
endif()

install(EXPORT termin_displayTargets
    FILE termin_displayTargets.cmake
    NAMESPACE termin_display::
    DESTINATION lib/cmake/termin_display
)

include(CMakePackageConfigHelpers)

configure_package_config_file(
    ${CMAKE_CURRENT_LIST_DIR}/cmake/termin_displayConfig.cmake.in
    ${CMAKE_CURRENT_BINARY_DIR}/termin_displayConfig.cmake
    INSTALL_DESTINATION lib/cmake/termin_display
)

write_basic_package_version_file(
    ${CMAKE_CURRENT_BINARY_DIR}/termin_displayConfigVersion.cmake
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMajorVersion
)

install(FILES
    ${CMAKE_CURRENT_BINARY_DIR}/termin_displayConfig.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/termin_displayConfigVersion.cmake
    DESTINATION lib/cmake/termin_display
)
