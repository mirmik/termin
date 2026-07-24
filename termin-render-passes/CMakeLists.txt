cmake_minimum_required(VERSION 3.16)
project(termin_render_passes VERSION 0.1.0 LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

option(TERMIN_RENDER_PASSES_BUILD_SHARED "Build shared library" ON)
option(TERMIN_BUILD_PYTHON "Build Python bindings for termin-render-passes" OFF)
option(TERMIN_RENDER_PASSES_BUILD_TESTS "Build termin-render-passes tests" ON)

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
    termin_require_package(termin_inspect termin_inspect::termin_inspect)
else()
    find_package(termin_inspect REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_render termin_render::termin_render)
else()
    find_package(termin_render REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_materials termin_materials::termin_materials)
else()
    find_package(termin_materials REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_components_render termin_components_render::termin_components_render)
else()
    find_package(termin_components_render REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_components_mesh termin_components_mesh::termin_components_mesh)
else()
    find_package(termin_components_mesh REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_components_collision termin_components_collision::termin_components_collision)
else()
    find_package(termin_components_collision REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_lighting termin_lighting::termin_lighting)
else()
    find_package(termin_lighting REQUIRED)
endif()

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_LIST_DIR}/../cmake")
include(TerminRpath)

set(TERMIN_RENDER_PASSES_SOURCES
    src/termin_render_passes_version.c
    src/bootstrap.cpp
    src/bloom_pass.cpp
    src/collider_gizmo_pass.cpp
    src/color_pass.cpp
    src/debug_triangle_pass.cpp
    src/grayscale_pass.cpp
    src/ground_grid_pass.cpp
    src/id_pass.cpp
    src/lighting_ubo.cpp
    src/present_pass.cpp
    src/resolve_pass.cpp
    src/shadow_camera.cpp
    src/shadow_pass.cpp
    src/skybox_pass.cpp
    src/tc_picking.c
    src/tonemap_pass.cpp
    src/ui_widget_pass.cpp
)

set(TERMIN_RENDER_PASSES_HEADERS
    include/termin/render_passes/export.h
    include/termin/render_passes/termin_render_passes.h
    include/termin/render_passes/version.h
    include/termin/render_passes/bootstrap.hpp
    include/termin/lighting/lighting_ubo.hpp
    include/termin/lighting/lighting_upload.hpp
    include/termin/render/bloom_pass.hpp
    include/termin/render/collider_gizmo_pass.hpp
    include/termin/render/color_pass.hpp
    include/termin/render/debug_triangle_pass.hpp
    include/termin/render/grayscale_pass.hpp
    include/termin/render/ground_grid_pass.hpp
    include/termin/render/id_pass.hpp
    include/termin/render/present_pass.hpp
    include/termin/render/resolve_pass.hpp
    include/termin/render/shadow_camera.hpp
    include/termin/render/shadow_pass.hpp
    include/termin/render/skybox_pass.hpp
    include/termin/render/tonemap_pass.hpp
    include/termin/render/ui_widget_pass.hpp
    include/tc_picking.h
)

if(TERMIN_RENDER_PASSES_BUILD_SHARED)
    add_library(termin_render_passes SHARED
        ${TERMIN_RENDER_PASSES_SOURCES}
        ${TERMIN_RENDER_PASSES_HEADERS}
    )
else()
    add_library(termin_render_passes STATIC
        ${TERMIN_RENDER_PASSES_SOURCES}
        ${TERMIN_RENDER_PASSES_HEADERS}
    )
endif()

if(COMMAND termin_add_alias_if_missing)
    termin_add_alias_if_missing(termin_render_passes::termin_render_passes termin_render_passes)
else()
    add_library(termin_render_passes::termin_render_passes ALIAS termin_render_passes)
endif()

target_include_directories(termin_render_passes
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include>
)
target_compile_features(termin_render_passes PUBLIC cxx_std_20)
target_link_libraries(termin_render_passes PUBLIC
    tcbase::termin_base
    tgfx::termin_graphics
    tgfx::termin_graphics2
    termin_inspect::termin_inspect
    termin_render::termin_render
    termin_materials::termin_materials
    termin_components_render::termin_components_render
    termin_components_mesh::termin_components_mesh
    termin_lighting::termin_lighting
)
target_link_libraries(termin_render_passes PRIVATE
    termin_components_collision::termin_components_collision
)
target_compile_definitions(termin_render_passes PRIVATE
    TERMIN_RENDER_PASSES_EXPORTS
    TERMIN_RENDER_EXPORTS
    TC_EXPORTS
)

if(MSVC)
    target_compile_options(termin_render_passes PRIVATE /W3 /wd4251 /wd4275)
    target_compile_definitions(termin_render_passes PRIVATE _CRT_SECURE_NO_WARNINGS)
