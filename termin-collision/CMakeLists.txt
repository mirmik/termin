cmake_minimum_required(VERSION 3.16)
project(termin_collision VERSION 0.1.0 LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

option(TERMIN_COLLISION_BUILD_TESTS "Build termin-collision tests" OFF)
option(TERMIN_BUILD_PYTHON "Build Python bindings (_colliders_native, _collision_native)" OFF)

# Dependencies (current valid contract for migration phase)
find_package(termin_base REQUIRED)
find_package(termin_inspect REQUIRED)
find_package(termin_scene REQUIRED)

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_LIST_DIR}/../cmake")
include(TerminRpath)

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

set(TERMIN_COLLISION_SOURCES
    src/termin_collision_version.cpp
    src/termin_collision_runtime.c
    src/termin/tc_collision_c_api.cpp
    src/termin/collision/collision_world_c.cpp
    src/termin/collision/tc_collision_world_ext.c
)

add_library(termin_collision SHARED ${TERMIN_COLLISION_SOURCES})
add_library(termin_collision::termin_collision ALIAS termin_collision)

target_compile_definitions(termin_collision PRIVATE TERMIN_COLLISION_EXPORTS TC_EXPORTS)

if(MSVC)
    target_compile_options(termin_collision PRIVATE /wd4251 /wd4275)
endif()

target_include_directories(termin_collision PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include/termin/colliders>
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include/termin/collision>
    $<INSTALL_INTERFACE:include>
)

target_link_libraries(termin_collision PUBLIC
    tcbase::termin_base
    termin_inspect::termin_inspect
    termin_scene::termin_scene
)

set_target_properties(termin_collision PROPERTIES
    VERSION ${PROJECT_VERSION}
    SOVERSION 0
)
termin_set_rpath_lib(termin_collision)

if(TERMIN_BUILD_PYTHON)
    nanobind_add_module(_colliders_native NB_SHARED cpp/bindings/colliders_bindings.cpp)
    target_link_libraries(_colliders_native PRIVATE termin_collision)

    nanobind_add_module(_collision_native NB_SHARED cpp/bindings/collision_bindings.cpp)
    target_link_libraries(_collision_native PRIVATE termin_collision termin_scene::termin_scene)

    termin_set_rpath_python(_colliders_native)
    termin_set_rpath_python(_collision_native)

    if(TERMIN_COLLISION_PYTHON_PREFIX)
        install(TARGETS _colliders_native DESTINATION ${TERMIN_COLLISION_PYTHON_PREFIX}/colliders)
        install(TARGETS _collision_native DESTINATION ${TERMIN_COLLISION_PYTHON_PREFIX}/collision)
    else()
        install(TARGETS _colliders_native DESTINATION lib/python/termin/colliders)
        install(TARGETS _collision_native DESTINATION lib/python/termin/collision)
    endif()

    install(DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/python/termin/colliders/
        DESTINATION lib/python/termin/colliders
        PATTERN "__pycache__" EXCLUDE
        PATTERN "*.pyc" EXCLUDE
        PATTERN "lib" EXCLUDE
    )
    install(DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/python/termin/collision/
        DESTINATION lib/python/termin/collision
        PATTERN "__pycache__" EXCLUDE
        PATTERN "*.pyc" EXCLUDE
        PATTERN "lib" EXCLUDE
    )
endif()


if(TERMIN_COLLISION_BUILD_TESTS)
    enable_testing()

    add_executable(termin_collision_tests
        tests/main.cpp
        tests/tests_colliders.cpp
        tests/tests_collision.cpp
        tests/tests_gjk.cpp
        tests/tests_quickhull.cpp
        tests/tests_convex_hull_collider.cpp
    )
    target_include_directories(termin_collision_tests PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/tests
        ${CMAKE_CURRENT_SOURCE_DIR}/tests/guard
    )
    target_link_libraries(termin_collision_tests PRIVATE termin_collision)
    add_test(NAME termin_collision_tests COMMAND termin_collision_tests)
endif()

include(GNUInstallDirs)

install(TARGETS termin_collision
    EXPORT termin_collisionTargets
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
)

install(DIRECTORY include/termin_collision
    DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
)

install(DIRECTORY include/termin
    DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
)

install(DIRECTORY include/physics
    DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
)

install(EXPORT termin_collisionTargets
    FILE termin_collisionTargets.cmake
    NAMESPACE termin_collision::
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_collision
)

include(CMakePackageConfigHelpers)

configure_package_config_file(
    cmake/termin_collisionConfig.cmake.in
    ${CMAKE_CURRENT_BINARY_DIR}/termin_collisionConfig.cmake
    INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_collision
)

write_basic_package_version_file(
    ${CMAKE_CURRENT_BINARY_DIR}/termin_collisionConfigVersion.cmake
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMajorVersion
)

install(FILES
    ${CMAKE_CURRENT_BINARY_DIR}/termin_collisionConfig.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/termin_collisionConfigVersion.cmake
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_collision
)
