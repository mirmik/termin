cmake_minimum_required(VERSION 3.16)
project(cpp_demo LANGUAGES CXX)

add_library(cpp_demo SHARED module.cpp)
target_compile_features(cpp_demo PRIVATE cxx_std_17)
set_target_properties(cpp_demo PROPERTIES
    PREFIX "lib"
    OUTPUT_NAME "cpp_demo"
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}"
)