else()
    target_compile_options(termin_render_passes PRIVATE -Wall -Wextra)
endif()

set_target_properties(termin_render_passes PROPERTIES
    POSITION_INDEPENDENT_CODE ON
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
)
termin_set_rpath_lib(termin_render_passes)

if(COMMAND termin_enable_unity_build_for)
    termin_enable_unity_build_for(termin_render_passes)
endif()
if(COMMAND termin_enable_pch_for)
    termin_enable_pch_for(termin_render_passes)
endif()

if(TERMIN_BUILD_PYTHON)
    find_package(Python 3.14 COMPONENTS Interpreter Development REQUIRED)
    find_package(nanobind CONFIG REQUIRED)

    nanobind_add_module(_render_passes_native NB_SHARED
        python/render_passes_bindings.cpp
    )
    target_link_libraries(_render_passes_native PRIVATE
        termin_render_passes
        termin_inspect::termin_inspect_python
    )
    target_include_directories(_render_passes_native PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/include
    )
    termin_set_rpath_python(_render_passes_native)
    install(TARGETS _render_passes_native DESTINATION lib/python/termin/render_passes)
    install(DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/python/termin/render_passes/
        DESTINATION lib/python/termin/render_passes
        PATTERN "__pycache__" EXCLUDE
        PATTERN "*.pyc" EXCLUDE
        PATTERN "*.so" EXCLUDE
        PATTERN "lib" EXCLUDE
    )
endif()

if(TERMIN_RENDER_PASSES_BUILD_TESTS)
    enable_testing()

    add_executable(termin_render_passes_builtin_shader_sources_test
        tests/test_builtin_shader_sources.cpp
    )
