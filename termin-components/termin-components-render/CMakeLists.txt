cmake_minimum_required(VERSION 3.16)
project(termin_components_render LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
option(TERMIN_BUILD_PYTHON "Build Python bindings for render components" OFF)

if(COMMAND termin_require_package)
    termin_require_package(termin_base tcbase::termin_base)
else()
    find_package(termin_base REQUIRED)
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
    termin_require_package(termin_render termin_render::termin_render)
else()
    find_package(termin_render REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_display termin_display::termin_display)
else()
    find_package(termin_display REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_components_mesh termin_components_mesh::termin_components_mesh)
else()
    find_package(termin_components_mesh REQUIRED)
endif()

include(${CMAKE_CURRENT_LIST_DIR}/../cmake/TerminModule.cmake)

termin_add_module(
    NAME termin_components_render
    NAMESPACE termin_components_render::
    SOURCES
        src/camera_component.cpp
        src/geometry_pass_base.cpp
        src/light_component.cpp
        src/xr_origin_component.cpp
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
        termin_components_mesh::termin_components_mesh
    FIND_DEPS
        termin_base
        termin_mesh
        termin_graphics
        termin_inspect
        termin_scene
        termin_render
        termin_display
        termin_components_mesh
    INSTALL_HEADERS
        termin
)

if(MSVC)
    target_compile_options(termin_components_render PRIVATE /wd4251 /wd4275)
endif()

set_target_properties(termin_components_render PROPERTIES
    WINDOWS_EXPORT_ALL_SYMBOLS ON
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

    if(TERMIN_COMPONENTS_RENDER_PYTHON_PREFIX)
        set(_py_dest ${TERMIN_COMPONENTS_RENDER_PYTHON_PREFIX}/render_components)
    else()
        set(_py_dest lib/python/termin/render_components)
    endif()
    install(TARGETS _components_render_native DESTINATION ${_py_dest})
    install(FILES
        python/termin/render_components/__init__.py
        python/termin/render_components/line_renderer.py
        python/termin/render_components/skinned_mesh_renderer.py
        python/termin/render_components/skybox_renderer.py
        python/termin/render_components/skeleton_controller.py
        DESTINATION ${_py_dest}
    )
endif()
