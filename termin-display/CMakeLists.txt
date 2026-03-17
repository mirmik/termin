cmake_minimum_required(VERSION 3.14)
project(termin_display VERSION 0.1.0 LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

option(TERMIN_DISPLAY_BUILD_SHARED "Build shared library" ON)
option(TERMIN_BUILD_PYTHON "Build Python bindings for termin-display" OFF)

find_package(termin_base REQUIRED)
find_package(termin_graphics REQUIRED)
find_package(termin_scene REQUIRED)
find_package(termin_input REQUIRED)
find_package(termin_render REQUIRED)

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_LIST_DIR}/../cmake")
include(TerminRpath)

set(TERMIN_DISPLAY_SOURCES
    ${CMAKE_CURRENT_LIST_DIR}/src/tc_viewport.c
    ${CMAKE_CURRENT_LIST_DIR}/src/tc_display.c
    ${CMAKE_CURRENT_LIST_DIR}/src/tc_input_manager.c
    ${CMAKE_CURRENT_LIST_DIR}/src/tc_display_input_router.c
    ${CMAKE_CURRENT_LIST_DIR}/src/tc_viewport_input_manager.c
    ${CMAKE_CURRENT_LIST_DIR}/src/tc_render_surface.c
)

if(TERMIN_DISPLAY_BUILD_SHARED)
    add_library(termin_display SHARED ${TERMIN_DISPLAY_SOURCES})
    target_compile_definitions(termin_display PRIVATE TERMIN_DISPLAY_EXPORTS)
else()
    add_library(termin_display STATIC ${TERMIN_DISPLAY_SOURCES})
endif()

add_library(termin_display::termin_display ALIAS termin_display)

set_target_properties(termin_display PROPERTIES
    POSITION_INDEPENDENT_CODE ON
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
)
termin_set_rpath_lib(termin_display)

target_include_directories(termin_display
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_LIST_DIR}/include>
        $<BUILD_INTERFACE:${CMAKE_CURRENT_LIST_DIR}/../termin/core_c/include>
        $<BUILD_INTERFACE:${CMAKE_CURRENT_LIST_DIR}/../termin-render/include>
        $<INSTALL_INTERFACE:include>
    PRIVATE
        ${CMAKE_CURRENT_LIST_DIR}/include
        ${CMAKE_CURRENT_LIST_DIR}/../termin/core_c/include
        ${CMAKE_CURRENT_LIST_DIR}/../termin-render/include
)

target_link_libraries(termin_display
    PUBLIC
        tcbase::termin_base
        tgfx::termin_graphics
        termin_scene::termin_scene
        termin_input::termin_input
        termin_render::termin_render
)

if(UNIX AND NOT APPLE)
    target_link_libraries(termin_display PRIVATE m)
endif()

if(MSVC)
    target_compile_options(termin_display PRIVATE /W3 /wd4251 /wd4275)
    target_compile_definitions(termin_display PRIVATE _CRT_SECURE_NO_WARNINGS)
else()
    target_compile_options(termin_display PRIVATE -Wall -Wextra -Wno-stringop-truncation)
endif()

if(TERMIN_BUILD_PYTHON)
    find_package(Python 3.8 COMPONENTS Interpreter Development REQUIRED)
    find_package(nanobind CONFIG REQUIRED)

    nanobind_add_module(_display_native NB_SHARED
        python/display_module.cpp
        bindings/render/tc_display_bindings.cpp
        bindings/render/tc_input_manager_bindings.cpp
        bindings/render/tc_render_surface_bindings.cpp
        bindings/input/display_input_router_bindings.cpp
    )
    target_link_libraries(_display_native PRIVATE termin_display)
    target_include_directories(_display_native PRIVATE
        ${CMAKE_CURRENT_LIST_DIR}/include
        ${CMAKE_CURRENT_LIST_DIR}/../termin/core_c/include
        ${CMAKE_CURRENT_LIST_DIR}/../termin-render/include
    )
    termin_set_rpath_python(_display_native)
    install(TARGETS _display_native DESTINATION lib/python/termin/display)

    nanobind_add_module(_viewport_native NB_SHARED
        bindings/viewport/viewport_module.cpp
    )
    target_link_libraries(_viewport_native PRIVATE termin_display termin_scene::termin_scene)
    target_include_directories(_viewport_native PRIVATE
        ${CMAKE_CURRENT_LIST_DIR}/include
        ${CMAKE_CURRENT_LIST_DIR}/../termin/core_c/include
        ${CMAKE_CURRENT_LIST_DIR}/../termin-render/include
    )
    termin_set_rpath_python(_viewport_native)
    install(TARGETS _viewport_native DESTINATION lib/python/termin/viewport)
endif()

install(TARGETS termin_display
    EXPORT termin_displayTargets
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
    RUNTIME DESTINATION bin
)

install(FILES
    ${CMAKE_CURRENT_LIST_DIR}/include/render/termin_display_api.h
    ${CMAKE_CURRENT_LIST_DIR}/include/render/tc_viewport.h
    ${CMAKE_CURRENT_LIST_DIR}/include/render/tc_viewport_pool.h
    ${CMAKE_CURRENT_LIST_DIR}/include/render/tc_display.h
    ${CMAKE_CURRENT_LIST_DIR}/include/render/tc_input_manager.h
    ${CMAKE_CURRENT_LIST_DIR}/include/render/tc_display_input_router.h
    ${CMAKE_CURRENT_LIST_DIR}/include/render/tc_viewport_input_manager.h
    ${CMAKE_CURRENT_LIST_DIR}/include/render/tc_render_surface.h
    DESTINATION include/render
)

install(FILES
    ${CMAKE_CURRENT_LIST_DIR}/include/termin/viewport/tc_viewport_handle.hpp
    DESTINATION include/termin/viewport
)

install(FILES
    ${CMAKE_CURRENT_LIST_DIR}/include/termin/render/tc_display_handle.hpp
    DESTINATION include/termin/render
)

install(FILES
    ${CMAKE_CURRENT_LIST_DIR}/include/termin/input/display_input_router.hpp
    DESTINATION include/termin/input
)

install(EXPORT termin_displayTargets
    FILE termin_displayTargets.cmake
    NAMESPACE termin_display::
    DESTINATION lib/cmake/termin_display
)

include(CMakePackageConfigHelpers)

configure_package_config_file(
    ${CMAKE_CURRENT_LIST_DIR}/cmake/termin_displayConfig.cmake.in
    ${CMAKE_CURRENT_BINARY_DIR}/termin_displayConfig.cmake
    INSTALL_DESTINATION lib/cmake/termin_display
)

write_basic_package_version_file(
    ${CMAKE_CURRENT_BINARY_DIR}/termin_displayConfigVersion.cmake
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMajorVersion
)

install(FILES
    ${CMAKE_CURRENT_BINARY_DIR}/termin_displayConfig.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/termin_displayConfigVersion.cmake
    DESTINATION lib/cmake/termin_display
)