target_include_directories(termin_render_passes_builtin_shader_sources_test PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/../termin-thirdparty/guard
    )
    target_link_libraries(termin_render_passes_builtin_shader_sources_test PRIVATE
        termin_render_passes
    )
    set_target_properties(termin_render_passes_builtin_shader_sources_test PROPERTIES
        RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    )
    add_test(
        NAME termin_render_passes_builtin_shader_sources_test
        COMMAND termin_render_passes_builtin_shader_sources_test
    )

    add_executable(termin_render_passes_picking_test
        tests/test_picking.c
    )
    target_include_directories(termin_render_passes_picking_test PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/../termin-thirdparty/guard
    )
    target_link_libraries(termin_render_passes_picking_test PRIVATE
        termin_render_passes
    )
    set_target_properties(termin_render_passes_picking_test PROPERTIES
        RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    )
    add_test(
        NAME termin_render_passes_picking_test
        COMMAND termin_render_passes_picking_test
    )

    add_executable(termin_render_passes_debug_triangle_pixel_smoke
        tests/test_debug_triangle_pixel_smoke.cpp
    )
    target_include_directories(termin_render_passes_debug_triangle_pixel_smoke PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/../termin-thirdparty/guard
    )
    target_link_libraries(termin_render_passes_debug_triangle_pixel_smoke PRIVATE
        termin_render_passes
    )
    if(TARGET termin_shaderc)
        add_dependencies(termin_render_passes_debug_triangle_pixel_smoke termin_shaderc)
    endif()
    set_target_properties(termin_render_passes_debug_triangle_pixel_smoke PROPERTIES
        RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    )
    add_test(
        NAME termin_render_passes_debug_triangle_pixel_smoke
        COMMAND termin_render_passes_debug_triangle_pixel_smoke
    )
    set_tests_properties(termin_render_passes_debug_triangle_pixel_smoke PROPERTIES
        TIMEOUT 20
        SKIP_REGULAR_EXPRESSION
            "Vulkan backend not compiled|Failed to create Vulkan device: Failed to create Vulkan instance|Failed to create Vulkan device: No Vulkan-capable GPU found"
    )
    termin_add_test_labels(termin_render_passes_debug_triangle_pixel_smoke
        "termin:capability:vulkan")

    add_executable(termin_render_passes_color_pass_pixel_smoke
        tests/test_color_pass_pixel_smoke.cpp
    )
    target_include_directories(termin_render_passes_color_pass_pixel_smoke PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/../termin-thirdparty/guard
    )
    target_link_libraries(termin_render_passes_color_pass_pixel_smoke PRIVATE
        termin_render_passes
    )
    if(TARGET termin_shaderc)
        add_dependencies(termin_render_passes_color_pass_pixel_smoke termin_shaderc)
    endif()
    set_target_properties(termin_render_passes_color_pass_pixel_smoke PROPERTIES
        RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    )
    add_test(
        NAME termin_render_passes_color_pass_pixel_smoke
        COMMAND termin_render_passes_color_pass_pixel_smoke
    )
    set_tests_properties(termin_render_passes_color_pass_pixel_smoke PROPERTIES
        TIMEOUT 20
        SKIP_REGULAR_EXPRESSION
            "Vulkan backend not compiled|Failed to create Vulkan device: Failed to create Vulkan instance|Failed to create Vulkan device: No Vulkan-capable GPU found"
    )
    termin_add_test_labels(termin_render_passes_color_pass_pixel_smoke
        "termin:capability:vulkan")

    add_executable(termin_render_passes_id_pass_line_pixel_smoke
        tests/test_id_pass_line_pixel_smoke.cpp
    )
    target_include_directories(termin_render_passes_id_pass_line_pixel_smoke PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/../termin-thirdparty/guard
    )
    target_compile_definitions(termin_render_passes_id_pass_line_pixel_smoke PRIVATE
        TERMIN_RENDER_PASSES_TEST_FONT_PATH="${CMAKE_CURRENT_SOURCE_DIR}/../termin-thirdparty/recastnavigation/RecastDemo/Bin/DroidSans.ttf"
    )
    target_link_libraries(termin_render_passes_id_pass_line_pixel_smoke PRIVATE
        termin_render_passes
        termin_components_render
    )
    if(TARGET termin_shaderc)
        add_dependencies(termin_render_passes_id_pass_line_pixel_smoke termin_shaderc)
    endif()
    set_target_properties(termin_render_passes_id_pass_line_pixel_smoke PROPERTIES
        RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    )
    add_test(
        NAME termin_render_passes_id_pass_line_pixel_smoke
        COMMAND termin_render_passes_id_pass_line_pixel_smoke
    )
    set_tests_properties(termin_render_passes_id_pass_line_pixel_smoke PROPERTIES
        TIMEOUT 20
        SKIP_REGULAR_EXPRESSION
            "Vulkan backend not compiled|Failed to create Vulkan device: Failed to create Vulkan instance|Failed to create Vulkan device: No Vulkan-capable GPU found"
    )
    termin_add_test_labels(termin_render_passes_id_pass_line_pixel_smoke
        "termin:capability:vulkan")

    add_executable(termin_render_passes_foliage_auxiliary_pass_pixel_smoke
        tests/test_foliage_auxiliary_pass_pixel_smoke.cpp
    )
    target_include_directories(termin_render_passes_foliage_auxiliary_pass_pixel_smoke PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/../termin-thirdparty/guard
    )
    target_link_libraries(termin_render_passes_foliage_auxiliary_pass_pixel_smoke PRIVATE
        termin_bootstrap::termin_bootstrap
        termin_render_passes
        termin_components_render
        termin_components_foliage
    )
    if(TARGET termin_shaderc)
        add_dependencies(termin_render_passes_foliage_auxiliary_pass_pixel_smoke termin_shaderc)
    endif()
    set_target_properties(termin_render_passes_foliage_auxiliary_pass_pixel_smoke PROPERTIES
        RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    )
    add_test(
        NAME termin_render_passes_foliage_auxiliary_pass_pixel_smoke
        COMMAND termin_render_passes_foliage_auxiliary_pass_pixel_smoke
    )
    set_tests_properties(termin_render_passes_foliage_auxiliary_pass_pixel_smoke PROPERTIES
        TIMEOUT 30
        SKIP_REGULAR_EXPRESSION
            "Vulkan backend not compiled|Failed to create Vulkan device: Failed to create Vulkan instance|Failed to create Vulkan device: No Vulkan-capable GPU found"
    )
    termin_add_test_labels(termin_render_passes_foliage_auxiliary_pass_pixel_smoke
        "termin:capability:vulkan")
endif()

install(TARGETS termin_render_passes
    EXPORT termin_render_passesTargets
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
    RUNTIME DESTINATION bin
)

install(DIRECTORY include/ DESTINATION include)

termin_label_tests_in_directory("termin-render-passes")

install(EXPORT termin_render_passesTargets
    FILE termin_render_passesTargets.cmake
    NAMESPACE termin_render_passes::
    DESTINATION lib/cmake/termin_render_passes
)

include(CMakePackageConfigHelpers)

configure_package_config_file(
    ${CMAKE_CURRENT_SOURCE_DIR}/cmake/termin_render_passesConfig.cmake.in
    ${CMAKE_CURRENT_BINARY_DIR}/termin_render_passesConfig.cmake
    INSTALL_DESTINATION lib/cmake/termin_render_passes
)

write_basic_package_version_file(
    ${CMAKE_CURRENT_BINARY_DIR}/termin_render_passesConfigVersion.cmake
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMajorVersion
)

install(FILES
    ${CMAKE_CURRENT_BINARY_DIR}/termin_render_passesConfig.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/termin_render_passesConfigVersion.cmake
    DESTINATION lib/cmake/termin_render_passes
)
