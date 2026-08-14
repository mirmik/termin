cmake_minimum_required(VERSION 3.16)
project(termin_qopt VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)


if(NOT TARGET tcbase::termin_base)
    find_package(termin_base CONFIG REQUIRED)
endif()

set(TERMIN_QOPT_EIGEN_DIR
    "${CMAKE_CURRENT_LIST_DIR}/../../termin-thirdparty/eigen"
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
    src/active_set_qp.cpp
    src/block_assembly.cpp
    src/equality_qp.cpp
    src/hqp.cpp
    src/qp_types.cpp
    src/subspaces.cpp
    src/termin_qopt.cpp
)
add_library(termin_qopt::termin_qopt ALIAS termin_qopt)
target_compile_features(termin_qopt PUBLIC cxx_std_20)

target_compile_definitions(termin_qopt PRIVATE TERMIN_QOPT_EXPORTS)
target_include_directories(termin_qopt PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)
target_link_libraries(termin_qopt
    PUBLIC tcbase::termin_base
    PRIVATE termin_qopt_eigen
)

set_target_properties(termin_qopt PROPERTIES
    VERSION ${PROJECT_VERSION}
    SOVERSION 0
    WINDOWS_EXPORT_ALL_SYMBOLS OFF
)

if(COMMAND termin_set_rpath_lib)
    termin_set_rpath_lib(termin_qopt)
else()
    list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_LIST_DIR}/../../cmake")
    include(TerminRpath)
    termin_set_rpath_lib(termin_qopt)
endif()

if(TERMIN_BUILD_TESTS)
    enable_testing()
    find_package(Python COMPONENTS Interpreter REQUIRED)

    set(TERMIN_QOPT_GENERATED_TEST_DIR
        "${CMAKE_CURRENT_BINARY_DIR}/generated-tests"
    )
    set(TERMIN_QOPT_ORACLE_HEADER
        "${TERMIN_QOPT_GENERATED_TEST_DIR}/qp_oracle_cases.hpp"
    )
    add_custom_command(
        OUTPUT "${TERMIN_QOPT_ORACLE_HEADER}"
        COMMAND ${CMAKE_COMMAND} -E make_directory
            "${TERMIN_QOPT_GENERATED_TEST_DIR}"
        COMMAND ${Python_EXECUTABLE}
            "${CMAKE_CURRENT_SOURCE_DIR}/tests/generate_qp_oracle_header.py"
            "${CMAKE_CURRENT_SOURCE_DIR}/tests/oracle/solver_oracle.json"
            "${TERMIN_QOPT_ORACLE_HEADER}"
        DEPENDS
            tests/generate_qp_oracle_header.py
            tests/oracle/solver_oracle.json
        VERBATIM
    )
    add_custom_target(termin_qopt_generate_oracle_header
        DEPENDS "${TERMIN_QOPT_ORACLE_HEADER}"
    )

    function(termin_qopt_add_test target source)
        add_executable(${target} ${source})
        target_link_libraries(${target} PRIVATE termin_qopt)
        add_test(NAME ${target} COMMAND ${target})
    endfunction()

    termin_qopt_add_test(termin_qopt_dense_views_test tests/test_dense_views.cpp)
    termin_qopt_add_test(termin_qopt_public_headers_test tests/test_public_headers.cpp)
    termin_qopt_add_test(termin_qopt_block_assembly_test tests/test_block_assembly.cpp)

    foreach(_target IN ITEMS equality_qp active_set_qp hqp)
        set(_test_target "termin_qopt_${_target}_test")
        termin_qopt_add_test(${_test_target} "tests/test_${_target}.cpp")
        add_dependencies(${_test_target} termin_qopt_generate_oracle_header)
        target_include_directories(${_test_target} PRIVATE
            "${TERMIN_QOPT_GENERATED_TEST_DIR}"
        )
    endforeach()
endif()

include(GNUInstallDirs)

install(TARGETS termin_qopt
    EXPORT termin_qoptTargets
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
)
install(DIRECTORY include/termin DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})
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
