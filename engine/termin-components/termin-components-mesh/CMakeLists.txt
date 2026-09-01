cmake_minimum_required(VERSION 3.16)
project(termin_components_mesh LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
option(TERMIN_BUILD_PYTHON "Build Python binding for MeshComponent" OFF)

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

include(${CMAKE_CURRENT_LIST_DIR}/../cmake/TerminModule.cmake)

termin_add_module(
    NAME termin_components_mesh
    NAMESPACE termin_components_mesh::
    SOURCES
        components/components_mesh_bootstrap.cpp
        components/mesh_component.cpp
    PUBLIC_DEPS tcbase::termin_base termin_scene::termin_scene termin_inspect::termin_inspect tmesh::termin_mesh
    FIND_DEPS termin_base termin_scene termin_inspect termin_mesh
    INSTALL_HEADERS components
)

if(MSVC)
    target_compile_options(termin_components_mesh PRIVATE /wd4251 /wd4275)
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

    nanobind_add_module(_components_mesh_native NB_SHARED components/mesh_component_bindings.cpp)
    target_link_libraries(_components_mesh_native PRIVATE termin_components_mesh)

    if(TERMIN_COMPONENTS_MESH_PYTHON_PREFIX)
        set(_py_dest ${TERMIN_COMPONENTS_MESH_PYTHON_PREFIX}/mesh/components)
    else()
        set(_py_dest lib/python/termin/mesh/components)
    endif()
    install(TARGETS _components_mesh_native DESTINATION ${_py_dest})
    install(DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/python/termin/mesh/components/
        DESTINATION ${_py_dest}
        PATTERN "__pycache__" EXCLUDE
        PATTERN "*.pyc" EXCLUDE
    )
endif()

if(TERMIN_BUILD_TESTS)
    add_executable(termin_components_mesh_component_test
        tests/test_mesh_component.cpp
    )
    target_include_directories(termin_components_mesh_component_test PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/../../../termin-thirdparty/guard
    )
    target_link_libraries(termin_components_mesh_component_test PRIVATE
        termin_components_mesh
    )
    set_target_properties(termin_components_mesh_component_test PROPERTIES
        RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    )
    add_test(
        NAME termin_components_mesh_component_test
        COMMAND termin_components_mesh_component_test
    )
endif()

termin_label_tests_in_directory("termin-components-mesh")
