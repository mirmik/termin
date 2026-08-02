cmake_minimum_required(VERSION 3.16)
project(termin_bootstrap VERSION 0.1.0 LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

option(TERMIN_BUILD_PYTHON "Build Python bindings for termin-bootstrap" OFF)
option(TERMIN_BOOTSTRAP_MINIMAL_ONLY
    "Build only the core scene bootstrap profile without desktop runtime domains"
    OFF)
option(TERMIN_BOOTSTRAP_RENDER_ONLY
    "Build the portable scene/render bootstrap profile"
    OFF)

if(TERMIN_BOOTSTRAP_MINIMAL_ONLY AND TERMIN_BOOTSTRAP_RENDER_ONLY)
    message(FATAL_ERROR "TERMIN_BOOTSTRAP_MINIMAL_ONLY and TERMIN_BOOTSTRAP_RENDER_ONLY are mutually exclusive")
endif()

if(COMMAND termin_require_package)
    termin_require_package(termin_base tcbase::termin_base)
else()
    find_package(termin_base REQUIRED)
endif()
if(NOT TERMIN_BOOTSTRAP_MINIMAL_ONLY AND NOT TERMIN_BOOTSTRAP_RENDER_ONLY AND COMMAND termin_require_package)
    termin_require_package(termin_audio termin_audio::termin_audio)
elseif(NOT TERMIN_BOOTSTRAP_MINIMAL_ONLY AND NOT TERMIN_BOOTSTRAP_RENDER_ONLY)
    find_package(termin_audio REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_inspect termin_inspect::termin_inspect)
else()
    find_package(termin_inspect REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_scene termin_scene::termin_scene)
else()
    find_package(termin_scene REQUIRED)
endif()
if(NOT TERMIN_BOOTSTRAP_MINIMAL_ONLY AND NOT TERMIN_BOOTSTRAP_RENDER_ONLY)
if(COMMAND termin_require_package)
    termin_require_package(termin_prefab termin_prefab::termin_prefab)
else()
    find_package(termin_prefab REQUIRED)
endif()

if(TERMIN_BOOTSTRAP_RENDER_ONLY)
    foreach(_termin_render_bootstrap_dependency IN ITEMS
            termin_mesh termin_graphics termin_materials termin_render
            termin_render_passes termin_components_mesh termin_components_render)
        if(COMMAND termin_require_package)
            if(_termin_render_bootstrap_dependency STREQUAL "termin_mesh")
                termin_require_package(termin_mesh tmesh::termin_mesh)
            elseif(_termin_render_bootstrap_dependency STREQUAL "termin_graphics")
                termin_require_package(termin_graphics tgfx::termin_graphics tgfx::termin_graphics2)
            elseif(_termin_render_bootstrap_dependency STREQUAL "termin_materials")
                termin_require_package(termin_materials termin_materials::termin_materials)
            elseif(_termin_render_bootstrap_dependency STREQUAL "termin_render")
                termin_require_package(termin_render termin_render::termin_render)
            elseif(_termin_render_bootstrap_dependency STREQUAL "termin_render_passes")
                termin_require_package(termin_render_passes termin_render_passes::termin_render_passes)
            elseif(_termin_render_bootstrap_dependency STREQUAL "termin_components_mesh")
                termin_require_package(termin_components_mesh termin_components_mesh::termin_components_mesh)
            elseif(_termin_render_bootstrap_dependency STREQUAL "termin_components_render")
                termin_require_package(termin_components_render termin_components_render::termin_components_render)
            endif()
        endif()
    endforeach()
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_render termin_render::termin_render)
else()
    find_package(termin_render REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_render_passes termin_render_passes::termin_render_passes)
else()
    find_package(termin_render_passes REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_collision termin_collision::termin_collision)
else()
    find_package(termin_collision REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_mesh tmesh::termin_mesh)
else()
    find_package(termin_mesh REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_graphics tgfx::termin_graphics tgfx::termin_graphics2)
else()
    find_package(termin_graphics REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_materials termin_materials::termin_materials)
