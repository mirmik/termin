cmake_minimum_required(VERSION 3.22)
project(termin_android_jni LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if(NOT DEFINED TERMIN_ANDROID_SDK_ROOT)
    message(FATAL_ERROR "TERMIN_ANDROID_SDK_ROOT is required")
endif()

if(NOT DEFINED TERMIN_ANDROID_ABI)
    set(TERMIN_ANDROID_ABI "${ANDROID_ABI}")
endif()

set(TERMIN_ANDROID_SDK_PREFIX "${TERMIN_ANDROID_SDK_ROOT}/${TERMIN_ANDROID_ABI}")
if(NOT EXISTS "${TERMIN_ANDROID_SDK_PREFIX}/lib/cmake/termin_android/termin_androidConfig.cmake")
    message(FATAL_ERROR
        "termin_androidConfig.cmake not found under ${TERMIN_ANDROID_SDK_PREFIX}. "
        "Run build-sdk-android.sh first or pass -DTERMIN_ANDROID_SDK_ROOT.")
endif()

list(APPEND CMAKE_PREFIX_PATH "${TERMIN_ANDROID_SDK_PREFIX}")
set(termin_base_DIR "${TERMIN_ANDROID_SDK_PREFIX}/lib/cmake/termin_base")
set(termin_mesh_DIR "${TERMIN_ANDROID_SDK_PREFIX}/lib/cmake/termin_mesh")
set(termin_graphics_DIR "${TERMIN_ANDROID_SDK_PREFIX}/lib/cmake/termin_graphics")
set(termin_android_DIR "${TERMIN_ANDROID_SDK_PREFIX}/lib/cmake/termin_android")

find_package(termin_android REQUIRED CONFIG NO_DEFAULT_PATH NO_CMAKE_FIND_ROOT_PATH)

find_library(ANDROID_LOG_LIB log REQUIRED)
find_library(ANDROID_NATIVE_LIB android REQUIRED)

add_library(termin_android_jni SHARED termin_android_jni.cpp)

target_link_libraries(termin_android_jni
    PRIVATE
        termin_android::termin_android
        ${ANDROID_LOG_LIB}
        ${ANDROID_NATIVE_LIB}
)

target_compile_options(termin_android_jni PRIVATE -Wall -Wextra)
