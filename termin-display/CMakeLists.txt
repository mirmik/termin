cmake_minimum_required(VERSION 3.14)
project(termin_display VERSION 0.1.0 LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

option(TERMIN_DISPLAY_BUILD_SHARED "Build shared library" ON)
option(TERMIN_BUILD_PYTHON "Build Python bindings for termin-display" OFF)

if(COMMAND termin_require_package)
    termin_require_package(termin_base tcbase::termin_base)
else()
    find_package(termin_base REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_graphics tgfx::termin_graphics tgfx::termin_graphics2)
else()
    find_package(termin_graphics REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_scene termin_scene::termin_scene)
else()
    find_package(termin_scene REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_input termin_input::termin_input)
else()
    find_package(termin_input REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_render termin_render::termin_render)
else()
    find_package(termin_render REQUIRED)
endif()

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_LIST_DIR}/../cmake")
include(TerminRpath)
include(TerminSDL2)

# ── SDL2 (optional) ──
option(USE_SYSTEM_SDL2 "Use system SDL2 library" ON)
set(TERMIN_DISPLAY_HAS_SDL OFF)

termin_configure_sdl2()

if(SDL2_FOUND)
    set(TERMIN_DISPLAY_HAS_SDL ON)
    message(STATUS "termin-display: SDL2 found, building SDL support")
else()
    message(STATUS "termin-display: SDL2 not found, SDL support disabled")
endif()

set(TERMIN_DISPLAY_REQUIRES_SDL2_PACKAGE OFF)
if(TERMIN_DISPLAY_HAS_SDL)
    foreach(_termin_display_sdl_link_item IN LISTS SDL2_LIBRARIES)
        if(_termin_display_sdl_link_item MATCHES "^SDL2::")
            set(TERMIN_DISPLAY_REQUIRES_SDL2_PACKAGE ON)
        endif()
    endforeach()
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

if(DEFINED termin_graphics_TGFX2_ENABLE_D3D11)
    set(_TERMIN_DISPLAY_D3D11_DEFAULT ${termin_graphics_TGFX2_ENABLE_D3D11})
elseif(WIN32)
    set(_TERMIN_DISPLAY_D3D11_DEFAULT ON)
else()
    set(_TERMIN_DISPLAY_D3D11_DEFAULT OFF)
endif()
option(TGFX2_ENABLE_D3D11 "Enable Direct3D 11 path in BackendWindow" ${_TERMIN_DISPLAY_D3D11_DEFAULT})
if(TGFX2_ENABLE_D3D11 AND NOT WIN32)
    message(FATAL_ERROR "TGFX2_ENABLE_D3D11 requires Windows")
endif()
if(TGFX2_ENABLE_D3D11 AND DEFINED termin_graphics_TGFX2_ENABLE_D3D11
   AND NOT termin_graphics_TGFX2_ENABLE_D3D11)
    message(FATAL_ERROR "TGFX2_ENABLE_D3D11 requires termin_graphics built with D3D11 support")
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
        $<INSTALL_INTERFACE:include>
    PRIVATE
        ${CMAKE_CURRENT_LIST_DIR}/include
)

if(TERMIN_DISPLAY_HAS_SDL)
    target_compile_definitions(termin_display PUBLIC TERMIN_DISPLAY_HAS_SDL)
    target_include_directories(termin_display PUBLIC ${SDL2_INCLUDE_DIRS})
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
    target_link_libraries(termin_display PUBLIC ${SDL2_LIBRARIES})
endif()

set_property(TARGET termin_display PROPERTY
    TERMIN_DISPLAY_HAS_SDL ${TERMIN_DISPLAY_HAS_SDL}
)

if(TGFX2_ENABLE_VULKAN)
    target_compile_definitions(termin_display PRIVATE TGFX2_HAS_VULKAN)
    target_link_libraries(termin_display PRIVATE Vulkan::Vulkan)
endif()

if(TGFX2_ENABLE_D3D11)
    target_compile_definitions(termin_display PRIVATE TGFX2_HAS_D3D11)
    target_link_libraries(termin_display PRIVATE d3d11 dxgi)
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
        bindings/input/input_events_bindings.cpp
        bindings/platform/offscreen_render_surface_bindings.cpp
    )
    target_link_libraries(_display_native PRIVATE termin_display)
    target_include_directories(_display_native PRIVATE
        ${CMAKE_CURRENT_LIST_DIR}/include
    )
    termin_set_rpath_python(_display_native)
    install(TARGETS _display_native DESTINATION lib/python/termin/display)

    nanobind_add_module(_viewport_native NB_SHARED
        bindings/viewport/viewport_module.cpp
    )
    target_link_libraries(_viewport_native PRIVATE termin_display termin_scene::termin_scene)
    target_include_directories(_viewport_native PRIVATE
        ${CMAKE_CURRENT_LIST_DIR}/include
    )
    termin_set_rpath_python(_viewport_native)
    install(TARGETS _viewport_native DESTINATION lib/python/termin/viewport)

    set(TERMIN_DISPLAY_PLATFORM_NATIVE_SOURCES
        bindings/platform/platform_module.cpp
    )
    if(TERMIN_DISPLAY_HAS_SDL)
        list(APPEND TERMIN_DISPLAY_PLATFORM_NATIVE_SOURCES
            bindings/platform/sdl_bindings.cpp
        )
    endif()

    nanobind_add_module(_platform_native NB_SHARED
        ${TERMIN_DISPLAY_PLATFORM_NATIVE_SOURCES}
    )
    target_link_libraries(_platform_native PRIVATE termin_display)
    target_include_directories(_platform_native PRIVATE
        ${CMAKE_CURRENT_LIST_DIR}/include
        ${CMAKE_CURRENT_LIST_DIR}/bindings/platform
    )
    if(TERMIN_DISPLAY_HAS_SDL)
        target_compile_definitions(_platform_native PRIVATE TERMIN_DISPLAY_HAS_SDL)
        target_include_directories(_platform_native PRIVATE ${SDL2_INCLUDE_DIRS})
        target_link_libraries(_platform_native PRIVATE ${SDL2_LIBRARIES})
    endif()
    termin_set_rpath_python(_platform_native)
    install(TARGETS _platform_native DESTINATION lib/python/termin/display)

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
    ${CMAKE_CURRENT_LIST_DIR}/include/tc_input_event.h
    DESTINATION include
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
    ${CMAKE_CURRENT_LIST_DIR}/include/termin/input/input_events.hpp
    DESTINATION include/termin/input
)

