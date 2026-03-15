cmake_minimum_required(VERSION 3.14)
project(termin_engine VERSION 0.1.0 LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

option(TERMIN_ENGINE_BUILD_SHARED "Build shared library" ON)
option(TERMIN_BUILD_PYTHON "Build Python bindings for termin-engine" OFF)

find_package(termin_base REQUIRED)
find_package(termin_graphics REQUIRED)
find_package(termin_scene REQUIRED)
find_package(termin_render REQUIRED)
find_package(termin_display REQUIRED)
find_package(termin_input REQUIRED)
find_package(termin_collision REQUIRED)
find_package(termin_components_render REQUIRED)

set(TERMIN_ENGINE_SOURCES
    src/engine_core.cpp
    src/scene_manager.cpp
    src/rendering_manager.cpp
    src/pull_rendering_manager.cpp
    ${CMAKE_CURRENT_LIST_DIR}/../termin/core_c/src/tc_scene_manager_instance.cpp
    ${CMAKE_CURRENT_LIST_DIR}/../termin/core_c/src/tc_rendering_manager_instance.cpp
    ${CMAKE_CURRENT_LIST_DIR}/../termin/core_c/src/tc_engine_core_instance.cpp
)

if(TERMIN_ENGINE_BUILD_SHARED)
    add_library(termin_engine SHARED ${TERMIN_ENGINE_SOURCES})
    target_compile_definitions(termin_engine PRIVATE TERMIN_ENGINE_EXPORTS)
else()
    add_library(termin_engine STATIC ${TERMIN_ENGINE_SOURCES})
endif()

add_library(termin_engine::termin_engine ALIAS termin_engine)

set_target_properties(termin_engine PROPERTIES
    POSITION_INDEPENDENT_CODE ON
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    INSTALL_RPATH "$ORIGIN:${CMAKE_INSTALL_PREFIX}/lib"
    BUILD_WITH_INSTALL_RPATH TRUE
)

target_include_directories(termin_engine
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_LIST_DIR}/include>
        $<BUILD_INTERFACE:${CMAKE_CURRENT_LIST_DIR}/../termin/core_c/include>
        $<INSTALL_INTERFACE:include>
    PRIVATE
        ${CMAKE_CURRENT_LIST_DIR}/include
        ${CMAKE_CURRENT_LIST_DIR}/../termin/core_c/include
)

target_link_libraries(termin_engine
    PUBLIC
        tcbase::termin_base
        tgfx::termin_graphics
        termin_scene::termin_scene
        termin_render::termin_render
        termin_display::termin_display
        termin_input::termin_input
        termin_collision::termin_collision
        termin_components_render::termin_components_render
)

if(UNIX AND NOT APPLE)
    target_link_libraries(termin_engine PRIVATE m)
endif()

if(MSVC)
    target_compile_options(termin_engine PRIVATE /W3)
else()
    target_compile_options(termin_engine PRIVATE -Wall -Wextra)
endif()

if(TERMIN_BUILD_PYTHON)
    find_package(Python 3.8 COMPONENTS Interpreter Development REQUIRED)
    find_package(nanobind CONFIG REQUIRED)

    nanobind_add_module(_engine_native NB_SHARED
        python/engine_module.cpp
        bindings/engine_core_bindings.cpp
        bindings/scene_manager_bindings.cpp
        bindings/rendering_manager_bindings.cpp
    )
    target_link_libraries(_engine_native PRIVATE termin_engine)
    target_include_directories(_engine_native PRIVATE
        ${CMAKE_CURRENT_LIST_DIR}/include
        ${CMAKE_CURRENT_LIST_DIR}/../termin/core_c/include
    )
    set_target_properties(_engine_native PROPERTIES
        INSTALL_RPATH "$ORIGIN;$ORIGIN/..;$ORIGIN/../..;$ORIGIN/../../..;${CMAKE_INSTALL_PREFIX}/lib"
        BUILD_WITH_INSTALL_RPATH TRUE
    )
    install(TARGETS _engine_native DESTINATION lib/python/termin/engine)
endif()

install(TARGETS termin_engine
    EXPORT termin_engineTargets
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
    RUNTIME DESTINATION bin
)

install(DIRECTORY include/
    DESTINATION include
)

install(EXPORT termin_engineTargets
    FILE termin_engineTargets.cmake
    NAMESPACE termin_engine::
    DESTINATION lib/cmake/termin_engine
)

include(CMakePackageConfigHelpers)

configure_package_config_file(
    ${CMAKE_CURRENT_LIST_DIR}/cmake/termin_engineConfig.cmake.in
    ${CMAKE_CURRENT_BINARY_DIR}/termin_engineConfig.cmake
    INSTALL_DESTINATION lib/cmake/termin_engine
)

write_basic_package_version_file(
    ${CMAKE_CURRENT_BINARY_DIR}/termin_engineConfigVersion.cmake
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMajorVersion
)

install(FILES
    ${CMAKE_CURRENT_BINARY_DIR}/termin_engineConfig.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/termin_engineConfigVersion.cmake
    DESTINATION lib/cmake/termin_engine
)
