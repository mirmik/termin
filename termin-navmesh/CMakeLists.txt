cmake_minimum_required(VERSION 3.16)
project(termin_navmesh VERSION 0.1.0 LANGUAGES C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
option(TERMIN_BUILD_PYTHON "Build Python bindings" OFF)

find_package(termin_base REQUIRED)

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_LIST_DIR}/../cmake")
include(TerminRpath)

add_library(termin_navmesh SHARED
    src/tc_navmesh_registry.c
)
add_library(termin_navmesh::termin_navmesh ALIAS termin_navmesh)

target_compile_definitions(termin_navmesh PRIVATE TERMIN_NAVMESH_EXPORTS)

target_include_directories(termin_navmesh PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)

target_link_libraries(termin_navmesh PUBLIC
    tcbase::termin_base
)

set_target_properties(termin_navmesh PROPERTIES
    VERSION ${PROJECT_VERSION}
    SOVERSION 0
)
termin_set_rpath_lib(termin_navmesh)

include(GNUInstallDirs)

install(TARGETS termin_navmesh
    EXPORT termin_navmeshTargets
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
)

install(DIRECTORY include/termin
    DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
)

install(EXPORT termin_navmeshTargets
    FILE termin_navmeshTargets.cmake
    NAMESPACE termin_navmesh::
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_navmesh
)

include(CMakePackageConfigHelpers)

configure_package_config_file(
    cmake/termin_navmeshConfig.cmake.in
    ${CMAKE_CURRENT_BINARY_DIR}/termin_navmeshConfig.cmake
    INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_navmesh
)

write_basic_package_version_file(
    ${CMAKE_CURRENT_BINARY_DIR}/termin_navmeshConfigVersion.cmake
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMajorVersion
)

install(FILES
    ${CMAKE_CURRENT_BINARY_DIR}/termin_navmeshConfig.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/termin_navmeshConfigVersion.cmake
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_navmesh
)
