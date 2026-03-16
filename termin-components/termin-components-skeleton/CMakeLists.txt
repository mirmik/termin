cmake_minimum_required(VERSION 3.16)
project(termin_components_skeleton VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

option(TERMIN_BUILD_PYTHON "Build Python binding for SkeletonController" OFF)

find_package(termin_base REQUIRED)
find_package(termin_scene REQUIRED)
find_package(termin_inspect REQUIRED)
find_package(termin_skeleton REQUIRED)

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_LIST_DIR}/../../cmake")
include(TerminRpath)

add_library(termin_components_skeleton SHARED
    src/skeleton_controller.cpp
)
add_library(termin_components_skeleton::termin_components_skeleton ALIAS termin_components_skeleton)
target_compile_definitions(termin_components_skeleton PRIVATE TERMIN_SCENE_EXPORTS)

target_include_directories(termin_components_skeleton PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)

target_link_libraries(termin_components_skeleton PUBLIC
    tcbase::termin_base
    termin_scene::termin_scene
    termin_inspect::termin_inspect
    termin_skeleton::termin_skeleton
)

include(GNUInstallDirs)
include(CMakePackageConfigHelpers)

install(TARGETS termin_components_skeleton
    EXPORT termin_components_skeletonTargets
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
    RUNTIME DESTINATION ${CMAKE_INSTALL_LIBDIR}
)

install(DIRECTORY include/termin
    DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
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

    nanobind_add_module(_components_skeleton_native NB_SHARED
        ${CMAKE_CURRENT_LIST_DIR}/../../termin/cpp/termin/bindings/skeleton/skeleton_component_module.cpp
    )
    target_include_directories(_components_skeleton_native PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/include
        ${CMAKE_CURRENT_LIST_DIR}/../../termin-scene/include
    )
    target_link_libraries(_components_skeleton_native PRIVATE
        termin_components_skeleton
        termin_inspect::termin_inspect_python
    )
    termin_set_rpath_python(_components_skeleton_native)

    set(_py_dest lib/python/termin/skeleton)
    if(TERMIN_COMPONENTS_SKELETON_PYTHON_PREFIX)
        set(_py_dest ${TERMIN_COMPONENTS_SKELETON_PYTHON_PREFIX}/skeleton)
    endif()
    install(TARGETS _components_skeleton_native DESTINATION ${_py_dest})
endif()

install(EXPORT termin_components_skeletonTargets
    FILE termin_components_skeletonTargets.cmake
    NAMESPACE termin_components_skeleton::
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_components_skeleton
)

configure_package_config_file(
    cmake/termin_components_skeletonConfig.cmake.in
    ${CMAKE_CURRENT_BINARY_DIR}/termin_components_skeletonConfig.cmake
    INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_components_skeleton
)

write_basic_package_version_file(
    ${CMAKE_CURRENT_BINARY_DIR}/termin_components_skeletonConfigVersion.cmake
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMajorVersion
)

install(FILES
    ${CMAKE_CURRENT_BINARY_DIR}/termin_components_skeletonConfig.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/termin_components_skeletonConfigVersion.cmake
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_components_skeleton
)
