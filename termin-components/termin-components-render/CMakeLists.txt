cmake_minimum_required(VERSION 3.16)
project(termin_components_render LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(termin_base REQUIRED)
find_package(termin_mesh REQUIRED)
find_package(termin_graphics REQUIRED)
find_package(termin_inspect REQUIRED)
find_package(termin_scene REQUIRED)
find_package(termin_render REQUIRED)

include(${CMAKE_CURRENT_LIST_DIR}/../cmake/TerminModule.cmake)

termin_add_module(
    NAME termin_components_render
    NAMESPACE termin_components_render::
    SOURCES
        src/geometry_pass_base.cpp
        src/mesh_renderer.cpp
        src/material_pass.cpp
        src/depth_pass.cpp
        src/normal_pass.cpp
        src/id_pass.cpp
    PUBLIC_DEPS
        tcbase::termin_base
        tmesh::termin_mesh
        tgfx::termin_graphics
        termin_inspect::termin_inspect
        termin_scene::termin_scene
        termin_render::termin_render
    FIND_DEPS
        termin_base
        termin_mesh
        termin_graphics
        termin_inspect
        termin_scene
        termin_render
    INSTALL_HEADERS
        termin
)

target_include_directories(termin_components_render PRIVATE
    ${CMAKE_CURRENT_LIST_DIR}/../../termin/cpp/termin
    ${CMAKE_CURRENT_LIST_DIR}/../../termin/core_c/include
)