else()
    find_package(termin_materials REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_skeleton termin_skeleton::termin_skeleton)
else()
    find_package(termin_skeleton REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_voxels termin_voxels::termin_voxels)
else()
    find_package(termin_voxels REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_navmesh termin_navmesh::termin_navmesh)
else()
    find_package(termin_navmesh REQUIRED)
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
    termin_require_package(termin_components_kinematic termin_components_kinematic::termin_components_kinematic)
else()
    find_package(termin_components_kinematic REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_components_physics_fem termin_components_physics_fem::termin_components_physics_fem)
else()
    find_package(termin_components_physics_fem REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_components_physics_fem_ui termin_components_physics_fem_ui::termin_components_physics_fem_ui)
else()
    find_package(termin_components_physics_fem_ui REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_components_skeleton termin_components_skeleton::termin_components_skeleton)
else()
    find_package(termin_components_skeleton REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_components_render termin_components_render::termin_components_render)
else()
    find_package(termin_components_render REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_components_foliage termin_components_foliage::termin_components_foliage)
else()
    find_package(termin_components_foliage REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_components_ui termin_components_ui::termin_components_ui)
else()
    find_package(termin_components_ui REQUIRED)
endif()

set(TERMIN_BOOTSTRAP_HAS_ANIMATION OFF)
if(TARGET termin_animation::termin_animation)
    set(TERMIN_BOOTSTRAP_HAS_ANIMATION ON)
elseif(NOT TERMIN_PLATFORM_ANDROID)
    find_package(termin_animation QUIET)
    if(TARGET termin_animation::termin_animation)
        set(TERMIN_BOOTSTRAP_HAS_ANIMATION ON)
    endif()
endif()

set(TERMIN_BOOTSTRAP_HAS_TCPLOT_GUI_NATIVE OFF)
if(TARGET tcplot_gui_native::tcplot_gui_native)
    set(TERMIN_BOOTSTRAP_HAS_TCPLOT_GUI_NATIVE ON)
elseif(NOT TERMIN_PLATFORM_ANDROID)
    find_package(tcplot_gui_native QUIET)
    if(TARGET tcplot_gui_native::tcplot_gui_native)
        set(TERMIN_BOOTSTRAP_HAS_TCPLOT_GUI_NATIVE ON)
    endif()
endif()
else()
    set(TERMIN_BOOTSTRAP_HAS_ANIMATION OFF)
    set(TERMIN_BOOTSTRAP_HAS_TCPLOT_GUI_NATIVE OFF)
endif()

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_LIST_DIR}/../cmake")
include(TerminRpath)

if(TERMIN_BOOTSTRAP_MINIMAL_ONLY)
    set(TERMIN_BOOTSTRAP_SOURCES src/bootstrap_minimal.cpp)
elseif(TERMIN_BOOTSTRAP_RENDER_ONLY)
    set(TERMIN_BOOTSTRAP_SOURCES src/bootstrap_render.cpp)
else()
    set(TERMIN_BOOTSTRAP_SOURCES src/bootstrap_core.cpp)
endif()

if(TERMIN_BUILD_PYTHON)
    if(TERMIN_BOOTSTRAP_MINIMAL_ONLY)
        message(FATAL_ERROR "TERMIN_BUILD_PYTHON is incompatible with TERMIN_BOOTSTRAP_MINIMAL_ONLY")
    endif()
    find_package(Python 3.14 COMPONENTS Interpreter Development REQUIRED)
    find_package(nanobind CONFIG REQUIRED)
    if(COMMAND termin_require_package)
        termin_require_package(termin_input termin_input::termin_input)
    else()
        find_package(termin_input REQUIRED)
    endif()
    if(COMMAND termin_require_package)
        termin_require_package(termin_display termin_display::termin_display)
    else()
        find_package(termin_display REQUIRED)
    endif()
    if(NOT TARGET termin_inspect::termin_inspect_python)
        message(FATAL_ERROR "termin-bootstrap Python build requires termin_inspect::termin_inspect_python")
    endif()
    list(APPEND TERMIN_BOOTSTRAP_SOURCES src/bootstrap_python.cpp)
