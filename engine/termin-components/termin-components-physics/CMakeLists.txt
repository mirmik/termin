cmake_minimum_required(VERSION 3.16)
project(termin_components_physics VERSION 0.1.0 LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
option(TERMIN_BUILD_PYTHON "Build Python bindings for game physics components" OFF)

foreach(_dep IN ITEMS termin_base termin_scene termin_inspect termin_physics termin_collision termin_components_collision)
    if(COMMAND termin_require_package)
        if(_dep STREQUAL "termin_base")
            termin_require_package(termin_base tcbase::termin_base)
        elseif(_dep STREQUAL "termin_scene")
            termin_require_package(termin_scene termin_scene::termin_scene)
        elseif(_dep STREQUAL "termin_inspect")
            termin_require_package(termin_inspect termin_inspect::termin_inspect)
        elseif(_dep STREQUAL "termin_physics")
            termin_require_package(termin_physics termin_physics::termin_physics)
        elseif(_dep STREQUAL "termin_collision")
            termin_require_package(termin_collision termin_collision::termin_collision)
        elseif(_dep STREQUAL "termin_components_collision")
            termin_require_package(termin_components_collision termin_components_collision::termin_components_collision)
        endif()
    else()
        find_package(${_dep} REQUIRED)
    endif()
endforeach()

include(${CMAKE_CURRENT_LIST_DIR}/../cmake/TerminModule.cmake)

termin_add_module(
    NAME termin_components_physics
    NAMESPACE termin_components_physics::
    SOURCES
        src/components.cpp
        src/components_bootstrap.cpp
    PUBLIC_DEPS
        tcbase::termin_base
        termin_scene::termin_scene
        termin_inspect::termin_inspect
        termin_physics::termin_physics
        termin_collision::termin_collision
        termin_components_collision::termin_components_collision
    FIND_DEPS termin_base termin_scene termin_inspect termin_physics termin_collision termin_components_collision
    INSTALL_HEADERS include/termin
)

target_include_directories(termin_components_physics PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
)

if(MSVC)
    target_compile_options(termin_components_physics PRIVATE /wd4251 /wd4275)
endif()

if(TERMIN_BUILD_PYTHON)
    find_package(Python 3.14 COMPONENTS Interpreter Development REQUIRED)
    find_package(nanobind CONFIG REQUIRED)
    nanobind_add_module(_components_physics_native NB_SHARED
        src/physics_component_bindings.cpp)
    target_link_libraries(_components_physics_native PRIVATE
        termin_components_physics)
    install(TARGETS _components_physics_native
        DESTINATION lib/python/termin/physics_components)
    install(DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/python/termin/physics_components/
        DESTINATION lib/python/termin/physics_components
        PATTERN "__pycache__" EXCLUDE
        PATTERN "*.pyc" EXCLUDE
    )
endif()

if(TERMIN_BUILD_TESTS)
    add_executable(termin_components_physics_component_test
        tests/test_components.cpp)
    target_include_directories(termin_components_physics_component_test PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/../../../termin-thirdparty/guard)
    target_link_libraries(termin_components_physics_component_test PRIVATE
        termin_components_physics)
    set_target_properties(termin_components_physics_component_test PROPERTIES
        RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")
    add_test(
        NAME termin_components_physics_component_test
        COMMAND termin_components_physics_component_test)
endif()

termin_label_tests_in_directory("termin-components-physics")
