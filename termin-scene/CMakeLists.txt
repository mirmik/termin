cmake_minimum_required(VERSION 3.14)
project(termin_scene VERSION 0.1.0 LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

option(TERMIN_SCENE_BUILD_SHARED "Build shared library" ON)
option(TERMIN_SCENE_BUILD_TESTS "Build tests" ON)
option(TERMIN_BUILD_PYTHON "Build Python bindings (_scene_native)" OFF)

# Dependencies
find_package(termin_base REQUIRED)
find_package(termin_inspect REQUIRED)

# Optional: nanobind for Python bindings
if(TERMIN_BUILD_PYTHON)
    if(NOT Python_EXECUTABLE)
        if(WIN32)
            set(Python_EXECUTABLE "python")
        else()
            set(Python_EXECUTABLE "python3")
        endif()
    endif()
    find_package(Python 3.8 COMPONENTS Interpreter Development REQUIRED)
    find_package(nanobind CONFIG REQUIRED)
endif()

set(TERMIN_SCENE_SOURCES
    src/termin_scene_version.c
    src/termin_scene_runtime.c
    src/tc_archetype.c
    src/tc_component.c
    src/tc_entity_pool.c
    src/tc_entity_pool_registry.c
    src/tc_hash_map.c
    src/tc_scene.c
    src/tc_scene_extension.c
    src/tc_type_registry.c
    src/tc_component_python.c
)

set(TERMIN_SCENE_CXX_SOURCES
    cpp/geom/general_transform3.cpp
    cpp/entity/entity.cpp
    cpp/entity/component.cpp
    cpp/entity/component_registry.cpp
    cpp/entity/vtable_utils.cpp
    cpp/entity/input_handler.cpp
    cpp/tc_scene.cpp
)

set(TERMIN_SCENE_CXX_HEADERS
    include/termin/export.hpp
    include/termin/geom/general_transform3.hpp
    include/termin/entity/entity.hpp
    include/termin/entity/component.hpp
    include/termin/entity/component_registry.hpp
    include/termin/entity/component_registry_python.hpp
    include/termin/entity/vtable_utils.hpp
    include/termin/entity/input_handler.hpp
    include/termin/tc_scene.hpp
    include/inspect/tc_inspect_context.h
)

set(TERMIN_SCENE_HEADERS
    include/termin_scene/termin_scene.h
    include/core/tc_archetype.h
    include/core/tc_component.h
    include/core/tc_dlist.h
    include/core/tc_entity_pool.h
    include/core/tc_entity_pool_registry.h
    include/core/tc_scene.h
    include/core/tc_scene_extension.h
    include/core/tc_scene_pool.h
    include/tc_hash_map.h
    include/tc_type_registry.h
    include/tc_types.h
    include/tc_value.h
    include/tc_component_python.h
)

if(TERMIN_SCENE_BUILD_SHARED)
    add_library(termin_scene SHARED
        ${TERMIN_SCENE_SOURCES} ${TERMIN_SCENE_HEADERS}
        ${TERMIN_SCENE_CXX_SOURCES} ${TERMIN_SCENE_CXX_HEADERS}
    )
    target_compile_definitions(termin_scene PRIVATE TERMIN_SCENE_EXPORTS TC_EXPORTS)
else()
    add_library(termin_scene STATIC
        ${TERMIN_SCENE_SOURCES} ${TERMIN_SCENE_HEADERS}
        ${TERMIN_SCENE_CXX_SOURCES} ${TERMIN_SCENE_CXX_HEADERS}
    )
endif()

add_library(termin_scene::termin_scene ALIAS termin_scene)

set_target_properties(termin_scene PROPERTIES
    POSITION_INDEPENDENT_CODE ON
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    INSTALL_RPATH "$ORIGIN"
    BUILD_WITH_INSTALL_RPATH TRUE
)

target_include_directories(termin_scene
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include>
)

target_link_libraries(termin_scene PUBLIC tcbase::termin_base termin_inspect::termin_inspect)

if(UNIX AND NOT APPLE)
    target_link_libraries(termin_scene PRIVATE m)
endif()

# _scene_native Python module (Entity, Component, TcScene core, registries)
if(TERMIN_BUILD_PYTHON)
    if(NOT TARGET termin_inspect::termin_inspect_python)
        message(FATAL_ERROR "termin_scene python bindings require termin_inspect::termin_inspect_python target")
    endif()
    nanobind_add_module(_scene_native NB_SHARED
        cpp/bindings/scene_module.cpp
        cpp/bindings/entity_bindings.cpp
        cpp/bindings/tc_component_ref_bindings.cpp
        cpp/bindings/component_bindings.cpp
        cpp/bindings/component_registry_python.cpp
        cpp/bindings/transform_bindings.cpp
        cpp/bindings/tc_scene_bindings.cpp
        cpp/bindings/soa_bindings.cpp
        cpp/bindings/tc_component_python_bindings.cpp
    )
    target_link_libraries(_scene_native PRIVATE termin_scene termin_inspect::termin_inspect termin_inspect::termin_inspect_python)
    target_compile_definitions(_scene_native PRIVATE TERMIN_HAS_NANOBIND)

    set(TERMIN_SCENE_PY_RPATH "$ORIGIN;$ORIGIN/..;$ORIGIN/../..;$ORIGIN/../../..")
    set_target_properties(_scene_native PROPERTIES
        INSTALL_RPATH "${TERMIN_SCENE_PY_RPATH}"
        BUILD_WITH_INSTALL_RPATH TRUE
    )

    if(TERMIN_SCENE_PYTHON_PREFIX)
        install(TARGETS _scene_native DESTINATION ${TERMIN_SCENE_PYTHON_PREFIX}/scene)
    else()
        install(TARGETS _scene_native DESTINATION lib/python/termin/scene)
    endif()
    install(DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/python/termin/scene/
        DESTINATION lib/python/termin/scene
        FILES_MATCHING PATTERN "*.py"
    )
endif()


install(TARGETS termin_scene
    EXPORT termin_sceneTargets
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
    RUNTIME DESTINATION bin
)

install(DIRECTORY include/
    DESTINATION include
)

install(EXPORT termin_sceneTargets
    FILE termin_sceneTargets.cmake
    NAMESPACE termin_scene::
    DESTINATION lib/cmake/termin_scene
)

include(CMakePackageConfigHelpers)

configure_package_config_file(
    ${CMAKE_CURRENT_SOURCE_DIR}/cmake/termin_sceneConfig.cmake.in
    ${CMAKE_CURRENT_BINARY_DIR}/termin_sceneConfig.cmake
    INSTALL_DESTINATION lib/cmake/termin_scene
)

write_basic_package_version_file(
    ${CMAKE_CURRENT_BINARY_DIR}/termin_sceneConfigVersion.cmake
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMajorVersion
)

install(FILES
    ${CMAKE_CURRENT_BINARY_DIR}/termin_sceneConfig.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/termin_sceneConfigVersion.cmake
    DESTINATION lib/cmake/termin_scene
)

if(TERMIN_SCENE_BUILD_TESTS)
    enable_testing()

    add_executable(termin_scene_data_structures_test tests/test_data_structures.c)
    target_link_libraries(termin_scene_data_structures_test PRIVATE termin_scene)
    add_test(NAME termin_scene_data_structures_test COMMAND termin_scene_data_structures_test)

    add_executable(termin_scene_archetype_test tests/test_archetype.c)
    target_link_libraries(termin_scene_archetype_test PRIVATE termin_scene)
    add_test(NAME termin_scene_archetype_test COMMAND termin_scene_archetype_test)

    set_target_properties(
        termin_scene_data_structures_test termin_scene_archetype_test
        PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    )
endif()
