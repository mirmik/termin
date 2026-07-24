cmake_minimum_required(VERSION 3.16)
project(termin_navmesh VERSION 0.1.0 LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
option(TERMIN_BUILD_PYTHON "Build Python bindings" OFF)
option(TERMIN_NAVMESH_BUILD_RECAST "Build Recast-backed navmesh components and Python bindings" ON)
option(TERMIN_NAVMESH_BUILD_TESTS "Build termin-navmesh C/C++ tests" OFF)

if(DEFINED TERMIN_BUILD_TESTS)
    set(TERMIN_NAVMESH_EFFECTIVE_BUILD_TESTS ${TERMIN_BUILD_TESTS})
else()
    set(TERMIN_NAVMESH_EFFECTIVE_BUILD_TESTS ${TERMIN_NAVMESH_BUILD_TESTS})
endif()

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
    termin_require_package(termin_inspect termin_inspect::termin_inspect)
else()
    find_package(termin_inspect REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_materials termin_materials::termin_materials)
else()
    find_package(termin_materials REQUIRED)
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
    termin_require_package(termin_components_mesh termin_components_mesh::termin_components_mesh)
else()
    find_package(termin_components_mesh REQUIRED)
endif()

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_LIST_DIR}/../cmake")
include(TerminRpath)

add_library(termin_navmesh SHARED
    src/tc_navmesh_registry.c
)
add_library(termin_navmesh::termin_navmesh ALIAS termin_navmesh)

target_compile_definitions(termin_navmesh PRIVATE TERMIN_NAVMESH_EXPORTS)

target_include_directories(termin_navmesh PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)

target_link_libraries(termin_navmesh PUBLIC
    tcbase::termin_base
)

set_target_properties(termin_navmesh PROPERTIES
    VERSION ${PROJECT_VERSION}
    SOVERSION 0
    WINDOWS_EXPORT_ALL_SYMBOLS OFF
)
termin_set_rpath_lib(termin_navmesh)

include(GNUInstallDirs)

set(TERMIN_HAS_RECAST OFF CACHE INTERNAL "termin-navmesh has Recast/Detour support")
set(TERMIN_RECASTNAVIGATION_DIR
    "${CMAKE_CURRENT_LIST_DIR}/../termin-thirdparty/recastnavigation"
    CACHE PATH "RecastNavigation source directory")
set(TERMIN_RECAST_DIR "${TERMIN_RECASTNAVIGATION_DIR}/Recast")
set(TERMIN_DETOUR_DIR "${TERMIN_RECASTNAVIGATION_DIR}/Detour")

if(TERMIN_NAVMESH_BUILD_RECAST)
    if(EXISTS "${TERMIN_RECAST_DIR}/CMakeLists.txt" AND EXISTS "${TERMIN_DETOUR_DIR}/CMakeLists.txt")
        set(SOVERSION 1)
        set(LIB_VERSION 1.6.0)
        set(RECASTNAVIGATION_ENABLE_ASSERTS OFF)
        set(SKIP_INSTALL_ALL ON)

        if(NOT TARGET Recast)
            add_subdirectory(${TERMIN_RECAST_DIR} ${CMAKE_CURRENT_BINARY_DIR}/Recast EXCLUDE_FROM_ALL)
        endif()
        if(NOT TARGET Detour)
            add_subdirectory(${TERMIN_DETOUR_DIR} ${CMAKE_CURRENT_BINARY_DIR}/Detour EXCLUDE_FROM_ALL)
        endif()

        set_target_properties(Recast PROPERTIES EXCLUDE_FROM_ALL FALSE UNITY_BUILD OFF)
        set_target_properties(Detour PROPERTIES EXCLUDE_FROM_ALL FALSE UNITY_BUILD OFF)
        target_include_directories(Recast PUBLIC
            $<INSTALL_INTERFACE:include/recastnavigation>
        )
        target_include_directories(Detour PUBLIC
            $<INSTALL_INTERFACE:include/recastnavigation>
        )
        set(TERMIN_HAS_RECAST ON CACHE INTERNAL "termin-navmesh has Recast/Detour support")
    elseif(TERMIN_BUILD_PYTHON)
        message(FATAL_ERROR
            "TERMIN_BUILD_PYTHON=ON requires the recastnavigation submodule. "
            "Run: git submodule update --init --recursive termin-thirdparty/recastnavigation")
    else()
        message(WARNING "Recast/Detour submodules not found; termin-navmesh components will be disabled.")
    endif()
endif()

