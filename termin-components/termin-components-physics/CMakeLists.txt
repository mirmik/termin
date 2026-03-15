cmake_minimum_required(VERSION 3.16)
project(termin_components_physics VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_library(termin_components_physics INTERFACE)
add_library(termin_components_physics::termin_components_physics ALIAS termin_components_physics)

target_include_directories(termin_components_physics INTERFACE
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}>
    $<INSTALL_INTERFACE:include>
)

include(GNUInstallDirs)
include(CMakePackageConfigHelpers)

install(TARGETS termin_components_physics
    EXPORT termin_components_physicsTargets
)

if(TERMIN_BUILD_PYTHON)
    if(TERMIN_COMPONENTS_PHYSICS_PYTHON_PREFIX)
        set(_py_dest ${TERMIN_COMPONENTS_PHYSICS_PYTHON_PREFIX}/physics)
    else()
        set(_py_dest lib/python/termin/physics)
    endif()

    install(FILES
        python/termin/physics/physics_world_component.py
        python/termin/physics/rigid_body_component.py
        DESTINATION ${_py_dest}
    )
endif()

install(EXPORT termin_components_physicsTargets
    FILE termin_components_physicsTargets.cmake
    NAMESPACE termin_components_physics::
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_components_physics
)

configure_package_config_file(
    cmake/termin_components_physicsConfig.cmake.in
    ${CMAKE_CURRENT_BINARY_DIR}/termin_components_physicsConfig.cmake
    INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_components_physics
)

write_basic_package_version_file(
    ${CMAKE_CURRENT_BINARY_DIR}/termin_components_physicsConfigVersion.cmake
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMajorVersion
)

install(FILES
    ${CMAKE_CURRENT_BINARY_DIR}/termin_components_physicsConfig.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/termin_components_physicsConfigVersion.cmake
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_components_physics
)
