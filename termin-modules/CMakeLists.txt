cmake_minimum_required(VERSION 3.16)
project(termin_modules LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include(cmake/TerminModule.cmake)

find_package(Python COMPONENTS Interpreter Development REQUIRED)
find_package(nanobind CONFIG REQUIRED)
find_package(termin_base REQUIRED)

add_library(termin_modules STATIC
    src/module_cpp_backend.cpp
    src/module_descriptor_parser.cpp
    src/module_python_backend.cpp
    src/module_runtime.cpp
)

target_compile_features(termin_modules PUBLIC cxx_std_20)
set_target_properties(termin_modules PROPERTIES POSITION_INDEPENDENT_CODE ON)

target_include_directories(termin_modules
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include>
)

target_link_libraries(termin_modules
    PUBLIC
        tcbase::termin_base
        Python::Python
        ${CMAKE_DL_LIBS}
)

nanobind_add_module(_termin_modules_native NB_SHARED
    python/bindings/termin_modules_module.cpp
)

target_link_libraries(_termin_modules_native PRIVATE termin_modules)

file(MAKE_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/python/termin_modules)
configure_file(
    ${CMAKE_CURRENT_SOURCE_DIR}/python/termin_modules/__init__.py
    ${CMAKE_CURRENT_BINARY_DIR}/python/termin_modules/__init__.py
    COPYONLY
)

add_executable(termin_modules_example
    examples/basic/main.cpp
)

target_link_libraries(termin_modules_example PRIVATE termin_modules)
target_compile_definitions(termin_modules_example PRIVATE
    TERMIN_MODULES_EXAMPLE_PROJECT_DIR="${CMAKE_CURRENT_SOURCE_DIR}/examples/basic/project"
)