else()
    list(APPEND TERMIN_BOOTSTRAP_SOURCES src/bootstrap_python_stub.cpp)
endif()

set(TERMIN_BOOTSTRAP_LIBRARY_TYPE SHARED)
if(EMSCRIPTEN)
    set(TERMIN_BOOTSTRAP_LIBRARY_TYPE STATIC)
endif()
add_library(termin_bootstrap ${TERMIN_BOOTSTRAP_LIBRARY_TYPE}
    ${TERMIN_BOOTSTRAP_SOURCES}
    include/termin/bootstrap/bootstrap.hpp
    include/termin/bootstrap/bootstrap_c.h
)
add_library(termin_bootstrap::termin_bootstrap ALIAS termin_bootstrap)

target_compile_definitions(termin_bootstrap PRIVATE TERMIN_BOOTSTRAP_EXPORTS)
if(TERMIN_BOOTSTRAP_MINIMAL_ONLY)
    target_compile_definitions(termin_bootstrap PUBLIC TERMIN_BOOTSTRAP_MINIMAL_ONLY)
endif()
if(TERMIN_BOOTSTRAP_RENDER_ONLY)
    target_compile_definitions(termin_bootstrap PUBLIC TERMIN_BOOTSTRAP_RENDER_ONLY)
endif()
if(TERMIN_BOOTSTRAP_HAS_ANIMATION)
    target_compile_definitions(termin_bootstrap PUBLIC TERMIN_BOOTSTRAP_HAS_ANIMATION)
endif()
if(TARGET termin_navmesh::termin_navmesh_components)
    target_compile_definitions(termin_bootstrap PUBLIC TERMIN_BOOTSTRAP_HAS_NAVMESH_COMPONENTS)
endif()
if(TARGET termin_components_animation::termin_components_animation)
    target_compile_definitions(termin_bootstrap PUBLIC TERMIN_BOOTSTRAP_HAS_ANIMATION_COMPONENTS)
endif()
if(TERMIN_BOOTSTRAP_HAS_TCPLOT_GUI_NATIVE)
    target_compile_definitions(termin_bootstrap PUBLIC TERMIN_BOOTSTRAP_HAS_TCPLOT_GUI_NATIVE)
endif()

if(TERMIN_BUILD_TESTS AND NOT TERMIN_BOOTSTRAP_MINIMAL_ONLY)
    enable_testing()
    add_executable(termin_bootstrap_explicit_pass_test
        tests/test_explicit_pass_bootstrap.cpp
    )
    add_executable(termin_bootstrap_scene_extension_lifecycle_test
        tests/test_scene_extension_lifecycle.cpp
    )
    add_executable(termin_bootstrap_shader_program_lifecycle_test
        tests/test_shader_program_lifecycle.cpp
    )
    target_link_libraries(termin_bootstrap_explicit_pass_test PRIVATE termin_bootstrap)
    target_link_libraries(termin_bootstrap_scene_extension_lifecycle_test PRIVATE
        termin_bootstrap
        termin_engine::termin_engine
    )
    target_link_libraries(termin_bootstrap_shader_program_lifecycle_test PRIVATE
        termin_bootstrap
    )
    set_target_properties(
        termin_bootstrap_explicit_pass_test
        termin_bootstrap_scene_extension_lifecycle_test
        termin_bootstrap_shader_program_lifecycle_test
        PROPERTIES
        RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    )
    add_test(
        NAME termin_bootstrap_explicit_pass_test
        COMMAND termin_bootstrap_explicit_pass_test
    )
    add_test(
        NAME termin_bootstrap_scene_extension_lifecycle_test
        COMMAND termin_bootstrap_scene_extension_lifecycle_test
    )
    add_test(
        NAME termin_bootstrap_shader_program_lifecycle_test
        COMMAND termin_bootstrap_shader_program_lifecycle_test
    )
    termin_label_tests_in_directory("termin-bootstrap")
