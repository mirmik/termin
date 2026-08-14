cmake_minimum_required(VERSION 3.14)
project(termin_render VERSION 0.1.0 LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

option(TERMIN_RENDER_BUILD_SHARED "Build shared library" ON)
option(TERMIN_BUILD_PYTHON "Build Python bindings for termin-render" OFF)

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
    termin_require_package(termin_materials termin_materials::termin_materials)
else()
    find_package(termin_materials REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(
        termin_render_core
        termin_render_core::termin_render_core)
    termin_require_package(termin_lighting termin_lighting::termin_lighting)
    termin_require_package(termin_scene termin_scene::termin_scene)
else()
    find_package(termin_render_core REQUIRED)
    find_package(termin_lighting REQUIRED)
    find_package(termin_scene REQUIRED)
endif()

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_LIST_DIR}/../../cmake")
include(TerminRpath)

set(TERMIN_RENDER_SOURCES
    src/termin_render_version.c
    src/tc_project_settings.c
    src/tc_viewport_config.c
    src/tc_component_python_drawable.c
    src/tc_component_python_render_lifecycle.c
    src/tc_debug_geometry.c
    src/tc_render_lifecycle.c
    src/tc_drawable_capability.c
    src/tc_light_capability.c
    src/tc_camera_capability.c
    src/tc_scene_drawable.c
    src/tc_scene_render_mount.c
    src/tc_scene_render_state.c
    src/tc_scene_skybox.c
    src/tc_render_target.c
    src/tc_render_target_config.c
    src/tc_scene_render_ext.cpp
    src/viewport_config.cpp
    src/render_target_config.cpp
    src/drawable.cpp
    src/debug_geometry.cpp
    src/render_lifecycle.cpp
    src/camera_capability.cpp
    src/graph_compiler.cpp
    src/graph_data.cpp
    src/graph_node_def.cpp
    src/render_scene_item_collector.cpp
    src/scene_render_services.cpp
    src/scene_render_execution.cpp
    src/shader_usage_collector.cpp
)


if(TERMIN_RENDER_BUILD_SHARED)
    add_library(termin_render SHARED ${TERMIN_RENDER_SOURCES})
    target_compile_definitions(termin_render PRIVATE TERMIN_RENDER_EXPORTS TC_EXPORTS)
else()
    add_library(termin_render STATIC ${TERMIN_RENDER_SOURCES})
endif()

if(COMMAND termin_enable_unity_build_for)
    termin_enable_unity_build_for(termin_render)
endif()
if(COMMAND termin_enable_pch_for)
    termin_enable_pch_for(termin_render)
endif()

add_library(termin_render::termin_render ALIAS termin_render)

set_target_properties(termin_render PROPERTIES
    POSITION_INDEPENDENT_CODE ON
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
)
termin_set_rpath_lib(termin_render)

target_include_directories(termin_render PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)
target_compile_features(termin_render PUBLIC cxx_std_20)
target_link_libraries(termin_render PUBLIC
    termin_render_core::termin_render_core
    termin_scene::termin_scene
    termin_lighting::termin_lighting
)

if(UNIX AND NOT APPLE)
    target_link_libraries(termin_render PRIVATE m)
endif()

if(MSVC)
    target_compile_options(termin_render PRIVATE /W3 /wd4251 /wd4275)
    target_compile_definitions(termin_render PRIVATE _CRT_SECURE_NO_WARNINGS)
else()
    target_compile_options(termin_render PRIVATE -Wall -Wextra)
endif()

if(TERMIN_BUILD_TESTS)
    enable_testing()

    add_executable(termin_render_drawable_test tests/test_drawable_capability.c)
    target_include_directories(termin_render_drawable_test PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/../../termin-thirdparty/guard
    )
    target_link_libraries(termin_render_drawable_test PRIVATE termin_render)
    add_test(NAME termin_render_drawable_test COMMAND termin_render_drawable_test)

    add_executable(termin_render_lifecycle_test tests/test_render_lifecycle.c)
    target_include_directories(termin_render_lifecycle_test PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/../../termin-thirdparty/guard
    )
    target_link_libraries(termin_render_lifecycle_test PRIVATE termin_render)
    add_test(NAME termin_render_lifecycle_test COMMAND termin_render_lifecycle_test)

    add_executable(termin_render_target_dimensions_test tests/test_render_target_dimensions.c)
    target_include_directories(termin_render_target_dimensions_test PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/../../termin-thirdparty/guard
    )
    target_link_libraries(termin_render_target_dimensions_test PRIVATE termin_render)
    add_test(NAME termin_render_target_dimensions_test COMMAND termin_render_target_dimensions_test)

    add_executable(
        termin_render_execute_context_render_pass_test
        tests/test_execute_context_render_pass.cpp)
    target_include_directories(
        termin_render_execute_context_render_pass_test
        PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/../../termin-thirdparty/guard)
    target_link_libraries(
        termin_render_execute_context_render_pass_test
        PRIVATE termin_render)
    add_test(
        NAME termin_render_execute_context_render_pass_test
        COMMAND termin_render_execute_context_render_pass_test)

    add_executable(termin_render_camera_capability_test tests/test_camera_capability.cpp)
    target_include_directories(termin_render_camera_capability_test PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/../../termin-thirdparty/guard
    )
    target_link_libraries(termin_render_camera_capability_test PRIVATE termin_render)
    add_test(NAME termin_render_camera_capability_test COMMAND termin_render_camera_capability_test)

    add_library(
        termin_render_project_surface_test_plugin SHARED
        tests/project_surface_test_plugin.cpp
    )
    target_link_libraries(
        termin_render_project_surface_test_plugin
        PRIVATE termin_materials::termin_materials
    )
    set_target_properties(
        termin_render_project_surface_test_plugin
        PROPERTIES
            WINDOWS_EXPORT_ALL_SYMBOLS ON
            LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
            RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
            ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    )
    termin_set_rpath_lib(termin_render_project_surface_test_plugin)

    add_executable(
        termin_render_project_surface_contract_test
        tests/test_project_surface_contract.cpp
    )
    target_include_directories(
        termin_render_project_surface_contract_test
        PRIVATE
            ${CMAKE_CURRENT_SOURCE_DIR}/../../termin-thirdparty/guard
            ${CMAKE_CURRENT_SOURCE_DIR}/tests
    )
    target_link_libraries(
        termin_render_project_surface_contract_test
        PRIVATE
            termin_render
            termin_render_project_surface_test_plugin
    )
    if(TARGET termin_shaderc)
        add_dependencies(
            termin_render_project_surface_contract_test
            termin_shaderc
        )
        target_compile_definitions(
            termin_render_project_surface_contract_test
            PRIVATE
                TERMIN_PROJECT_SURFACE_TEST_SHADERC="$<TARGET_FILE:termin_shaderc>"
        )
    endif()
    add_test(
        NAME termin_render_project_surface_contract_test
        COMMAND termin_render_project_surface_contract_test
    )

    add_executable(
        termin_render_scene_item_snapshot_test
        tests/test_render_scene_item_snapshot.cpp)
    target_link_libraries(
        termin_render_scene_item_snapshot_test
        PRIVATE termin_render)
    add_test(
        NAME termin_render_scene_item_snapshot_test
        COMMAND termin_render_scene_item_snapshot_test)

    set_target_properties(
        termin_render_drawable_test
        termin_render_target_dimensions_test
        termin_render_camera_capability_test
        termin_render_project_surface_contract_test
        termin_render_scene_item_snapshot_test
        PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    )
endif()

if(TERMIN_BUILD_PYTHON)
    find_package(Python 3.14 COMPONENTS Interpreter Development REQUIRED)
    find_package(nanobind CONFIG REQUIRED)

    nanobind_add_module(_render_framework_native NB_SHARED
        python/render_framework_bindings.cpp
        python/tc_pass_bindings.cpp
        python/tc_render_target_bindings.cpp
        python/render_engine_bindings.cpp
        python/render_pipeline_bindings.cpp
    )
    target_link_libraries(_render_framework_native PRIVATE termin_render termin_inspect::termin_inspect_python)
    target_include_directories(_render_framework_native PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/include
    )
    termin_set_rpath_python(_render_framework_native)
    install(TARGETS _render_framework_native DESTINATION lib/python/termin/render_framework)
    install(DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/python/termin/render_framework/
        DESTINATION lib/python/termin/render_framework
        PATTERN "__pycache__" EXCLUDE
        PATTERN "*.pyc" EXCLUDE
        PATTERN "*.so" EXCLUDE
        PATTERN "lib" EXCLUDE
    )

    # Drawable capability bindings (install_drawable_vtable, is_drawable, etc.)
    nanobind_add_module(_render_native NB_SHARED
        python/render_native_bindings.cpp
        python/drawable_bindings.cpp
        python/render_config_bindings.cpp
        python/scene_render_extension_bindings.cpp
    )
    target_link_libraries(_render_native PRIVATE termin_render)
    termin_set_rpath_python(_render_native)
    install(TARGETS _render_native DESTINATION lib/python/termin/render)
    install(DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/python/termin/render/
        DESTINATION lib/python/termin/render
        PATTERN "__pycache__" EXCLUDE
        PATTERN "*.pyc" EXCLUDE
        PATTERN "*.so" EXCLUDE
        PATTERN "lib" EXCLUDE
    )
endif()

install(TARGETS termin_render
    EXPORT termin_renderTargets
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
    RUNTIME DESTINATION bin
)

install(DIRECTORY include/
    DESTINATION include
)

install(EXPORT termin_renderTargets
    FILE termin_renderTargets.cmake
    NAMESPACE termin_render::
    DESTINATION lib/cmake/termin_render
)

include(CMakePackageConfigHelpers)

configure_package_config_file(
    ${CMAKE_CURRENT_SOURCE_DIR}/cmake/termin_renderConfig.cmake.in
    ${CMAKE_CURRENT_BINARY_DIR}/termin_renderConfig.cmake
    INSTALL_DESTINATION lib/cmake/termin_render
)

write_basic_package_version_file(
    ${CMAKE_CURRENT_BINARY_DIR}/termin_renderConfigVersion.cmake
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMajorVersion
)

install(FILES
    ${CMAKE_CURRENT_BINARY_DIR}/termin_renderConfig.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/termin_renderConfigVersion.cmake
    DESTINATION lib/cmake/termin_render
)

termin_label_tests_in_directory("termin-render")
