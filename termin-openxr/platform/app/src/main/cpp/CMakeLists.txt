cmake_minimum_required(VERSION 3.22)
project(termin_openxr_smoke_jni LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if(NOT DEFINED TERMIN_ANDROID_SDK_ROOT)
    message(FATAL_ERROR "TERMIN_ANDROID_SDK_ROOT is required")
endif()

if(NOT DEFINED TERMIN_ANDROID_ABI)
    set(TERMIN_ANDROID_ABI "${ANDROID_ABI}")
endif()

set(TERMIN_ANDROID_SDK_PREFIX "${TERMIN_ANDROID_SDK_ROOT}/${TERMIN_ANDROID_ABI}")
if(NOT EXISTS "${TERMIN_ANDROID_SDK_PREFIX}/lib/cmake/termin_openxr/termin_openxrConfig.cmake")
    message(FATAL_ERROR
        "termin_openxrConfig.cmake not found under ${TERMIN_ANDROID_SDK_PREFIX}. "
        "Run build-sdk-android.sh first or pass -DTERMIN_ANDROID_SDK_ROOT.")
endif()

list(APPEND CMAKE_PREFIX_PATH "${TERMIN_ANDROID_SDK_PREFIX}")
file(GLOB TERMIN_ANDROID_CMAKE_PACKAGE_DIRS
    LIST_DIRECTORIES true
    "${TERMIN_ANDROID_SDK_PREFIX}/lib/cmake/termin_*"
)
foreach(TERMIN_ANDROID_CMAKE_PACKAGE_DIR IN LISTS TERMIN_ANDROID_CMAKE_PACKAGE_DIRS)
    get_filename_component(TERMIN_ANDROID_CMAKE_PACKAGE "${TERMIN_ANDROID_CMAKE_PACKAGE_DIR}" NAME)
    set("${TERMIN_ANDROID_CMAKE_PACKAGE}_DIR" "${TERMIN_ANDROID_CMAKE_PACKAGE_DIR}")
endforeach()

find_package(termin_scene REQUIRED CONFIG NO_DEFAULT_PATH NO_CMAKE_FIND_ROOT_PATH)
find_package(termin_mesh REQUIRED CONFIG NO_DEFAULT_PATH NO_CMAKE_FIND_ROOT_PATH)
find_package(termin_components_mesh REQUIRED CONFIG NO_DEFAULT_PATH NO_CMAKE_FIND_ROOT_PATH)
find_package(termin_inspect REQUIRED CONFIG NO_DEFAULT_PATH NO_CMAKE_FIND_ROOT_PATH)
find_package(termin_components_render REQUIRED CONFIG NO_DEFAULT_PATH NO_CMAKE_FIND_ROOT_PATH)
find_package(termin_graphics REQUIRED CONFIG NO_DEFAULT_PATH NO_CMAKE_FIND_ROOT_PATH)
find_package(termin_render REQUIRED CONFIG NO_DEFAULT_PATH NO_CMAKE_FIND_ROOT_PATH)
find_package(termin_render_passes REQUIRED CONFIG NO_DEFAULT_PATH NO_CMAKE_FIND_ROOT_PATH)
find_package(termin_engine REQUIRED CONFIG NO_DEFAULT_PATH NO_CMAKE_FIND_ROOT_PATH)
find_package(termin_runtime REQUIRED CONFIG NO_DEFAULT_PATH NO_CMAKE_FIND_ROOT_PATH)
find_package(termin_collision REQUIRED CONFIG NO_DEFAULT_PATH NO_CMAKE_FIND_ROOT_PATH)
find_package(termin_openxr REQUIRED CONFIG NO_DEFAULT_PATH NO_CMAKE_FIND_ROOT_PATH)

set(TERMIN_OPENXR_SDK_ROOT
    "${CMAKE_CURRENT_LIST_DIR}/../../../../../../termin-thirdparty/openxr-sdk"
)
if(EXISTS "${TERMIN_OPENXR_SDK_ROOT}/CMakeLists.txt")
    set(BUILD_LOADER ON CACHE BOOL "" FORCE)
    set(DYNAMIC_LOADER ON CACHE BOOL "" FORCE)
    set(BUILD_API_LAYERS OFF CACHE BOOL "" FORCE)
    set(BUILD_TESTS OFF CACHE BOOL "" FORCE)
    set(BUILD_CONFORMANCE_TESTS OFF CACHE BOOL "" FORCE)
    set(BUILD_SDK_TESTS OFF CACHE BOOL "" FORCE)
    set(BUILD_WITH_SYSTEM_JSONCPP OFF CACHE BOOL "" FORCE)
    add_subdirectory(
        "${TERMIN_OPENXR_SDK_ROOT}"
        "${CMAKE_BINARY_DIR}/openxr-sdk"
        EXCLUDE_FROM_ALL
    )
else()
    message(WARNING "OpenXR SDK submodule not found at ${TERMIN_OPENXR_SDK_ROOT}; relying on a system loader")
endif()

find_library(ANDROID_LOG_LIB log REQUIRED)

find_library(ANDROID_NATIVE_LIB android REQUIRED)

add_library(termin_openxr_native_activity SHARED termin_openxr_native_activity.cpp)
target_link_libraries(termin_openxr_native_activity
    PRIVATE
        termin_openxr::termin_openxr
        ${ANDROID_LOG_LIB}
        ${ANDROID_NATIVE_LIB}
)
if(TARGET OpenXR::openxr_loader)
    target_link_libraries(termin_openxr_native_activity PRIVATE OpenXR::openxr_loader)
endif()
target_compile_options(termin_openxr_native_activity PRIVATE -Wall -Wextra)
