cmake_minimum_required(VERSION 3.16)
project(termin_qopt VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

option(TERMIN_QOPT_BUILD_TESTS "Build termin-qopt native tests" OFF)

set(TERMIN_QOPT_EIGEN_DIR
    "${CMAKE_CURRENT_LIST_DIR}/../termin-thirdparty/eigen"
    CACHE PATH
    "Path to the pinned Eigen source tree"
)
if(NOT EXISTS "${TERMIN_QOPT_EIGEN_DIR}/Eigen/Core")
    message(FATAL_ERROR
        "termin-qopt requires the pinned Eigen submodule. "
        "Run: git submodule update --init termin-thirdparty/eigen")
endif()

add_library(termin_qopt_eigen INTERFACE)
target_include_directories(termin_qopt_eigen SYSTEM INTERFACE
    "${TERMIN_QOPT_EIGEN_DIR}"
)

add_library(termin_qopt SHARED
    src/termin_qopt.cpp
)
add_library(termin_qopt::termin_qopt ALIAS termin_qopt)

target_compile_definitions(termin_qopt PRIVATE TERMIN_QOPT_EXPORTS)
target_include_directories(termin_qopt PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)
target_link_libraries(termin_qopt PRIVATE termin_qopt_eigen)

set_target_properties(termin_qopt PROPERTIES
    VERSION ${PROJECT_VERSION}
    SOVERSION 0
    WINDOWS_EXPORT_ALL_SYMBOLS OFF
)

if(COMMAND termin_set_rpath_lib)
    termin_set_rpath_lib(termin_qopt)
else()
    list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_LIST_DIR}/../cmake")
    include(TerminRpath)
    termin_set_rpath_lib(termin_qopt)
endif()

if(TERMIN_QOPT_BUILD_TESTS)
    enable_testing()

    add_executable(termin_qopt_dense_views_test
        tests/test_dense_views.cpp
    )
    target_link_libraries(termin_qopt_dense_views_test PRIVATE termin_qopt)
    add_test(NAME termin_qopt_dense_views_test COMMAND termin_qopt_dense_views_test)

    add_executable(termin_qopt_public_headers_test
        tests/test_public_headers.cpp
    )
    target_link_libraries(termin_qopt_public_headers_test PRIVATE termin_qopt)
    add_test(NAME termin_qopt_public_headers_test COMMAND termin_qopt_public_headers_test)
endif()

include(GNUInstallDirs)

install(TARGETS termin_qopt
    EXPORT termin_qoptTargets
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
)

install(DIRECTORY include/termin
    DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
)

install(EXPORT termin_qoptTargets
    FILE termin_qoptTargets.cmake
    NAMESPACE termin_qopt::
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_qopt
)

include(CMakePackageConfigHelpers)

configure_package_config_file(
    cmake/termin_qoptConfig.cmake.in
    ${CMAKE_CURRENT_BINARY_DIR}/termin_qoptConfig.cmake
    INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_qopt
)

write_basic_package_version_file(
    ${CMAKE_CURRENT_BINARY_DIR}/termin_qoptConfigVersion.cmake
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMajorVersion
)

install(FILES
    ${CMAKE_CURRENT_BINARY_DIR}/termin_qoptConfig.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/termin_qoptConfigVersion.cmake
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_qopt
)

if(COMMAND termin_label_tests_in_directory)
    termin_label_tests_in_directory("termin-qopt")
endif()
