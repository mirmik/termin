cmake_minimum_required(VERSION 3.16)
project(termin_components_physics_fem_ui LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

foreach(_dep IN ITEMS
        termin_base
        termin_scene
        termin_inspect
        termin_gui_native
        termin_components_ui
        termin_components_physics_fem)
    if(COMMAND termin_require_package)
        if(_dep STREQUAL "termin_base")
            termin_require_package(termin_base tcbase::termin_base)
        elseif(_dep STREQUAL "termin_scene")
            termin_require_package(termin_scene termin_scene::termin_scene)
        elseif(_dep STREQUAL "termin_inspect")
            termin_require_package(termin_inspect termin_inspect::termin_inspect)
        elseif(_dep STREQUAL "termin_gui_native")
            termin_require_package(termin_gui_native termin_gui_native::termin_gui_native)
        elseif(_dep STREQUAL "termin_components_ui")
            termin_require_package(termin_components_ui termin_components_ui::termin_components_ui)
        elseif(_dep STREQUAL "termin_components_physics_fem")
            termin_require_package(termin_components_physics_fem termin_components_physics_fem::termin_components_physics_fem)
        endif()
    else()
        find_package(${_dep} REQUIRED)
    endif()
endforeach()

include(${CMAKE_CURRENT_LIST_DIR}/../cmake/TerminModule.cmake)

termin_add_module(
    NAME termin_components_physics_fem_ui
    NAMESPACE termin_components_physics_fem_ui::
    SOURCES
        src/components.cpp
        src/components_bootstrap.cpp
    PUBLIC_DEPS
        tcbase::termin_base
        termin_scene::termin_scene
        termin_inspect::termin_inspect
        termin_gui_native::termin_gui_native
        termin_components_ui::termin_components_ui
        termin_components_physics_fem::termin_components_physics_fem
    FIND_DEPS
        termin_base
        termin_scene
        termin_inspect
        termin_gui_native
        termin_components_ui
        termin_components_physics_fem
    INSTALL_HEADERS include/termin
)

target_include_directories(termin_components_physics_fem_ui PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
)

if(MSVC)
    target_compile_options(termin_components_physics_fem_ui PRIVATE /wd4251 /wd4275)
endif()
