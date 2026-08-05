cmake_minimum_required(VERSION 3.16)
project(termin_components_physics_fem LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

foreach(_dep IN ITEMS termin_base termin_scene termin_inspect termin_qopt termin_robotics termin_physics_qopt termin_collision termin_components_collision termin_components_kinematic termin_render)
    if(COMMAND termin_require_package)
        if(_dep STREQUAL "termin_base")
            termin_require_package(termin_base tcbase::termin_base)
        elseif(_dep STREQUAL "termin_scene")
            termin_require_package(termin_scene termin_scene::termin_scene)
        elseif(_dep STREQUAL "termin_inspect")
            termin_require_package(termin_inspect termin_inspect::termin_inspect)
        elseif(_dep STREQUAL "termin_qopt")
            termin_require_package(termin_qopt termin_qopt::termin_qopt)
        elseif(_dep STREQUAL "termin_robotics")
            termin_require_package(termin_robotics termin_robotics::termin_robotics)
        elseif(_dep STREQUAL "termin_physics_qopt")
            termin_require_package(termin_physics_qopt termin_physics_qopt::termin_physics_qopt)
        elseif(_dep STREQUAL "termin_collision")
            termin_require_package(termin_collision termin_collision::termin_collision)
        elseif(_dep STREQUAL "termin_components_collision")
            termin_require_package(termin_components_collision termin_components_collision::termin_components_collision)
        elseif(_dep STREQUAL "termin_components_kinematic")
            termin_require_package(termin_components_kinematic termin_components_kinematic::termin_components_kinematic)
        elseif(_dep STREQUAL "termin_render")
            termin_require_package(termin_render termin_render::termin_render)
        endif()
    else()
        find_package(${_dep} REQUIRED)
    endif()
endforeach()

include(${CMAKE_CURRENT_LIST_DIR}/../cmake/TerminModule.cmake)

termin_add_module(
    NAME termin_components_physics_fem
    NAMESPACE termin_components_physics_fem::
    SOURCES
        src/components.cpp
        src/world_state.cpp
        src/collision_contacts.cpp
        src/articulation_scene.cpp
        src/components_bootstrap.cpp
    PUBLIC_DEPS
        tcbase::termin_base
        termin_scene::termin_scene
        termin_inspect::termin_inspect
        termin_qopt::termin_qopt
        termin_robotics::termin_robotics
        termin_physics_qopt::termin_physics_qopt
        termin_components_kinematic::termin_components_kinematic
        termin_render::termin_render
    FIND_DEPS termin_base termin_scene termin_inspect termin_qopt termin_robotics termin_physics_qopt termin_components_kinematic termin_render
    INSTALL_HEADERS include/termin
)

target_link_libraries(termin_components_physics_fem PRIVATE
    termin_collision::termin_collision
    termin_components_collision::termin_components_collision
)

target_include_directories(termin_components_physics_fem PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
)

if(MSVC)
    target_compile_options(termin_components_physics_fem PRIVATE /wd4251 /wd4275)
endif()

if(TERMIN_BUILD_PYTHON)
    find_package(Python 3.14 COMPONENTS Interpreter Development REQUIRED)
    find_package(nanobind CONFIG REQUIRED)
    nanobind_add_module(_components_physics_fem_native NB_SHARED
        src/physics_fem_bindings.cpp)
    target_link_libraries(_components_physics_fem_native PRIVATE
        termin_components_physics_fem)
    install(TARGETS _components_physics_fem_native
        DESTINATION lib/python/termin/physics_fem)
endif()

if(TERMIN_BUILD_TESTS)
    enable_testing()
    add_executable(termin_components_physics_fem_component_test
        tests/test_components.cpp
    )
    target_include_directories(termin_components_physics_fem_component_test PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/../../termin-thirdparty/guard
    )
    target_link_libraries(termin_components_physics_fem_component_test PRIVATE
        termin_components_physics_fem
        termin_components_collision::termin_components_collision
    )
    set_target_properties(termin_components_physics_fem_component_test PROPERTIES
        RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    )
    add_test(
        NAME termin_components_physics_fem_component_test
        COMMAND termin_components_physics_fem_component_test
    )
endif()

termin_label_tests_in_directory("termin-components-physics-fem")
