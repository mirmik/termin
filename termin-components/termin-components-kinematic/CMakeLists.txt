cmake_minimum_required(VERSION 3.16)
project(termin_components_kinematic LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
option(TERMIN_BUILD_PYTHON "Build Python binding for kinematic components" OFF)

find_package(termin_base REQUIRED)
find_package(termin_scene REQUIRED)
find_package(termin_inspect REQUIRED)

include(${CMAKE_CURRENT_LIST_DIR}/../cmake/TerminModule.cmake)

termin_add_module(
    NAME termin_components_kinematic
    NAMESPACE termin_components_kinematic::
    SOURCES
        components/kinematic_unit_component.cpp
        components/actuator_component.cpp
        components/rotator_component.cpp
    PUBLIC_DEPS tcbase::termin_base termin_scene::termin_scene termin_inspect::termin_inspect
    FIND_DEPS termin_base termin_scene termin_inspect
    INSTALL_HEADERS components
)

if(MSVC)
    target_compile_options(termin_components_kinematic PRIVATE /wd4251 /wd4275)
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

    nanobind_add_module(_components_kinematic_native NB_SHARED components/kinematic_bindings.cpp)
    target_link_libraries(_components_kinematic_native PRIVATE termin_components_kinematic)

    if(TERMIN_COMPONENTS_KINEMATIC_PYTHON_PREFIX)
        set(_py_dest ${TERMIN_COMPONENTS_KINEMATIC_PYTHON_PREFIX}/kinematic)
    else()
        set(_py_dest lib/python/termin/kinematic)
    endif()
    install(TARGETS _components_kinematic_native DESTINATION ${_py_dest})
endif()
