cmake_minimum_required(VERSION 3.16)
project(termin_components_collision LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
option(TERMIN_BUILD_PYTHON "Build Python binding for ColliderComponent" OFF)

if(COMMAND termin_require_package)
    termin_require_package(termin_base tcbase::termin_base)
else()
    find_package(termin_base REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_scene termin_scene::termin_scene)
else()
    find_package(termin_scene REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_inspect termin_inspect::termin_inspect)
else()
    find_package(termin_inspect REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_mesh tmesh::termin_mesh)
else()
    find_package(termin_mesh REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_collision termin_collision::termin_collision)
else()
    find_package(termin_collision REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_components_mesh termin_components_mesh::termin_components_mesh)
else()
    find_package(termin_components_mesh REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_render termin_render::termin_render)
else()
    find_package(termin_render REQUIRED)
endif()

include(${CMAKE_CURRENT_LIST_DIR}/../cmake/TerminModule.cmake)

termin_add_module(
    NAME termin_components_collision
    NAMESPACE termin_components_collision::
    SOURCES
        components/collider_component.cpp
        components/components_collision_bootstrap.cpp
    PUBLIC_DEPS tcbase::termin_base termin_scene::termin_scene termin_inspect::termin_inspect tmesh::termin_mesh termin_collision::termin_collision termin_components_mesh::termin_components_mesh termin_render::termin_render
    FIND_DEPS termin_base termin_scene termin_inspect termin_mesh termin_collision termin_components_mesh termin_render
    INSTALL_HEADERS components
)

if(MSVC)
    target_compile_options(termin_components_collision PRIVATE /wd4251 /wd4275)
endif()

if(TERMIN_BUILD_PYTHON)
    if(NOT Python_EXECUTABLE)
        if(WIN32)
            set(Python_EXECUTABLE "python")
        else()
            set(Python_EXECUTABLE "python3")
        endif()
    endif()

    find_package(Python 3.14 COMPONENTS Interpreter Development REQUIRED)
    find_package(nanobind CONFIG REQUIRED)

    nanobind_add_module(_components_collision_native NB_SHARED components/collider_component_bindings.cpp)
    target_link_libraries(_components_collision_native PRIVATE termin_components_collision)

    if(TERMIN_COMPONENTS_COLLISION_PYTHON_PREFIX)
        set(_py_dest ${TERMIN_COMPONENTS_COLLISION_PYTHON_PREFIX}/colliders)
    else()
        set(_py_dest lib/python/termin/colliders)
    endif()
    install(TARGETS _components_collision_native DESTINATION ${_py_dest})
    install(DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/python/termin/colliders/
        DESTINATION lib/python/termin/colliders
        PATTERN "__pycache__" EXCLUDE
        PATTERN "*.pyc" EXCLUDE
    )
endif()

if(TERMIN_BUILD_TESTS)
    add_executable(termin_components_collision_debug_geometry_test
        tests/test_collider_debug_geometry.cpp
    )
    target_include_directories(termin_components_collision_debug_geometry_test PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/../../../termin-thirdparty/guard
    )
    target_link_libraries(termin_components_collision_debug_geometry_test PRIVATE
        termin_components_collision
    )
    set_target_properties(termin_components_collision_debug_geometry_test PROPERTIES
        RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    )
    add_test(
        NAME termin_components_collision_debug_geometry_test
        COMMAND termin_components_collision_debug_geometry_test
    )
endif()

termin_label_tests_in_directory("termin-components-collision")
