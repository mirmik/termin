cmake_minimum_required(VERSION 3.14)
project(termin_engine VERSION 0.1.0 LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

option(TERMIN_ENGINE_BUILD_SHARED "Build shared library" ON)
option(TERMIN_ENGINE_BUILD_TESTS "Build termin-engine tests" ON)
option(TERMIN_BUILD_PYTHON "Build Python bindings for termin-engine" OFF)

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
if(COMMAND termin_require_package)
    termin_require_package(termin_scene termin_scene::termin_scene)
else()
    find_package(termin_scene REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_render termin_render::termin_render)
else()
    find_package(termin_render REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_display termin_display::termin_display)
else()
    find_package(termin_display REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_input termin_input::termin_input)
else()
    find_package(termin_input REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_collision termin_collision::termin_collision)
else()
    find_package(termin_collision REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_modules termin_modules::termin_modules)
else()
    find_package(termin_modules REQUIRED)
endif()

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_LIST_DIR}/../cmake")
include(TerminRpath)

set(TERMIN_ENGINE_SOURCES
    src/display_presenter.cpp
    src/engine_core.cpp
    src/default_pipeline_factory.cpp
    src/render_display_registry.cpp
    src/render_frame_planner.cpp
    src/scene_manager.cpp
    src/scene_light_collector.cpp
    src/tc_scene_render_ext.cpp
    src/render_target_context_builder.cpp
    src/render_state_store.cpp
    src/rendering_manager.cpp
    src/render_attachment_context.cpp
    src/render_topology.cpp
    src/modules/term_modules_integration.cpp
    src/viewport_render_state.cpp
)

if(TERMIN_ENGINE_BUILD_SHARED)
    add_library(termin_engine SHARED ${TERMIN_ENGINE_SOURCES})
    target_compile_definitions(termin_engine PRIVATE TERMIN_ENGINE_EXPORTS TC_EXPORTS)
else()
    add_library(termin_engine STATIC ${TERMIN_ENGINE_SOURCES})
endif()

add_library(termin_engine::termin_engine ALIAS termin_engine)

if(COMMAND termin_enable_pch_for)
    termin_enable_pch_for(termin_engine)
endif()

set_target_properties(termin_engine PROPERTIES
    POSITION_INDEPENDENT_CODE ON
    WINDOWS_EXPORT_ALL_SYMBOLS OFF
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
)
termin_set_rpath_lib(termin_engine)

target_include_directories(termin_engine
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_LIST_DIR}/include>
        $<INSTALL_INTERFACE:include>
    PRIVATE
        ${CMAKE_CURRENT_LIST_DIR}/include
)

target_link_libraries(termin_engine
    PUBLIC
        tcbase::termin_base
        tgfx::termin_graphics
        termin_scene::termin_scene
        termin_render::termin_render
        termin_display::termin_display
        termin_input::termin_input
        termin_collision::termin_collision
        termin_modules::termin_modules
)

if(UNIX AND NOT APPLE)
    target_link_libraries(termin_engine PRIVATE m)
endif()

if(MSVC)
    target_compile_options(termin_engine PRIVATE /W3 /wd4251 /wd4275)
    target_compile_definitions(termin_engine PRIVATE _CRT_SECURE_NO_WARNINGS)
else()
    target_compile_options(termin_engine PRIVATE -Wall -Wextra)
endif()

if(TERMIN_BUILD_PYTHON)
    find_package(Python 3.8 COMPONENTS Interpreter Development REQUIRED)
    find_package(nanobind CONFIG REQUIRED)

    nanobind_add_module(_engine_native NB_SHARED
        python/engine_module.cpp
        bindings/engine_core_bindings.cpp
        bindings/scene_manager_bindings.cpp
        bindings/scene_render_ext_bindings.cpp
        bindings/rendering_manager_bindings.cpp
        bindings/term_modules_integration_bindings.cpp
    )
    target_link_libraries(_engine_native PRIVATE termin_engine)
    target_include_directories(_engine_native PRIVATE
        ${CMAKE_CURRENT_LIST_DIR}/include
    )
    termin_set_rpath_python(_engine_native)
    install(TARGETS _engine_native DESTINATION lib/python/termin/engine)
    install(DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/python/termin/engine/
        DESTINATION lib/python/termin/engine
        PATTERN "__pycache__" EXCLUDE
        PATTERN "*.pyc" EXCLUDE
        # Native modules are installed from their CMake targets above.  A
        # locally cached setuptools artifact in the source package must never
        # overwrite the freshly linked module in the install tree.
        PATTERN "*.so" EXCLUDE
        PATTERN "*.pyd" EXCLUDE
        PATTERN "*.dylib" EXCLUDE
    )
