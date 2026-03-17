cmake_minimum_required(VERSION 3.16)
project(termin_components_collision LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
option(TERMIN_BUILD_PYTHON "Build Python binding for ColliderComponent" OFF)

find_package(termin_base REQUIRED)
find_package(termin_scene REQUIRED)
find_package(termin_inspect REQUIRED)
find_package(termin_mesh REQUIRED)
find_package(termin_collision REQUIRED)

include(${CMAKE_CURRENT_LIST_DIR}/../cmake/TerminModule.cmake)

termin_add_module(
    NAME termin_components_collision
    NAMESPACE termin_components_collision::
    SOURCES components/collider_component.cpp
    PUBLIC_DEPS tcbase::termin_base termin_scene::termin_scene termin_inspect::termin_inspect tmesh::termin_mesh termin_collision::termin_collision
    FIND_DEPS termin_base termin_scene termin_inspect termin_mesh termin_collision
    INSTALL_HEADERS components
)

if(MSVC)
    target_compile_options(termin_components_collision PRIVATE /wd4251 /wd4275)
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

    nanobind_add_module(_components_collision_native NB_SHARED components/collider_component_bindings.cpp)
    target_link_libraries(_components_collision_native PRIVATE termin_components_collision)

    if(TERMIN_COMPONENTS_COLLISION_PYTHON_PREFIX)
        set(_py_dest ${TERMIN_COMPONENTS_COLLISION_PYTHON_PREFIX}/colliders)
    else()
        set(_py_dest lib/python/termin/colliders)
    endif()
    install(TARGETS _components_collision_native DESTINATION ${_py_dest})
endif()
