# core_c - Pure C library for Termin engine core
# No C++ or Python dependencies
cmake_minimum_required(VERSION 3.14)
project(termin_core C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

# Options
option(TC_BUILD_SHARED "Build shared library" ON)
option(TC_BUILD_TESTS "Build tests" ON)

# Source files (only .c)
# Note: tc_collision.c is NOT included here because collision detection
# requires C++ CollisionWorld from termin.dll. The C API is implemented
# in cpp/termin/tc_collision_c_api.cpp instead.
set(TC_SOURCES
    src/tc_animation_registry.c
    src/tc_component.c
    src/tc_core.c
    src/tc_display.c
    src/tc_entity_pool.c
    src/tc_entity_pool_registry.c
    src/tc_input_manager.c
    src/tc_simple_input_manager.c
    src/tc_frame_graph.c
    src/tc_gpu.c
    src/tc_hash_map.c
    src/tc_inspect.c
    src/tc_kind.c
    src/tc_log.c
    src/tc_material_registry.c
    src/tc_mesh.c
    src/tc_mesh_registry.c
    src/tc_primitive_mesh.c
    src/tc_pass.c
    src/tc_pipeline.c
    src/tc_picking.c
    src/tc_pool.c
    src/tc_profiler.c
    src/tc_project_settings.c
    src/tc_render_surface.c
    src/tc_resource_map.c
    src/tc_scene.c
    src/tc_scene_pipeline_template.c
    src/tc_scene_skybox.c
    src/tc_shader_registry.c
    src/tc_skeleton_registry.c
    src/tc_texture_registry.c
    src/tc_type_registry.c
    src/tc_viewport.c
    src/tc_viewport_config.c
)

# Header files (only .h, for IDE integration)
set(TC_HEADERS
    include/tc_animation.h
    include/tc_animation_registry.h
    include/tc_collision.h
    include/tc_component.h
    include/tc_entity_pool.h
    include/tc_entity_pool_registry.h
    include/tc_gpu.h
    include/tc_handle.h
    include/tc_hash_map.h
    include/tc_inspect.h
    include/tc_kind.h
    include/tc_log.h
    include/tc_material.h
    include/tc_material_registry.h
    include/tc_mesh.h
    include/tc_mesh_registry.h
    include/tc_picking.h
    include/tc_pool.h
    include/tc_pose.h
    include/tc_profiler.h
    include/tc_project_settings.h
    include/tc_quat.h
    include/tc_registry_utils.h
    include/tc_resource.h
    include/tc_resource_map.h
    include/tc_scene.h
    include/tc_scene_pipeline_template.h
    include/tc_scene_pool.h
    include/tc_scene_registry.h
    include/tc_shader.h
    include/tc_shader_registry.h
    include/tc_skeleton.h
    include/tc_skeleton_registry.h
    include/tc_texture.h
    include/tc_texture_registry.h
    include/tc_type_registry.h
    include/tc_types.h
    include/tc_vec3.h
    include/tc_viewport_config.h
    include/termin_core.h
    include/render/tc_display.h
    include/render/tc_input_manager.h
    include/render/tc_simple_input_manager.h
    include/render/tc_pass.h
    include/render/tc_pipeline.h
    include/render/tc_pipeline_pool.h
    include/render/tc_render_surface.h
    include/render/tc_viewport.h
    include/render/tc_frame_graph.h
)

# Library target
if(TC_BUILD_SHARED)
    add_library(termin_core SHARED ${TC_SOURCES} ${TC_HEADERS})
    target_compile_definitions(termin_core PRIVATE TC_EXPORTS)
else()
    add_library(termin_core STATIC ${TC_SOURCES} ${TC_HEADERS})
endif()

set_target_properties(termin_core PROPERTIES
    POSITION_INDEPENDENT_CODE ON
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
)

target_include_directories(termin_core
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include>
)

# Platform-specific
if(WIN32)
    target_link_libraries(termin_core PRIVATE winmm)
    target_compile_definitions(termin_core PRIVATE _CRT_SECURE_NO_WARNINGS)
endif()

if(UNIX AND NOT APPLE)
    target_link_libraries(termin_core PRIVATE m)
endif()

# Compiler warnings
if(MSVC)
    target_compile_options(termin_core PRIVATE /W3)
else()
    target_compile_options(termin_core PRIVATE -Wall -Wextra)
endif()

# Tests
if(TC_BUILD_TESTS)
    enable_testing()

    add_executable(termin_core_test tests/test_main.c)
    target_link_libraries(termin_core_test PRIVATE termin_core)
    if(UNIX AND NOT APPLE)
        target_link_libraries(termin_core_test PRIVATE m)
    endif()
    add_test(NAME termin_core_test COMMAND termin_core_test)

    add_executable(termin_mesh_test tests/test_mesh.c)
    target_link_libraries(termin_mesh_test PRIVATE termin_core)
    add_test(NAME termin_mesh_test COMMAND termin_mesh_test)
endif()

# Install
install(TARGETS termin_core
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
    RUNTIME DESTINATION bin
)

install(FILES ${TC_HEADERS} DESTINATION include/termin_core)
