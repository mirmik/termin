cmake_minimum_required(VERSION 3.16)
project(termin_input VERSION 0.1.0 LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

option(TERMIN_BUILD_PYTHON "Build Python-related input bridge code" OFF)

find_package(termin_base REQUIRED)
find_package(termin_scene REQUIRED)

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_LIST_DIR}/../cmake")
include(TerminRpath)

set(TERMIN_INPUT_SOURCES
    src/tc_input_capability.c
    src/tc_input_component.c
    src/tc_input_scene.c
    src/tc_input_entity_pool.c
    src/tc_component_python_input.c
)

set(TERMIN_INPUT_CXX_SOURCES
    cpp/entity/input_handler.cpp
)

add_library(termin_input SHARED
    ${TERMIN_INPUT_SOURCES}
    ${TERMIN_INPUT_CXX_SOURCES}
)
add_library(termin_input::termin_input ALIAS termin_input)

target_compile_definitions(termin_input PRIVATE TERMIN_INPUT_EXPORTS)

target_include_directories(termin_input
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include>
)

target_link_libraries(termin_input
    PUBLIC
        tcbase::termin_base
        termin_scene::termin_scene
)

termin_set_rpath_lib(termin_input)

include(GNUInstallDirs)
include(CMakePackageConfigHelpers)

install(TARGETS termin_input
    EXPORT termin_inputTargets
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
)

install(DIRECTORY include/
    DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
)

install(EXPORT termin_inputTargets
    FILE termin_inputTargets.cmake
    NAMESPACE termin_input::
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_input
)

configure_package_config_file(
    ${CMAKE_CURRENT_SOURCE_DIR}/cmake/termin_inputConfig.cmake.in
    ${CMAKE_CURRENT_BINARY_DIR}/termin_inputConfig.cmake
    INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_input
)

write_basic_package_version_file(
    ${CMAKE_CURRENT_BINARY_DIR}/termin_inputConfigVersion.cmake
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMajorVersion
)

install(FILES
    ${CMAKE_CURRENT_BINARY_DIR}/termin_inputConfig.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/termin_inputConfigVersion.cmake
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_input
)
