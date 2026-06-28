cmake_minimum_required(VERSION 3.16)
project(termin_components_foliage LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
option(TERMIN_BUILD_PYTHON "Build Python bindings for foliage components" OFF)

if(COMMAND termin_require_package)
    termin_require_package(termin_base tcbase::termin_base)
else()
    find_package(termin_base REQUIRED)
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
    termin_require_package(termin_mesh tmesh::termin_mesh)
else()
    find_package(termin_mesh REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_graphics tgfx::termin_graphics)
else()
    find_package(termin_graphics REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_render termin_render::termin_render)
else()
    find_package(termin_render REQUIRED)
endif()

include(${CMAKE_CURRENT_LIST_DIR}/../cmake/TerminModule.cmake)

termin_add_module(
    NAME termin_components_foliage
    NAMESPACE termin_components_foliage::
    SOURCES
        src/components_bootstrap.cpp
        src/foliage_data.cpp
        src/foliage_data_registry.cpp
        src/foliage_file.cpp
        src/foliage_layer_component.cpp
    PUBLIC_DEPS
        tcbase::termin_base
        termin_inspect::termin_inspect
        termin_scene::termin_scene
        tmesh::termin_mesh
        tgfx::termin_graphics
        termin_render::termin_render
    FIND_DEPS
        termin_base
        termin_inspect
        termin_scene
        termin_mesh
        termin_graphics
        termin_render
    INSTALL_HEADERS
        termin
)

if(MSVC)
    target_compile_options(termin_components_foliage PRIVATE /wd4251 /wd4275)
endif()

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

    nanobind_add_module(_foliage_native NB_SHARED
        cpp/bindings/foliage_module.cpp
    )
    target_link_libraries(_foliage_native PRIVATE termin_components_foliage)

    if(TERMIN_COMPONENTS_FOLIAGE_PYTHON_PREFIX)
        set(_py_dest ${TERMIN_COMPONENTS_FOLIAGE_PYTHON_PREFIX}/foliage)
    else()
        set(_py_dest lib/python/termin/foliage)
    endif()
    install(TARGETS _foliage_native DESTINATION ${_py_dest})
    install(DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/python/termin/foliage/
        DESTINATION ${_py_dest}
        PATTERN "__pycache__" EXCLUDE
        PATTERN "*.pyc" EXCLUDE
    )
endif()
