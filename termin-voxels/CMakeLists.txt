cmake_minimum_required(VERSION 3.16)
project(termin_voxels VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

option(TERMIN_BUILD_PYTHON "Build Python binding _voxels_native" OFF)

if(COMMAND termin_require_package)
    termin_require_package(termin_base tcbase::termin_base)
else()
    find_package(termin_base REQUIRED)
endif()

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_LIST_DIR}/../cmake")
include(TerminRpath)
include(GNUInstallDirs)

add_library(termin_voxels SHARED
    src/tc_voxel_grid_registry.cpp
)
add_library(termin_voxels::termin_voxels ALIAS termin_voxels)

target_compile_definitions(termin_voxels PRIVATE TERMIN_VOXELS_EXPORTS)

target_include_directories(termin_voxels PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}>
    $<INSTALL_INTERFACE:include>
)

target_link_libraries(termin_voxels PUBLIC
    tcbase::termin_base
)

set_target_properties(termin_voxels PROPERTIES
    VERSION ${PROJECT_VERSION}
    SOVERSION 0
)
termin_set_rpath_lib(termin_voxels)

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

    if(COMMAND termin_require_package)
        termin_require_package(termin_inspect termin_inspect::termin_inspect_python)
    else()
        find_package(termin_inspect REQUIRED)
    endif()
    if(NOT TARGET termin_inspect::termin_inspect_python)
        message(FATAL_ERROR "termin-voxels Python build requires termin_inspect::termin_inspect_python")
    endif()

    nanobind_add_module(_voxels_native NB_SHARED
        python/bindings/voxels_bindings.cpp
    )
    target_link_libraries(_voxels_native PRIVATE
        termin_voxels::termin_voxels
        termin_inspect::termin_inspect_python
    )
    termin_set_rpath_python(_voxels_native)
    install(TARGETS _voxels_native DESTINATION lib/python/termin/voxels)
endif()

install(TARGETS termin_voxels
    EXPORT termin_voxelsTargets
)

install(DIRECTORY termin/
    DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}/termin
    FILES_MATCHING PATTERN "*.h" PATTERN "*.hpp"
)

install(EXPORT termin_voxelsTargets
    FILE termin_voxelsTargets.cmake
    NAMESPACE termin_voxels::
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_voxels
)

set(_config_path "${CMAKE_CURRENT_BINARY_DIR}/termin_voxelsConfig.cmake")
set(_cmake_current_list_dir_literal [[${CMAKE_CURRENT_LIST_DIR}]])
file(WRITE ${_config_path}
    "include(CMakeFindDependencyMacro)\n"
    "find_dependency(termin_base REQUIRED)\n"
    "include(\"${_cmake_current_list_dir_literal}/termin_voxelsTargets.cmake\")\n"
)
install(FILES ${_config_path}
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_voxels
)
