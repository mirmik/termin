cmake_minimum_required(VERSION 3.14)
project(termin_android VERSION 0.1.0 LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if(NOT ANDROID)
    message(STATUS "termin-android: skipped outside Android toolchain")
    return()
endif()

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

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_LIST_DIR}/../cmake")
include(TerminRpath)

set(TERMIN_ANDROID_SOURCES
    src/bootstrap.cpp
)

set(TERMIN_ANDROID_HEADERS
    include/termin/android/bootstrap.h
    include/termin/android/termin_android_api.h
)

add_library(termin_android SHARED ${TERMIN_ANDROID_SOURCES} ${TERMIN_ANDROID_HEADERS})
add_library(termin_android::termin_android ALIAS termin_android)

set_target_properties(termin_android PROPERTIES
    POSITION_INDEPENDENT_CODE ON
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    WINDOWS_EXPORT_ALL_SYMBOLS ON
)
termin_set_rpath_lib(termin_android)

target_compile_definitions(termin_android
    PRIVATE
        TERMIN_ANDROID_EXPORTS
        TGFX2_HAS_VULKAN
        VK_USE_PLATFORM_ANDROID_KHR
)

target_include_directories(termin_android
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_LIST_DIR}/include>
        $<INSTALL_INTERFACE:include>
)

target_compile_features(termin_android PUBLIC cxx_std_20)

find_library(ANDROID_LOG_LIB log REQUIRED)
find_library(ANDROID_NATIVE_LIB android REQUIRED)
find_library(ANDROID_VULKAN_LIB vulkan REQUIRED)

target_link_libraries(termin_android
    PUBLIC
        tcbase::termin_base
        tgfx::termin_graphics2
    PRIVATE
        ${ANDROID_LOG_LIB}
        ${ANDROID_NATIVE_LIB}
        ${ANDROID_VULKAN_LIB}
)

target_compile_options(termin_android PRIVATE -Wall -Wextra)

install(TARGETS termin_android
    EXPORT termin_androidTargets
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
    RUNTIME DESTINATION bin
)

install(DIRECTORY include/
    DESTINATION include
)

install(EXPORT termin_androidTargets
    FILE termin_androidTargets.cmake
    NAMESPACE termin_android::
    DESTINATION lib/cmake/termin_android
)

include(CMakePackageConfigHelpers)

configure_package_config_file(
    ${CMAKE_CURRENT_LIST_DIR}/cmake/termin_androidConfig.cmake.in
    ${CMAKE_CURRENT_BINARY_DIR}/termin_androidConfig.cmake
    INSTALL_DESTINATION lib/cmake/termin_android
)

write_basic_package_version_file(
    ${CMAKE_CURRENT_BINARY_DIR}/termin_androidConfigVersion.cmake
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMajorVersion
)

install(FILES
    ${CMAKE_CURRENT_BINARY_DIR}/termin_androidConfig.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/termin_androidConfigVersion.cmake
    DESTINATION lib/cmake/termin_android
)