endif()

install(TARGETS termin_engine
    EXPORT termin_engineTargets
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
    RUNTIME DESTINATION bin
)

install(DIRECTORY include/
    DESTINATION include
)

install(EXPORT termin_engineTargets
    FILE termin_engineTargets.cmake
    NAMESPACE termin_engine::
    DESTINATION lib/cmake/termin_engine
)

include(CMakePackageConfigHelpers)

configure_package_config_file(
    ${CMAKE_CURRENT_LIST_DIR}/cmake/termin_engineConfig.cmake.in
    ${CMAKE_CURRENT_BINARY_DIR}/termin_engineConfig.cmake
    INSTALL_DESTINATION lib/cmake/termin_engine
)

write_basic_package_version_file(
    ${CMAKE_CURRENT_BINARY_DIR}/termin_engineConfigVersion.cmake
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMajorVersion
)

install(FILES
    ${CMAKE_CURRENT_BINARY_DIR}/termin_engineConfig.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/termin_engineConfigVersion.cmake
    DESTINATION lib/cmake/termin_engine
)

if(TERMIN_ENGINE_BUILD_TESTS)
    enable_testing()

    add_library(termin_engine_cpp_hot_reload_test_module SHARED
        tests/cpp_hot_reload_module.cpp
    )
    target_link_libraries(termin_engine_cpp_hot_reload_test_module
        PRIVATE
            termin_scene::termin_scene
            termin_inspect::termin_inspect
            termin_render::termin_render
            termin_modules::termin_modules
    )
    set_target_properties(termin_engine_cpp_hot_reload_test_module PROPERTIES
        LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
        RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
        ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    )
    termin_set_rpath_lib(termin_engine_cpp_hot_reload_test_module)

    add_executable(termin_engine_cpp_module_hot_reload_test
        tests/test_cpp_module_hot_reload.cpp
    )
    target_link_libraries(termin_engine_cpp_module_hot_reload_test
        PRIVATE
            termin_engine
            termin_modules::termin_modules
            termin_scene::termin_scene
            termin_inspect::termin_inspect
            termin_render::termin_render
    )
    target_compile_definitions(termin_engine_cpp_module_hot_reload_test PRIVATE
        TERMIN_ENGINE_CPP_HOT_RELOAD_TEST_MODULE="$<TARGET_FILE:termin_engine_cpp_hot_reload_test_module>"
    )
    set_target_properties(termin_engine_cpp_module_hot_reload_test PROPERTIES
        RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    )
    add_dependencies(termin_engine_cpp_module_hot_reload_test termin_engine_cpp_hot_reload_test_module)

    add_test(
        NAME termin_engine_cpp_module_hot_reload_test
        COMMAND termin_engine_cpp_module_hot_reload_test
    )

    add_executable(termin_engine_render_topology_test
        tests/test_render_topology.cpp
    )
    target_link_libraries(termin_engine_render_topology_test PRIVATE
        termin_engine
        termin_scene::termin_scene
    )
    add_test(
        NAME termin_engine_render_topology_test
        COMMAND termin_engine_render_topology_test
    )

    add_executable(termin_engine_render_frame_planner_test
        tests/test_render_frame_planner.cpp
        src/render_frame_planner.cpp
    )
    target_include_directories(termin_engine_render_frame_planner_test PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/src
    )
    target_link_libraries(termin_engine_render_frame_planner_test PRIVATE termin_engine)
    add_test(
        NAME termin_engine_render_frame_planner_test
        COMMAND termin_engine_render_frame_planner_test
    )

    add_executable(termin_engine_frame_cadence_test
        tests/test_frame_cadence.cpp
    )
    target_include_directories(termin_engine_frame_cadence_test PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/src
    )
    add_test(
        NAME termin_engine_frame_cadence_test
        COMMAND termin_engine_frame_cadence_test
    )

    add_executable(termin_engine_viewport_render_state_test
        tests/test_viewport_render_state.cpp
    )
    target_include_directories(termin_engine_viewport_render_state_test PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/../termin-thirdparty/guard
    )
    target_link_libraries(termin_engine_viewport_render_state_test PRIVATE termin_engine)
    add_test(
        NAME termin_engine_viewport_render_state_test
        COMMAND termin_engine_viewport_render_state_test
    )
endif()

termin_label_tests_in_directory("termin-engine")