if(TERMIN_HAS_RECAST)
    add_library(termin_navmesh_components SHARED
        src/components_bootstrap.cpp
        src/detour_navmesh_build.cpp
        src/detour_navmesh_asset_utils.cpp
        src/detour_pathfinding_world_component.cpp
        src/navmesh_bake_source.cpp
        src/detour_query_session.cpp
        src/navmesh_keeper_component.cpp
        src/off_mesh_link_component.cpp
        src/pathfinding_world.cpp
        src/recast_navmesh_bake.cpp
        src/recast_navmesh_entity_geometry.cpp
        src/recast_navmesh_builder_component.cpp
        src/tc_pathfinding_world_ext.cpp
    )
    add_library(termin_navmesh::termin_navmesh_components ALIAS termin_navmesh_components)
    target_include_directories(termin_navmesh_components PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include>
    )
    target_link_libraries(termin_navmesh_components PUBLIC
        termin_navmesh::termin_navmesh
        tcbase::termin_base
        tgfx::termin_graphics
        tgfx::termin_graphics2
        termin_inspect::termin_inspect
        termin_materials::termin_materials
        termin_scene::termin_scene
        termin_render::termin_render
        termin_components_mesh::termin_components_mesh
        Recast
        Detour
    )
    target_compile_features(termin_navmesh_components PUBLIC cxx_std_20)
    target_compile_definitions(termin_navmesh_components PRIVATE TERMIN_NAVMESH_COMPONENTS_EXPORTS)
    if(COMMAND termin_enable_pch_for)
        termin_enable_pch_for(termin_navmesh_components)
    endif()
    if(COMMAND termin_enable_unity_build_for)
        termin_enable_unity_build_for(termin_navmesh_components)
    endif()
    set_target_properties(termin_navmesh_components PROPERTIES
        VERSION ${PROJECT_VERSION}
        SOVERSION 0
        WINDOWS_EXPORT_ALL_SYMBOLS OFF
    )
    termin_set_rpath_lib(termin_navmesh_components)

    if(TERMIN_BUILD_PYTHON)
        find_package(Python 3.14 COMPONENTS Interpreter Development REQUIRED)
        find_package(nanobind CONFIG REQUIRED)
        if(NOT TARGET termin_inspect::termin_inspect_python)
            message(FATAL_ERROR "termin-navmesh Python build requires termin_inspect::termin_inspect_python")
        endif()

        nanobind_add_module(_navmesh_native NB_SHARED
            python/bindings/navmesh_module.cpp
        )
        target_link_libraries(_navmesh_native PRIVATE
            termin_navmesh_components
            termin_inspect::termin_inspect_python
        )
        target_compile_features(_navmesh_native PRIVATE cxx_std_20)
        termin_set_rpath_python(_navmesh_native)
        install(TARGETS _navmesh_native DESTINATION lib/python/termin/navmesh)
    endif()

    if(TERMIN_NAVMESH_EFFECTIVE_BUILD_TESTS)
        enable_testing()
        add_executable(termin_navmesh_bake_visitor_registry_test
            tests/test_navmesh_bake_visitor_registry.cpp
        )
        target_link_libraries(termin_navmesh_bake_visitor_registry_test
            PRIVATE termin_navmesh_components
        )
        termin_set_rpath_test(termin_navmesh_bake_visitor_registry_test)
        add_test(
            NAME termin_navmesh_bake_visitor_registry_test
            COMMAND termin_navmesh_bake_visitor_registry_test
        )

        add_executable(termin_navmesh_detour_linear_paths_test
            tests/test_detour_linear_paths.cpp
        )
        target_link_libraries(termin_navmesh_detour_linear_paths_test
            PRIVATE Detour
        )
        termin_set_rpath_test(termin_navmesh_detour_linear_paths_test)
        add_test(
            NAME termin_navmesh_detour_linear_paths_test
            COMMAND termin_navmesh_detour_linear_paths_test
        )
    endif()
endif()

install(TARGETS termin_navmesh
    EXPORT termin_navmeshTargets
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
)

if(TERMIN_HAS_RECAST)
    install(TARGETS termin_navmesh_components Recast Detour
        EXPORT termin_navmeshTargets
        LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
        ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
        RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
    )
    install(DIRECTORY ${TERMIN_RECAST_DIR}/Include/
        DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}/recastnavigation
        FILES_MATCHING PATTERN "*.h"
    )
    install(DIRECTORY ${TERMIN_DETOUR_DIR}/Include/
        DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}/recastnavigation
        FILES_MATCHING PATTERN "*.h"
    )
endif()

install(DIRECTORY include/termin
    DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
)

install(EXPORT termin_navmeshTargets
    FILE termin_navmeshTargets.cmake
    NAMESPACE termin_navmesh::
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_navmesh
)

include(CMakePackageConfigHelpers)

configure_package_config_file(
    cmake/termin_navmeshConfig.cmake.in
    ${CMAKE_CURRENT_BINARY_DIR}/termin_navmeshConfig.cmake
    INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_navmesh
)

write_basic_package_version_file(
    ${CMAKE_CURRENT_BINARY_DIR}/termin_navmeshConfigVersion.cmake
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMajorVersion
)

install(FILES
    ${CMAKE_CURRENT_BINARY_DIR}/termin_navmeshConfig.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/termin_navmeshConfigVersion.cmake
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_navmesh
)

termin_label_tests_in_directory("termin-navmesh")
