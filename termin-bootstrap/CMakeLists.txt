cmake_minimum_required(VERSION 3.16)
project(termin_bootstrap VERSION 0.1.0 LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

option(TERMIN_BUILD_PYTHON "Build Python bindings for termin-bootstrap" OFF)

if(COMMAND termin_require_package)
    termin_require_package(termin_base tcbase::termin_base)
else()
    find_package(termin_base REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_audio termin_audio::termin_audio)
else()
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
if(COMMAND termin_require_package)
    termin_require_package(termin_prefab termin_prefab::termin_prefab)
else()
    find_package(termin_prefab REQUIRED)
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

set(TERMIN_BOOTSTRAP_HAS_ANIMATION OFF)
if(TARGET termin_animation::termin_animation)
    set(TERMIN_BOOTSTRAP_HAS_ANIMATION ON)
elseif(NOT TERMIN_PLATFORM_ANDROID)
    find_package(termin_animation QUIET)
    if(TARGET termin_animation::termin_animation)
        set(TERMIN_BOOTSTRAP_HAS_ANIMATION ON)
    endif()
endif()

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_LIST_DIR}/../cmake")
include(TerminRpath)

set(TERMIN_BOOTSTRAP_SOURCES
    src/bootstrap_core.cpp
)

if(TERMIN_BUILD_PYTHON)
    find_package(Python 3.8 COMPONENTS Interpreter Development REQUIRED)
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

add_library(termin_bootstrap SHARED
    ${TERMIN_BOOTSTRAP_SOURCES}
    include/termin/bootstrap/bootstrap.hpp
    include/termin/bootstrap/bootstrap_c.h
)
add_library(termin_bootstrap::termin_bootstrap ALIAS termin_bootstrap)

target_compile_definitions(termin_bootstrap PRIVATE TERMIN_BOOTSTRAP_EXPORTS)
if(TERMIN_BOOTSTRAP_HAS_ANIMATION)
    target_compile_definitions(termin_bootstrap PUBLIC TERMIN_BOOTSTRAP_HAS_ANIMATION)
endif()
if(TARGET termin_navmesh::termin_navmesh_components)
    target_compile_definitions(termin_bootstrap PUBLIC TERMIN_BOOTSTRAP_HAS_NAVMESH_COMPONENTS)
endif()
if(TARGET termin_components_animation::termin_components_animation)
    target_compile_definitions(termin_bootstrap PUBLIC TERMIN_BOOTSTRAP_HAS_ANIMATION_COMPONENTS)
endif()

if(TERMIN_BUILD_TESTS)
    enable_testing()
    add_executable(termin_bootstrap_explicit_pass_test
        tests/test_explicit_pass_bootstrap.cpp
    )
    add_executable(termin_bootstrap_scene_extension_lifecycle_test
        tests/test_scene_extension_lifecycle.cpp
    )
    target_link_libraries(termin_bootstrap_explicit_pass_test PRIVATE termin_bootstrap)
    target_link_libraries(termin_bootstrap_scene_extension_lifecycle_test PRIVATE
        termin_bootstrap
        termin_engine::termin_engine
    )
    set_target_properties(
        termin_bootstrap_explicit_pass_test
        termin_bootstrap_scene_extension_lifecycle_test
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
    termin_label_tests_in_directory("termin-bootstrap")
endif()

target_include_directories(termin_bootstrap
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include>
)

target_link_libraries(termin_bootstrap
    PUBLIC
        tcbase::termin_base
        termin_audio::termin_audio
        termin_inspect::termin_inspect
        termin_scene::termin_scene
        termin_prefab::termin_prefab
        termin_render::termin_render
        termin_render_passes::termin_render_passes
        termin_collision::termin_collision
        tmesh::termin_mesh
        tgfx::termin_graphics
        tgfx::termin_graphics2
        termin_skeleton::termin_skeleton
        termin_voxels::termin_voxels
        termin_navmesh::termin_navmesh
        termin_components_mesh::termin_components_mesh
        termin_components_collision::termin_components_collision
        termin_components_kinematic::termin_components_kinematic
        termin_components_skeleton::termin_components_skeleton
        termin_components_render::termin_components_render
        termin_components_foliage::termin_components_foliage
)

if(TERMIN_BOOTSTRAP_HAS_ANIMATION)
    target_link_libraries(termin_bootstrap PUBLIC termin_animation::termin_animation)
endif()
if(TARGET termin_navmesh::termin_navmesh_components)
    target_link_libraries(termin_bootstrap PUBLIC termin_navmesh::termin_navmesh_components)
endif()
if(TARGET termin_components_animation::termin_components_animation)
    target_link_libraries(termin_bootstrap PUBLIC termin_components_animation::termin_components_animation)
endif()

if(TERMIN_BUILD_PYTHON)
    target_link_libraries(termin_bootstrap
        PUBLIC
            termin_inspect::termin_inspect_python
            termin_input::termin_input
            termin_display::termin_display
        PRIVATE
            nanobind
            Python::Python
    )
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

set(TERMIN_BOOTSTRAP_CONFIG_FIND_ANIMATION "")
if(TERMIN_BOOTSTRAP_HAS_ANIMATION)
    set(TERMIN_BOOTSTRAP_CONFIG_FIND_ANIMATION "find_dependency(termin_animation REQUIRED)")
endif()
set(TERMIN_BOOTSTRAP_CONFIG_FIND_ANIMATION_COMPONENTS "")
if(TARGET termin_components_animation::termin_components_animation)
    set(TERMIN_BOOTSTRAP_CONFIG_FIND_ANIMATION_COMPONENTS "find_dependency(termin_components_animation REQUIRED)")
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
