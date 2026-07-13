cmake_minimum_required(VERSION 3.20)

project(termin_cpp_class_layout LANGUAGES C CXX)

set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

find_package(LLVM REQUIRED CONFIG)
find_package(Clang REQUIRED CONFIG)

if(NOT LLVM_VERSION_MAJOR EQUAL 18)
    message(FATAL_ERROR
        "termin-cpp-class-layout currently requires LLVM/Clang 18; "
        "found ${LLVM_PACKAGE_VERSION}")
endif()

add_executable(termin-cpp-class-layout
    src/main.cpp
)

target_compile_features(termin-cpp-class-layout PRIVATE cxx_std_20)
target_include_directories(termin-cpp-class-layout SYSTEM PRIVATE
    ${LLVM_INCLUDE_DIRS}
    ${CLANG_INCLUDE_DIRS}
)
target_compile_definitions(termin-cpp-class-layout PRIVATE
    ${LLVM_DEFINITIONS}
)
if(MSVC)
    target_compile_options(termin-cpp-class-layout PRIVATE /W4 /WX)
else()
    target_compile_options(termin-cpp-class-layout PRIVATE
        -Wall
        -Wextra
        -Wpedantic
        -Werror
    )
endif()
target_link_libraries(termin-cpp-class-layout PRIVATE
    clang-cpp
    LLVM
)

include(CTest)
if(BUILD_TESTING)
    find_package(Python3 REQUIRED COMPONENTS Interpreter)
    find_program(TERMIN_CLANGXX_EXECUTABLE NAMES clang++-18 clang++ REQUIRED)

    add_test(
        NAME termin-cpp-class-layout-fixtures
        COMMAND
            ${Python3_EXECUTABLE}
            ${CMAKE_CURRENT_SOURCE_DIR}/tests/run_fixture_tests.py
            $<TARGET_FILE:termin-cpp-class-layout>
            ${TERMIN_CLANGXX_EXECUTABLE}
            ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures
    )

    add_test(
        NAME termin-cpp-class-layout-self-check
        COMMAND
            $<TARGET_FILE:termin-cpp-class-layout>
            -p ${CMAKE_CURRENT_BINARY_DIR}
            --repo-root ${CMAKE_CURRENT_SOURCE_DIR}/../..
            --path tools/cpp-class-layout
    )
endif()
