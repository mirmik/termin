cmake_minimum_required(VERSION 3.16)
project(termin_physics VERSION 0.1.0 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

option(TERMIN_PHYSICS_BUILD_TESTS "Build termin-physics tests" OFF)
option(TERMIN_BUILD_PYTHON "Build Python bindings (_physics_native)" OFF)

find_package(termin_base REQUIRED)
find_package(termin_collision REQUIRED)

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

set(TERMIN_PHYSICS_SOURCES
    src/termin_physics_version.cpp
)

add_library(termin_physics SHARED ${TERMIN_PHYSICS_SOURCES})
add_library(termin_physics::termin_physics ALIAS termin_physics)

target_compile_definitions(termin_physics PRIVATE TERMIN_PHYSICS_EXPORTS)

target_include_directories(termin_physics PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)

target_link_libraries(termin_physics PUBLIC
    tcbase::termin_base
    termin_collision::termin_collision
)

set_target_properties(termin_physics PROPERTIES
    VERSION ${PROJECT_VERSION}
    SOVERSION 0
)
if(NOT WIN32)
    set_target_properties(termin_physics PROPERTIES INSTALL_RPATH "$ORIGIN")
endif()

if(TERMIN_BUILD_PYTHON)
    nanobind_add_module(_physics_native NB_SHARED cpp/bindings/physics_bindings.cpp)
    target_link_libraries(_physics_native PRIVATE termin_physics)

    set(TERMIN_PHYSICS_PY_RPATH "$ORIGIN;$ORIGIN/..;$ORIGIN/../..;$ORIGIN/../../..")
    set_target_properties(_physics_native PROPERTIES
        INSTALL_RPATH "${TERMIN_PHYSICS_PY_RPATH}"
        BUILD_WITH_INSTALL_RPATH TRUE
    )

    if(TERMIN_PHYSICS_PYTHON_PREFIX)
        install(TARGETS _physics_native DESTINATION ${TERMIN_PHYSICS_PYTHON_PREFIX}/physics)
    else()
        install(TARGETS _physics_native DESTINATION lib/python/termin/physics)
    endif()
endif()

include(GNUInstallDirs)

install(TARGETS termin_physics
    EXPORT termin_physicsTargets
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
    RUNTIME DESTINATION ${CMAKE_INSTALL_LIBDIR}
)

install(DIRECTORY include/termin
    DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
)

install(EXPORT termin_physicsTargets
    FILE termin_physicsTargets.cmake
    NAMESPACE termin_physics::
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_physics
)

include(CMakePackageConfigHelpers)

configure_package_config_file(
    cmake/termin_physicsConfig.cmake.in
    ${CMAKE_CURRENT_BINARY_DIR}/termin_physicsConfig.cmake
    INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_physics
)

write_basic_package_version_file(
    ${CMAKE_CURRENT_BINARY_DIR}/termin_physicsConfigVersion.cmake
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMajorVersion
)

install(FILES
    ${CMAKE_CURRENT_BINARY_DIR}/termin_physicsConfig.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/termin_physicsConfigVersion.cmake
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_physics
)
