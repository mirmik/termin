cmake_minimum_required(VERSION 3.20)
project(termin_avalonia_positioner_probe LANGUAGES CXX)

find_package(termin_display CONFIG REQUIRED)

add_library(termin_avalonia_positioner_probe SHARED positioner_probe.cpp)
target_compile_features(termin_avalonia_positioner_probe PRIVATE cxx_std_20)
target_link_libraries(termin_avalonia_positioner_probe PRIVATE
    termin_display::termin_display
    tgfx::termin_graphics2
    tcbase::termin_base
)
set_target_properties(termin_avalonia_positioner_probe PROPERTIES
    CXX_VISIBILITY_PRESET hidden
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/$<CONFIG>"
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/$<CONFIG>"
)
