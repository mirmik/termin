cmake_minimum_required(VERSION 3.16)
project(termin_components_ui LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
option(TERMIN_BUILD_PYTHON "Build Python bindings for UI components" OFF)

if(COMMAND termin_require_package)
    termin_require_package(termin_base tcbase::termin_base)
    termin_require_package(termin_inspect termin_inspect::termin_inspect)
    termin_require_package(termin_scene termin_scene::termin_scene)
    termin_require_package(termin_input termin_input::termin_input)
    termin_require_package(termin_display termin_display::termin_display)
    termin_require_package(termin_gui_native termin_gui_native::termin_gui_native)
else()
    find_package(termin_base REQUIRED)
    find_package(termin_inspect REQUIRED)
    find_package(termin_scene REQUIRED)
    find_package(termin_input REQUIRED)
    find_package(termin_display REQUIRED)
    find_package(termin_gui_native REQUIRED)
endif()

include(${CMAKE_CURRENT_LIST_DIR}/../cmake/TerminModule.cmake)

termin_add_module(
    NAME termin_components_ui
    NAMESPACE termin_components_ui::
    SOURCES
        src/components_bootstrap.cpp
        src/scene_ui_document_capability.c
        src/ui_component.cpp
        src/world_ui_surface_component.cpp
    PUBLIC_DEPS
        tcbase::termin_base
        termin_inspect::termin_inspect
        termin_scene::termin_scene
        termin_input::termin_input
        termin_display::termin_display
        termin_gui_native::termin_gui_native
    FIND_DEPS
        termin_base
        termin_inspect
        termin_scene
        termin_input
        termin_display
        termin_gui_native
    INSTALL_HEADERS
        termin
)

if(MSVC)
    target_compile_options(termin_components_ui PRIVATE /wd4251 /wd4275)
endif()

if(TERMIN_BUILD_TESTS)
    enable_testing()
    add_executable(termin_components_ui_component_test
        tests/test_ui_component.cpp
    )
    target_include_directories(termin_components_ui_component_test PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/../../../termin-thirdparty/guard
    )
    target_link_libraries(termin_components_ui_component_test PRIVATE
        termin_components_ui
    )
    set_target_properties(termin_components_ui_component_test PROPERTIES
        RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    )
    add_test(
        NAME termin_components_ui_component_test
        COMMAND termin_components_ui_component_test
    )
endif()

if(TERMIN_BUILD_PYTHON)
    find_package(Python 3.14 COMPONENTS Interpreter Development REQUIRED)
    find_package(nanobind CONFIG REQUIRED)

    nanobind_add_module(_ui_components_native NB_SHARED
        cpp/bindings/ui_components_module.cpp
    )
    target_link_libraries(_ui_components_native PRIVATE termin_components_ui)

    if(TERMIN_COMPONENTS_UI_PYTHON_PREFIX)
        set(_py_dest ${TERMIN_COMPONENTS_UI_PYTHON_PREFIX}/ui_components)
    else()
        set(_py_dest lib/python/termin/ui_components)
    endif()
    install(TARGETS _ui_components_native DESTINATION ${_py_dest})
    install(DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/python/termin/ui_components/
        DESTINATION ${_py_dest}
        PATTERN "__pycache__" EXCLUDE
        PATTERN "*.pyc" EXCLUDE
    )
endif()

termin_label_tests_in_directory("termin-components-ui")