endif()

target_include_directories(termin_bootstrap
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include>
)

target_link_libraries(termin_bootstrap PUBLIC
    tcbase::termin_base
    termin_inspect::termin_inspect
    termin_scene::termin_scene
)

if(NOT TERMIN_BOOTSTRAP_MINIMAL_ONLY AND NOT TERMIN_BOOTSTRAP_RENDER_ONLY)
target_link_libraries(termin_bootstrap PUBLIC
        termin_audio::termin_audio
        termin_prefab::termin_prefab
        termin_render::termin_render
        termin_render_passes::termin_render_passes
        termin_collision::termin_collision
        tmesh::termin_mesh
        tgfx::termin_graphics
        tgfx::termin_graphics2
        termin_materials::termin_materials
        termin_skeleton::termin_skeleton
        termin_voxels::termin_voxels
        termin_navmesh::termin_navmesh
        termin_components_mesh::termin_components_mesh
        termin_components_collision::termin_components_collision
        termin_components_kinematic::termin_components_kinematic
        termin_components_physics_fem::termin_components_physics_fem
        termin_components_physics_fem_ui::termin_components_physics_fem_ui
        termin_components_skeleton::termin_components_skeleton
        termin_components_render::termin_components_render
        termin_components_foliage::termin_components_foliage
        termin_components_ui::termin_components_ui
)
endif()
if(TERMIN_BOOTSTRAP_RENDER_ONLY)
target_link_libraries(termin_bootstrap PUBLIC
        tmesh::termin_mesh
        tgfx::termin_graphics
        tgfx::termin_graphics2
        termin_materials::termin_materials
        termin_render::termin_render
        termin_render_passes::termin_render_passes
        termin_components_mesh::termin_components_mesh
        termin_components_render::termin_components_render
)
endif()

if(TERMIN_BOOTSTRAP_HAS_ANIMATION)
    target_link_libraries(termin_bootstrap PUBLIC termin_animation::termin_animation)
endif()
if(TARGET termin_navmesh::termin_navmesh_components)
    target_link_libraries(termin_bootstrap PUBLIC termin_navmesh::termin_navmesh_components)
endif()
if(TARGET termin_components_animation::termin_components_animation)
    target_link_libraries(termin_bootstrap PUBLIC termin_components_animation::termin_components_animation)
endif()
if(TERMIN_BOOTSTRAP_HAS_TCPLOT_GUI_NATIVE)
    target_link_libraries(termin_bootstrap PUBLIC tcplot_gui_native::tcplot_gui_native)
endif()

if(TERMIN_BUILD_PYTHON)
    target_link_libraries(termin_bootstrap
        PUBLIC
            termin_inspect::termin_inspect_python
            termin_input::termin_input
            termin_display::termin_display
        PRIVATE
            Python::Python
    )
    termin_nanobind_link_runtime(termin_bootstrap PRIVATE)
endif()

set_target_properties(termin_bootstrap PROPERTIES
    POSITION_INDEPENDENT_CODE ON
    WINDOWS_EXPORT_ALL_SYMBOLS OFF
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
)
termin_set_rpath_lib(termin_bootstrap)

if(COMMAND termin_enable_pch_for)
    termin_enable_pch_for(termin_bootstrap)
endif()

if(MSVC)
    target_compile_options(termin_bootstrap PRIVATE /W3 /wd4251 /wd4275)
else()
    target_compile_options(termin_bootstrap PRIVATE -Wall -Wextra)
endif()

if(TERMIN_BUILD_PYTHON)
    nanobind_add_module(_bootstrap_native NB_SHARED
        python/bootstrap_module.cpp
    )
    target_link_libraries(_bootstrap_native PRIVATE termin_bootstrap)
    termin_set_rpath_python(_bootstrap_native)
    install(TARGETS _bootstrap_native DESTINATION lib/python/termin/bootstrap)
    install(DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/python/termin/bootstrap/
        DESTINATION lib/python/termin/bootstrap
        PATTERN "__pycache__" EXCLUDE
        PATTERN "*.pyc" EXCLUDE
    )