install(FILES
    ${CMAKE_CURRENT_LIST_DIR}/include/termin/platform/backend_window.hpp
    ${CMAKE_CURRENT_LIST_DIR}/include/termin/platform/offscreen_render_surface.hpp
    DESTINATION include/termin/platform
)

if(TERMIN_DISPLAY_HAS_SDL)
    install(FILES
        ${CMAKE_CURRENT_LIST_DIR}/include/termin/platform/sdl_window.hpp
        ${CMAKE_CURRENT_LIST_DIR}/include/termin/platform/sdl_render_surface.hpp
        ${CMAKE_CURRENT_LIST_DIR}/include/termin/platform/sdl_backend_window.hpp
        DESTINATION include/termin/platform
    )
    if(WIN32 AND SDL2_DLL)
        termin_install_sdl2_runtime(bin)
    endif()
endif()

option(TERMIN_DISPLAY_BUILD_TESTS "Build termin-display tests" OFF)
option(TERMIN_DISPLAY_BUILD_WINDOW_TESTS "Build termin-display window smoke tests" OFF)
option(TERMIN_DISPLAY_BUILD_D3D11_WINDOW_TEST
       "Build termin-display D3D11 BackendWindow present smoke test"
       ${TERMIN_DISPLAY_BUILD_WINDOW_TESTS})
if(TERMIN_DISPLAY_BUILD_TESTS)
    add_executable(display_input_router_test tests/test_display_input_router.cpp)
    target_link_libraries(display_input_router_test PRIVATE termin_display)
    add_test(NAME display_input_router_test COMMAND display_input_router_test)

    add_executable(viewport_input_manager_source_test tests/test_viewport_input_manager_source.cpp)
    target_link_libraries(viewport_input_manager_source_test PRIVATE termin_display)
    add_test(NAME viewport_input_manager_source_test COMMAND viewport_input_manager_source_test)

    # Standalone smoke test: the same triangle code running on either backend.
    if(TERMIN_DISPLAY_HAS_SDL AND TERMIN_DISPLAY_BUILD_WINDOW_TESTS)
        add_executable(backend_window_triangle tests/test_backend_window_triangle.cpp)
        target_link_libraries(backend_window_triangle
            PRIVATE termin_display ${SDL2_LIBRARIES})
        target_include_directories(backend_window_triangle
            PRIVATE ${SDL2_INCLUDE_DIRS})
        termin_copy_sdl2_runtime(backend_window_triangle)
        add_test(NAME backend_window_triangle COMMAND backend_window_triangle)
        set_tests_properties(backend_window_triangle PROPERTIES
            TIMEOUT 10
            ENVIRONMENT "TERMIN_BACKEND=opengl"
            SKIP_RETURN_CODE 77
            SKIP_REGULAR_EXPRESSION "SDL_InitSubSystem failed|No available video device|Vulkan support is either not configured in SDL")
        termin_add_test_labels(backend_window_triangle
            "termin:capability:window")
    endif()

    if(TERMIN_DISPLAY_HAS_SDL AND TGFX2_ENABLE_D3D11 AND TERMIN_DISPLAY_BUILD_D3D11_WINDOW_TEST)
        add_executable(backend_window_d3d11_present
            tests/test_backend_window_d3d11_present.cpp)
        target_link_libraries(backend_window_d3d11_present
            PRIVATE termin_display ${SDL2_LIBRARIES})
        target_include_directories(backend_window_d3d11_present
            PRIVATE ${SDL2_INCLUDE_DIRS})
        termin_copy_sdl2_runtime(backend_window_d3d11_present)
        add_test(NAME backend_window_d3d11_present COMMAND backend_window_d3d11_present)
        set_tests_properties(backend_window_d3d11_present PROPERTIES
            TIMEOUT 10
            SKIP_RETURN_CODE 77
            SKIP_REGULAR_EXPRESSION "SDL_InitSubSystem failed|No available video device|D3D11CreateDevice failed")
        termin_add_test_labels(backend_window_d3d11_present
            "termin:capability:window"
            "termin:capability:d3d11")
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

termin_label_tests_in_directory("termin-display")
