cmake_minimum_required(VERSION 3.14)
project(termin_openxr VERSION 0.1.0 LANGUAGES C CXX)

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
    termin_require_package(termin_scene termin_scene::termin_scene)
else()
    find_package(termin_scene REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_mesh tmesh::termin_mesh)
else()
    find_package(termin_mesh REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_components_mesh termin_components_mesh::termin_components_mesh)
else()
    find_package(termin_components_mesh REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_inspect termin_inspect::termin_inspect)
else()
    find_package(termin_inspect REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_components_render termin_components_render::termin_components_render)
else()
    find_package(termin_components_render REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_graphics tgfx::termin_graphics2)
else()
    find_package(termin_graphics REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_render termin_render::termin_render)
else()
    find_package(termin_render REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_render_passes termin_render_passes::termin_render_passes)
else()
    find_package(termin_render_passes REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_engine termin_engine::termin_engine)
else()
    find_package(termin_engine REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_runtime termin_runtime::termin_runtime)
else()
    find_package(termin_runtime REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_collision termin_collision::termin_collision)
else()
    find_package(termin_collision REQUIRED)
endif()

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_LIST_DIR}/../cmake")
include(TerminRpath)

set(TERMIN_OPENXR_SDK_ROOT "" CACHE PATH "Path to an OpenXR SDK checkout/root containing include/openxr/openxr.h")
set(TERMIN_OPENXR_DEFAULT_SDK_ROOT "${CMAKE_CURRENT_LIST_DIR}/../termin-thirdparty/openxr-sdk")
if(NOT TERMIN_OPENXR_SDK_ROOT AND EXISTS "${TERMIN_OPENXR_DEFAULT_SDK_ROOT}/include/openxr/openxr.h")
    set(TERMIN_OPENXR_SDK_ROOT "${TERMIN_OPENXR_DEFAULT_SDK_ROOT}" CACHE PATH "Path to an OpenXR SDK checkout/root containing include/openxr/openxr.h" FORCE)
endif()

find_path(TERMIN_OPENXR_INCLUDE_DIR
    NAMES openxr/openxr.h openxr/openxr_platform.h
    HINTS
        "${TERMIN_OPENXR_SDK_ROOT}/include"
        "${TERMIN_OPENXR_SDK_ROOT}"
    NO_CMAKE_FIND_ROOT_PATH
)

set(TERMIN_OPENXR_HAS_HEADERS OFF)
if(TERMIN_OPENXR_INCLUDE_DIR)
    set(TERMIN_OPENXR_HAS_HEADERS ON)
    message(STATUS "termin-openxr: OpenXR headers found: ${TERMIN_OPENXR_INCLUDE_DIR}")
else()
    message(STATUS "termin-openxr: OpenXR headers not found; building placeholder without OpenXR headers")
endif()

set(TERMIN_OPENXR_SOURCES
    src/openxr_runtime.cpp
)

set(TERMIN_OPENXR_HEADERS
    include/termin/openxr/openxr_runtime.hpp
    include/termin/openxr/termin_openxr_api.h
)

add_library(termin_openxr SHARED ${TERMIN_OPENXR_SOURCES} ${TERMIN_OPENXR_HEADERS})
add_library(termin_openxr::termin_openxr ALIAS termin_openxr)

set_target_properties(termin_openxr PROPERTIES
    POSITION_INDEPENDENT_CODE ON
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    WINDOWS_EXPORT_ALL_SYMBOLS ON
)
termin_set_rpath_lib(termin_openxr)

target_include_directories(termin_openxr
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_LIST_DIR}/include>
        $<INSTALL_INTERFACE:include>
)

if(TERMIN_OPENXR_HAS_HEADERS)
    target_include_directories(termin_openxr PRIVATE "${TERMIN_OPENXR_INCLUDE_DIR}")
    target_compile_definitions(termin_openxr PRIVATE TERMIN_OPENXR_HAS_HEADERS)
endif()

target_compile_definitions(termin_openxr PRIVATE TERMIN_OPENXR_EXPORTS)
if(ANDROID)
    target_compile_definitions(termin_openxr PRIVATE TGFX2_HAS_VULKAN)
endif()
target_compile_features(termin_openxr PUBLIC cxx_std_20)

target_link_libraries(termin_openxr
    PUBLIC
        tcbase::termin_base
        termin_scene::termin_scene
        tmesh::termin_mesh
        termin_components_mesh::termin_components_mesh
        termin_inspect::termin_inspect
        termin_components_render::termin_components_render
        tgfx::termin_graphics2
        termin_render::termin_render
        termin_render_passes::termin_render_passes
        termin_engine::termin_engine
        termin_runtime::termin_runtime
        termin_collision::termin_collision
)

if(ANDROID)
    find_library(ANDROID_LOG_LIB log REQUIRED)
    find_library(ANDROID_NATIVE_LIB android REQUIRED)
    find_library(ANDROID_VULKAN_LIB vulkan REQUIRED)
    target_link_libraries(termin_openxr PRIVATE
        ${ANDROID_LOG_LIB}
        ${ANDROID_NATIVE_LIB}
        ${ANDROID_VULKAN_LIB}
    )
endif()

if(MSVC)
    target_compile_options(termin_openxr PRIVATE /W3 /wd4251 /wd4275)
else()
    target_compile_options(termin_openxr PRIVATE -Wall -Wextra)
endif()

install(TARGETS termin_openxr
    EXPORT termin_openxrTargets
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
    RUNTIME DESTINATION bin
)

install(DIRECTORY include/
    DESTINATION include
)

install(EXPORT termin_openxrTargets
    FILE termin_openxrTargets.cmake
    NAMESPACE termin_openxr::
    DESTINATION lib/cmake/termin_openxr
)

include(CMakePackageConfigHelpers)

configure_package_config_file(
    ${CMAKE_CURRENT_LIST_DIR}/cmake/termin_openxrConfig.cmake.in
    ${CMAKE_CURRENT_BINARY_DIR}/termin_openxrConfig.cmake
    INSTALL_DESTINATION lib/cmake/termin_openxr
)

write_basic_package_version_file(
    ${CMAKE_CURRENT_BINARY_DIR}/termin_openxrConfigVersion.cmake
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMajorVersion
)

install(FILES
    ${CMAKE_CURRENT_BINARY_DIR}/termin_openxrConfig.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/termin_openxrConfigVersion.cmake
    DESTINATION lib/cmake/termin_openxr
)
