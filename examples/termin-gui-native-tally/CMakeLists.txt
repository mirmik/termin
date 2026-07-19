cmake_minimum_required(VERSION 3.20)

project(termin_gui_native_tally VERSION 0.1.0 LANGUAGES CXX)

find_package(termin_gui_native CONFIG REQUIRED)
find_package(termin_window CONFIG REQUIRED)

if(NOT termin_window_HAS_SDL)
    message(FATAL_ERROR "termin-gui-native tally requires an SDK built with SDL support")
endif()

get_filename_component(TERMIN_TALLY_SDK_HINT
    "${termin_gui_native_DIR}/../../.."
    ABSOLUTE
)
find_program(TERMIN_TALLY_SLANGC_HINT NAMES slangc)

add_executable(termin_tally
    src/main.cpp
)
target_compile_features(termin_tally PRIVATE cxx_std_20)
target_link_libraries(termin_tally
    PRIVATE
        termin_gui_native::termin_gui_native
        termin_window::termin_window
)
target_compile_definitions(termin_tally
    PRIVATE
        TERMIN_TALLY_SDK_HINT="${TERMIN_TALLY_SDK_HINT}"
)
if(TERMIN_TALLY_SLANGC_HINT)
    target_compile_definitions(termin_tally
        PRIVATE TERMIN_TALLY_SLANGC_HINT="${TERMIN_TALLY_SLANGC_HINT}"
    )
endif()

if(MSVC)
    target_compile_options(termin_tally PRIVATE /W4 /permissive-)
else()
    target_compile_options(termin_tally PRIVATE -Wall -Wextra -Wpedantic)
endif()

if(WIN32)
    add_custom_command(TARGET termin_tally POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy_if_different
            $<TARGET_RUNTIME_DLLS:termin_tally>
            $<TARGET_FILE_DIR:termin_tally>
        COMMAND_EXPAND_LISTS
    )
else()
    set_target_properties(termin_tally PROPERTIES
        BUILD_RPATH_USE_ORIGIN TRUE
    )
endif()

include(CTest)
if(BUILD_TESTING)
    add_test(NAME termin_tally_smoke COMMAND termin_tally --frames 2)
    set_tests_properties(termin_tally_smoke PROPERTIES SKIP_RETURN_CODE 77)
endif()
