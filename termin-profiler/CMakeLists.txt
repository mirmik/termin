cmake_minimum_required(VERSION 3.20)
project(termin_profiler_app VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_LIST_DIR}/../cmake")
include(TerminRpath)
include(TerminTestMetadata)
include(GNUInstallDirs)

if(COMMAND termin_require_package)
    termin_require_package(termin_base tcbase::termin_base)
    termin_require_package(termin_frame_profiler termin_frame_profiler::termin_frame_profiler)
    termin_require_package(termin_gui_native termin_gui_native::window_adapter)
    termin_require_package(termin_graphics tgfx::termin_graphics2)
else()
    find_package(termin_base CONFIG REQUIRED)
    find_package(termin_frame_profiler CONFIG REQUIRED)
    find_package(termin_gui_native CONFIG REQUIRED COMPONENTS window_adapter)
    find_package(termin_graphics CONFIG REQUIRED)
endif()

add_library(termin_profiler_app_support STATIC
    src/android_bridge.cpp
    src/capture_export.cpp
    src/cli.cpp
    src/session.cpp
)
target_include_directories(termin_profiler_app_support PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_LIST_DIR}/include>
)
target_link_libraries(termin_profiler_app_support PUBLIC
    termin_frame_profiler::termin_frame_profiler
    tcbase::termin_base
)

add_executable(termin_profiler src/main.cpp)
target_link_libraries(termin_profiler PRIVATE
    termin_profiler_app_support
    termin_gui_native::window_adapter
    tgfx::termin_graphics2
)
termin_set_rpath_tool(termin_profiler)

add_executable(termin_profiler_cli src/cli_main.cpp)
target_link_libraries(termin_profiler_cli PRIVATE termin_profiler_app_support)
termin_set_rpath_tool(termin_profiler_cli)

install(TARGETS termin_profiler termin_profiler_cli RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})
install(FILES README.md DESTINATION ${CMAKE_INSTALL_DATADIR}/doc/termin-profiler)

if(TERMIN_BUILD_TESTS)
    add_executable(termin_profiler_session_test tests/test_session.cpp)
    target_include_directories(termin_profiler_session_test PRIVATE
        ${CMAKE_CURRENT_LIST_DIR}/../termin-thirdparty/guard
    )
    target_link_libraries(termin_profiler_session_test PRIVATE termin_profiler_app_support)
    termin_set_rpath_test(termin_profiler_session_test)
    add_test(NAME termin_profiler_session_test COMMAND termin_profiler_session_test)

    add_executable(termin_profiler_android_bridge_test tests/test_android_bridge.cpp)
    target_include_directories(termin_profiler_android_bridge_test PRIVATE
        ${CMAKE_CURRENT_LIST_DIR}/../termin-thirdparty/guard
    )
    target_link_libraries(termin_profiler_android_bridge_test PRIVATE termin_profiler_app_support)
    termin_set_rpath_test(termin_profiler_android_bridge_test)
    add_test(NAME termin_profiler_android_bridge_test COMMAND termin_profiler_android_bridge_test)

    add_executable(termin_profiler_cli_test tests/test_cli.cpp)
    target_include_directories(termin_profiler_cli_test PRIVATE
        ${CMAKE_CURRENT_LIST_DIR}/../termin-thirdparty/guard
    )
    target_link_libraries(termin_profiler_cli_test PRIVATE termin_profiler_app_support)
    termin_set_rpath_test(termin_profiler_cli_test)
    add_test(NAME termin_profiler_cli_test COMMAND termin_profiler_cli_test)

    add_test(NAME termin_profiler_window_smoke COMMAND termin_profiler)
    set_tests_properties(termin_profiler_window_smoke PROPERTIES
        ENVIRONMENT "TERMIN_PROFILER_RENDER_COUNT=2"
        SKIP_RETURN_CODE 77
    )
    termin_add_test_labels(termin_profiler_window_smoke "termin:capability:window")
    termin_set_test_build_target(termin_profiler_window_smoke termin_profiler)

    termin_label_tests_in_directory("termin-profiler")
endif()
