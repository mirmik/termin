cmake_minimum_required(VERSION 3.18)
project(termin_csg VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

option(TERMIN_CSG_BUILD_TESTS "Build termin-csg tests" OFF)
option(TERMIN_CSG_BUILD_EXAMPLES "Build termin-csg examples" OFF)
option(TERMIN_BUILD_PYTHON "Build termin-csg Python bindings" OFF)

if(COMMAND termin_require_package)
    termin_require_package(termin_base tcbase::termin_base)
else()
    find_package(termin_base REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_mesh tmesh::termin_mesh)
else()
    find_package(termin_mesh REQUIRED)
endif()

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_LIST_DIR}/../cmake")
include(TerminRpath)

set(TERMIN_CSG_THIRDPARTY_DIR "${CMAKE_CURRENT_LIST_DIR}/../termin-thirdparty")
set(TERMIN_CSG_MANIFOLD_DIR "${TERMIN_CSG_THIRDPARTY_DIR}/manifold")
set(TERMIN_CSG_CLIPPER2_DIR "${TERMIN_CSG_THIRDPARTY_DIR}/clipper2")

if(NOT EXISTS "${TERMIN_CSG_MANIFOLD_DIR}/CMakeLists.txt")
    message(FATAL_ERROR "Manifold is missing: ${TERMIN_CSG_MANIFOLD_DIR}")
endif()

if(NOT EXISTS "${TERMIN_CSG_CLIPPER2_DIR}/CPP/CMakeLists.txt")
    message(FATAL_ERROR "Clipper2 is missing: ${TERMIN_CSG_CLIPPER2_DIR}")
endif()

set(MANIFOLD_CROSS_SECTION ON CACHE BOOL "" FORCE)
set(MANIFOLD_DOWNLOADS OFF CACHE BOOL "" FORCE)
set(MANIFOLD_PAR OFF CACHE BOOL "" FORCE)
set(MANIFOLD_TEST OFF CACHE BOOL "" FORCE)
set(MANIFOLD_PYBIND OFF CACHE BOOL "" FORCE)
set(MANIFOLD_CBIND OFF CACHE BOOL "" FORCE)
set(MANIFOLD_JSBIND OFF CACHE BOOL "" FORCE)
set(MANIFOLD_USE_BUILTIN_CLIPPER2 ON CACHE BOOL "" FORCE)
set(FETCHCONTENT_SOURCE_DIR_CLIPPER2 "${TERMIN_CSG_CLIPPER2_DIR}" CACHE PATH "" FORCE)
set(FETCHCONTENT_SOURCE_DIR_Clipper2 "${TERMIN_CSG_CLIPPER2_DIR}" CACHE PATH "" FORCE)
set(BUILD_SHARED_LIBS OFF)

add_subdirectory("${TERMIN_CSG_MANIFOLD_DIR}" "${CMAKE_CURRENT_BINARY_DIR}/thirdparty/manifold" EXCLUDE_FROM_ALL)

add_library(termin_csg SHARED
    src/csg.cpp
)
add_library(tcsg::termin_csg ALIAS termin_csg)

target_include_directories(termin_csg PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)

target_link_libraries(termin_csg PUBLIC
    tcbase::termin_base
    tmesh::termin_mesh
)

target_link_libraries(termin_csg PRIVATE
    manifold
)

set_target_properties(termin_csg PROPERTIES
    VERSION ${PROJECT_VERSION}
    SOVERSION 0
)
termin_set_rpath_lib(termin_csg)

if(TERMIN_CSG_BUILD_TESTS)
    enable_testing()
    add_subdirectory(tests)
endif()

if(TERMIN_CSG_BUILD_EXAMPLES)
    add_subdirectory(examples)
endif()

if(TERMIN_BUILD_PYTHON)
    add_subdirectory(python)
endif()

include(GNUInstallDirs)

install(TARGETS termin_csg
    EXPORT termin_csgTargets
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
)

install(DIRECTORY include/termin
    DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
)

install(EXPORT termin_csgTargets
    FILE termin_csgTargets.cmake
    NAMESPACE tcsg::
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_csg
)

include(CMakePackageConfigHelpers)

configure_package_config_file(
    cmake/termin_csgConfig.cmake.in
    ${CMAKE_CURRENT_BINARY_DIR}/termin_csgConfig.cmake
    INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_csg
)

write_basic_package_version_file(
    ${CMAKE_CURRENT_BINARY_DIR}/termin_csgConfigVersion.cmake
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMajorVersion
)

install(FILES
    ${CMAKE_CURRENT_BINARY_DIR}/termin_csgConfig.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/termin_csgConfigVersion.cmake
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_csg
)
