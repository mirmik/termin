cmake_minimum_required(VERSION 3.16)
project(termin_components_physics VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if(COMMAND termin_require_package)
    termin_require_package(termin_physics termin_physics::termin_physics)
else()
    find_package(termin_physics REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_collision termin_collision::termin_collision)
else()
    find_package(termin_collision REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_components_collision termin_components_collision::termin_components_collision)
else()
    find_package(termin_components_collision REQUIRED)
endif()

add_library(termin_components_physics INTERFACE)
add_library(termin_components_physics::termin_components_physics ALIAS termin_components_physics)

target_include_directories(termin_components_physics INTERFACE
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}>
    $<INSTALL_INTERFACE:include>
)

target_link_libraries(termin_components_physics INTERFACE
    termin_physics::termin_physics
    termin_collision::termin_collision
    termin_components_collision::termin_components_collision
)

include(GNUInstallDirs)
include(CMakePackageConfigHelpers)

install(TARGETS termin_components_physics
    EXPORT termin_components_physicsTargets
)

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
