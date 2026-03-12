cmake_minimum_required(VERSION 3.16)
project(termin_components_render LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
option(TERMIN_BUILD_PYTHON "Build Python bindings for render components" OFF)

find_package(termin_base REQUIRED)
find_package(termin_mesh REQUIRED)
find_package(termin_graphics REQUIRED)
find_package(termin_inspect REQUIRED)
find_package(termin_scene REQUIRED)
find_package(termin_render REQUIRED)
find_package(termin_display REQUIRED)

include(${CMAKE_CURRENT_LIST_DIR}/../cmake/TerminModule.cmake)

termin_add_module(
    NAME termin_components_render
    NAMESPACE termin_components_render::
    SOURCES
        src/camera_component.cpp
        src/geometry_pass_base.cpp
        src/light_component.cpp
        src/mesh_renderer.cpp
        src/material_pass.cpp
        src/depth_pass.cpp
        src/normal_pass.cpp
    PUBLIC_DEPS
        tcbase::termin_base
        tmesh::termin_mesh
        tgfx::termin_graphics
        termin_inspect::termin_inspect
        termin_scene::termin_scene
        termin_render::termin_render
        termin_display::termin_display
    FIND_DEPS
        termin_base
        termin_mesh
        termin_graphics
        termin_inspect
        termin_scene
        termin_render
        termin_display
    INSTALL_HEADERS
        termin
)

target_include_directories(termin_components_render PRIVATE
    ${CMAKE_CURRENT_LIST_DIR}/../../termin-render/include
    ${CMAKE_CURRENT_LIST_DIR}/../../termin/cpp/termin
    ${CMAKE_CURRENT_LIST_DIR}/../../termin/core_c/include
)

if(TERMIN_BUILD_PYTHON)
    if(NOT Python_EXECUTABLE)
        if(WIN32)
            set(Python_EXECUTABLE "python")
        else()
            set(Python_EXECUTABLE "python3")
        endif()
    endif()

    find_package(Python 3.8 COMPONENTS Interpreter Development REQUIRED)
    find_package(nanobind CONFIG REQUIRED)

    nanobind_add_module(_components_render_native NB_SHARED
        components/render_components_bindings.cpp
    )
    target_link_libraries(_components_render_native PRIVATE termin_components_render)
    target_include_directories(_components_render_native PRIVATE
        ${CMAKE_CURRENT_LIST_DIR}/../../termin-render/include
        ${CMAKE_CURRENT_LIST_DIR}/../../termin/cpp
        ${CMAKE_CURRENT_LIST_DIR}/../../termin/cpp/termin
        ${CMAKE_CURRENT_LIST_DIR}/../../termin/core_c/include
    )

    if(TERMIN_COMPONENTS_RENDER_PYTHON_PREFIX)
        set(_py_dest ${TERMIN_COMPONENTS_RENDER_PYTHON_PREFIX}/render_components)
    else()
        set(_py_dest lib/python/termin/render_components)
    endif()
    install(TARGETS _components_render_native DESTINATION ${_py_dest})
    install(FILES python/termin/render_components/__init__.py DESTINATION ${_py_dest})
endif()
