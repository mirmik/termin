cmake_minimum_required(VERSION 3.14)
project(termin_runtime VERSION 0.1.0 LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if(COMMAND termin_require_package)
    termin_require_package(termin_base tcbase::termin_base)
else()
    find_package(termin_base REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_graphics tgfx::termin_graphics tgfx::termin_graphics2)
else()
    find_package(termin_graphics REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_mesh tmesh::termin_mesh)
else()
    find_package(termin_mesh REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_scene termin_scene::termin_scene)
else()
    find_package(termin_scene REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_render termin_render::termin_render)
else()
    find_package(termin_render REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_engine termin_engine::termin_engine)
else()
    find_package(termin_engine REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_components_mesh termin_components_mesh::termin_components_mesh)
else()
    find_package(termin_components_mesh REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_components_render termin_components_render::termin_components_render)
else()
    find_package(termin_components_render REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_components_foliage termin_components_foliage::termin_components_foliage)
else()
    find_package(termin_components_foliage REQUIRED)
endif()

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_LIST_DIR}/../cmake")
include(TerminRpath)

add_library(termin_runtime SHARED
    src/runtime_package.cpp
)
add_library(termin_runtime::termin_runtime ALIAS termin_runtime)

set_target_properties(termin_runtime PROPERTIES
    POSITION_INDEPENDENT_CODE ON
    WINDOWS_EXPORT_ALL_SYMBOLS OFF
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
)
termin_set_rpath_lib(termin_runtime)

target_compile_definitions(termin_runtime PRIVATE TERMIN_RUNTIME_EXPORTS)

target_include_directories(termin_runtime
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_LIST_DIR}/include>
        $<INSTALL_INTERFACE:include>
)

target_link_libraries(termin_runtime
    PUBLIC
        tcbase::termin_base
        tgfx::termin_graphics
        tgfx::termin_graphics2
        tmesh::termin_mesh
        termin_scene::termin_scene
        termin_render::termin_render
        termin_engine::termin_engine
        termin_components_mesh::termin_components_mesh
        termin_components_render::termin_components_render
        termin_components_foliage::termin_components_foliage
)

if(MSVC)
    target_compile_options(termin_runtime PRIVATE /W3 /wd4251 /wd4275)
else()
    target_compile_options(termin_runtime PRIVATE -Wall -Wextra)
endif()

install(TARGETS termin_runtime
    EXPORT termin_runtimeTargets
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
    RUNTIME DESTINATION bin
)

install(DIRECTORY include/
    DESTINATION include
)

install(EXPORT termin_runtimeTargets
    FILE termin_runtimeTargets.cmake
    NAMESPACE termin_runtime::
    DESTINATION lib/cmake/termin_runtime
)

include(CMakePackageConfigHelpers)

configure_package_config_file(
    ${CMAKE_CURRENT_LIST_DIR}/cmake/termin_runtimeConfig.cmake.in
    ${CMAKE_CURRENT_BINARY_DIR}/termin_runtimeConfig.cmake
    INSTALL_DESTINATION lib/cmake/termin_runtime
)

write_basic_package_version_file(
    ${CMAKE_CURRENT_BINARY_DIR}/termin_runtimeConfigVersion.cmake
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMajorVersion
)

install(FILES
    ${CMAKE_CURRENT_BINARY_DIR}/termin_runtimeConfig.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/termin_runtimeConfigVersion.cmake
    DESTINATION lib/cmake/termin_runtime
)
