cmake_minimum_required(VERSION 3.16)
project(termin_lighting VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

option(TERMIN_BUILD_PYTHON "Build Python binding _lighting_native" OFF)

# termin-lighting is binding-only: it has no standalone C++ library.
# The nanobind module exposes termin::lighting types that are defined in
# main termin's entity_lib. Therefore this subproject depends on the
# `termin` CMake package and must be built AFTER main termin.
find_package(termin REQUIRED)

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_LIST_DIR}/../cmake")
include(TerminRpath)

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

    nanobind_add_module(_lighting_native NB_SHARED
        cpp/bindings/lighting_bindings.cpp
    )
    target_link_libraries(_lighting_native PRIVATE termin::entity_lib)
    termin_set_rpath_python(_lighting_native)
    install(TARGETS _lighting_native DESTINATION lib/python/termin/lighting)
    install(DIRECTORY ${CMAKE_CURRENT_LIST_DIR}/python/termin/lighting/
            DESTINATION lib/python/termin/lighting
            FILES_MATCHING PATTERN "*.py")
endif()