endif()

install(TARGETS termin_bootstrap
    EXPORT termin_bootstrapTargets
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
    RUNTIME DESTINATION bin
)

install(DIRECTORY include/
    DESTINATION include
)

install(EXPORT termin_bootstrapTargets
    FILE termin_bootstrapTargets.cmake
    NAMESPACE termin_bootstrap::
    DESTINATION lib/cmake/termin_bootstrap
)

include(CMakePackageConfigHelpers)

set(TERMIN_BOOTSTRAP_CONFIG_FIND_FULL_DEPS "")
if(NOT TERMIN_BOOTSTRAP_MINIMAL_ONLY)
    set(TERMIN_BOOTSTRAP_CONFIG_FIND_FULL_DEPS
"find_dependency(termin_audio REQUIRED)
find_dependency(termin_prefab REQUIRED)
find_dependency(termin_render REQUIRED)
find_dependency(termin_render_passes REQUIRED)
find_dependency(termin_collision REQUIRED)
find_dependency(termin_mesh REQUIRED)
find_dependency(termin_graphics REQUIRED)
find_dependency(termin_materials REQUIRED)
find_dependency(termin_skeleton REQUIRED)
find_dependency(termin_voxels REQUIRED)
find_dependency(termin_navmesh REQUIRED)
find_dependency(termin_components_mesh REQUIRED)
find_dependency(termin_components_collision REQUIRED)
find_dependency(termin_components_kinematic REQUIRED)
find_dependency(termin_components_physics_fem REQUIRED)
find_dependency(termin_components_physics_fem_ui REQUIRED)
find_dependency(termin_components_skeleton REQUIRED)
find_dependency(termin_components_render REQUIRED)
find_dependency(termin_components_foliage REQUIRED)
find_dependency(termin_components_ui REQUIRED)")
endif()

set(TERMIN_BOOTSTRAP_CONFIG_FIND_ANIMATION "")
if(TERMIN_BOOTSTRAP_HAS_ANIMATION)
    set(TERMIN_BOOTSTRAP_CONFIG_FIND_ANIMATION "find_dependency(termin_animation REQUIRED)")
endif()
set(TERMIN_BOOTSTRAP_CONFIG_FIND_ANIMATION_COMPONENTS "")
if(TARGET termin_components_animation::termin_components_animation)
    set(TERMIN_BOOTSTRAP_CONFIG_FIND_ANIMATION_COMPONENTS "find_dependency(termin_components_animation REQUIRED)")
endif()
set(TERMIN_BOOTSTRAP_CONFIG_FIND_TCPLOT_GUI_NATIVE "")
if(TERMIN_BOOTSTRAP_HAS_TCPLOT_GUI_NATIVE)
    set(TERMIN_BOOTSTRAP_CONFIG_FIND_TCPLOT_GUI_NATIVE
        "find_dependency(tcplot_gui_native REQUIRED)")
endif()
set(TERMIN_BOOTSTRAP_CONFIG_FIND_PYTHON_DEPS "")
if(TERMIN_BUILD_PYTHON)
    set(TERMIN_BOOTSTRAP_CONFIG_FIND_PYTHON_DEPS
        "find_dependency(termin_input REQUIRED)\nfind_dependency(termin_display REQUIRED)"
    )
endif()

configure_package_config_file(
    ${CMAKE_CURRENT_LIST_DIR}/cmake/termin_bootstrapConfig.cmake.in
    ${CMAKE_CURRENT_BINARY_DIR}/termin_bootstrapConfig.cmake
    INSTALL_DESTINATION lib/cmake/termin_bootstrap
)

write_basic_package_version_file(
    ${CMAKE_CURRENT_BINARY_DIR}/termin_bootstrapConfigVersion.cmake
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMajorVersion
)

install(FILES
    ${CMAKE_CURRENT_BINARY_DIR}/termin_bootstrapConfig.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/termin_bootstrapConfigVersion.cmake
    DESTINATION lib/cmake/termin_bootstrap
)
