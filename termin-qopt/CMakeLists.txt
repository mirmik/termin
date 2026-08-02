cmake_minimum_required(VERSION 3.16)
project(termin_qopt VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

option(TERMIN_QOPT_BUILD_TESTS "Build termin-qopt native tests" OFF)

if(NOT TARGET tcbase::termin_base)
    find_package(termin_base CONFIG REQUIRED)
endif()

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
    src/active_set_qp.cpp
    src/articulation3d.cpp
    src/articulation3d_motor.cpp
    src/block_assembly.cpp
    src/contact_friction.cpp
    src/contact3d.cpp
    src/dynamics.cpp
    src/equality_qp.cpp
    src/hqp.cpp
    src/multibody2d.cpp
    src/multibody3d_contributions.cpp
    src/point_kinematics3d.cpp
    src/qp_types.cpp
    src/subspaces.cpp
    src/termin_qopt.cpp
)
add_library(termin_qopt::termin_qopt ALIAS termin_qopt)

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
    list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_LIST_DIR}/../cmake")
    include(TerminRpath)
    termin_set_rpath_lib(termin_qopt)
endif()

if(TERMIN_QOPT_BUILD_TESTS)
    enable_testing()
    find_package(Python COMPONENTS Interpreter REQUIRED)

    set(TERMIN_QOPT_GENERATED_TEST_DIR
        "${CMAKE_CURRENT_BINARY_DIR}/generated-tests"
    )
    set(TERMIN_QOPT_ORACLE_HEADER
        "${TERMIN_QOPT_GENERATED_TEST_DIR}/qp_oracle_cases.hpp"
    )
    set(TERMIN_QOPT_MULTIBODY_ORACLE_HEADER
        "${TERMIN_QOPT_GENERATED_TEST_DIR}/multibody_oracle_case.hpp"
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
    add_custom_command(
        OUTPUT "${TERMIN_QOPT_MULTIBODY_ORACLE_HEADER}"
        COMMAND ${CMAKE_COMMAND} -E make_directory
            "${TERMIN_QOPT_GENERATED_TEST_DIR}"
        COMMAND ${Python_EXECUTABLE}
            "${CMAKE_CURRENT_SOURCE_DIR}/tests/generate_multibody_oracle_header.py"
            "${CMAKE_CURRENT_SOURCE_DIR}/tests/oracle/multibody_oracle.json"
            "${TERMIN_QOPT_MULTIBODY_ORACLE_HEADER}"
        DEPENDS
            tests/generate_multibody_oracle_header.py
            tests/oracle/multibody_oracle.json
        VERBATIM
    )
    add_custom_target(termin_qopt_generate_multibody_oracle_header
        DEPENDS "${TERMIN_QOPT_MULTIBODY_ORACLE_HEADER}"
    )

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

    add_executable(termin_qopt_block_assembly_test
        tests/test_block_assembly.cpp
    )
    target_link_libraries(termin_qopt_block_assembly_test PRIVATE termin_qopt)
    add_test(NAME termin_qopt_block_assembly_test COMMAND termin_qopt_block_assembly_test)

    add_executable(termin_qopt_dynamics_test
        tests/test_dynamics.cpp
    )
    target_link_libraries(termin_qopt_dynamics_test PRIVATE termin_qopt)
    add_test(NAME termin_qopt_dynamics_test COMMAND termin_qopt_dynamics_test)

    add_executable(termin_qopt_contact_friction_test
        tests/test_contact_friction.cpp
    )
    target_link_libraries(termin_qopt_contact_friction_test PRIVATE termin_qopt)
    add_test(
        NAME termin_qopt_contact_friction_test
        COMMAND termin_qopt_contact_friction_test
    )

    add_executable(termin_qopt_multibody2d_test
        tests/test_multibody2d.cpp
    )
    target_link_libraries(termin_qopt_multibody2d_test PRIVATE termin_qopt)
    add_test(NAME termin_qopt_multibody2d_test COMMAND termin_qopt_multibody2d_test)

    add_executable(termin_qopt_multibody3d_test
        tests/test_multibody3d.cpp
    )
    add_dependencies(
        termin_qopt_multibody3d_test
        termin_qopt_generate_multibody_oracle_header
    )
    target_include_directories(termin_qopt_multibody3d_test PRIVATE
        "${TERMIN_QOPT_GENERATED_TEST_DIR}"
    )
    target_link_libraries(termin_qopt_multibody3d_test PRIVATE termin_qopt)
    add_test(NAME termin_qopt_multibody3d_test COMMAND termin_qopt_multibody3d_test)

    add_executable(termin_qopt_multibody3d_assembly_test
        tests/test_multibody3d_assembly.cpp
    )
    target_link_libraries(
        termin_qopt_multibody3d_assembly_test PRIVATE termin_qopt
    )
    add_test(
        NAME termin_qopt_multibody3d_assembly_test
        COMMAND termin_qopt_multibody3d_assembly_test
    )

    add_executable(termin_qopt_multibody3d_energy_test
        tests/test_multibody3d_energy.cpp
    )
    target_link_libraries(
        termin_qopt_multibody3d_energy_test PRIVATE termin_qopt
    )
    add_test(
        NAME termin_qopt_multibody3d_energy_test
        COMMAND termin_qopt_multibody3d_energy_test
    )

    add_executable(termin_qopt_articulation3d_test
        tests/test_articulation3d.cpp
    )
    target_link_libraries(
        termin_qopt_articulation3d_test PRIVATE termin_qopt
    )
    add_test(
        NAME termin_qopt_articulation3d_test
        COMMAND termin_qopt_articulation3d_test
    )

    add_executable(termin_qopt_articulation3d_motor_test
        tests/test_articulation3d_motor.cpp
    )
    target_link_libraries(
        termin_qopt_articulation3d_motor_test PRIVATE termin_qopt
    )
    add_test(
        NAME termin_qopt_articulation3d_motor_test
        COMMAND termin_qopt_articulation3d_motor_test
    )

    add_executable(termin_qopt_point_kinematics3d_test
        tests/test_point_kinematics3d.cpp
    )
    target_link_libraries(
        termin_qopt_point_kinematics3d_test PRIVATE termin_qopt
    )
    add_test(
        NAME termin_qopt_point_kinematics3d_test
        COMMAND termin_qopt_point_kinematics3d_test
    )

    add_executable(termin_qopt_contact3d_test
        tests/test_contact3d.cpp
    )
    target_link_libraries(
        termin_qopt_contact3d_test PRIVATE termin_qopt
    )
    add_test(
        NAME termin_qopt_contact3d_test
        COMMAND termin_qopt_contact3d_test
    )

    add_executable(termin_qopt_double_pendulum2d_test
        tests/test_double_pendulum2d.cpp
    )
    add_dependencies(
        termin_qopt_double_pendulum2d_test
        termin_qopt_generate_multibody_oracle_header
    )
    target_include_directories(termin_qopt_double_pendulum2d_test PRIVATE
        "${TERMIN_QOPT_GENERATED_TEST_DIR}"
    )
    target_link_libraries(termin_qopt_double_pendulum2d_test PRIVATE termin_qopt)
    add_test(
        NAME termin_qopt_double_pendulum2d_test
        COMMAND termin_qopt_double_pendulum2d_test
    )

    add_executable(termin_qopt_double_pendulum2d_example
        examples/double_pendulum2d.cpp
    )
    target_link_libraries(
        termin_qopt_double_pendulum2d_example PRIVATE termin_qopt
    )
    add_test(
        NAME termin_qopt_double_pendulum2d_example
        COMMAND termin_qopt_double_pendulum2d_example
    )

    add_executable(termin_qopt_equality_qp_test
        tests/test_equality_qp.cpp
    )
    add_dependencies(termin_qopt_equality_qp_test
        termin_qopt_generate_oracle_header
    )
    target_include_directories(termin_qopt_equality_qp_test PRIVATE
        "${TERMIN_QOPT_GENERATED_TEST_DIR}"
    )
    target_link_libraries(termin_qopt_equality_qp_test PRIVATE termin_qopt)
    add_test(NAME termin_qopt_equality_qp_test COMMAND termin_qopt_equality_qp_test)

    add_executable(termin_qopt_active_set_qp_test
        tests/test_active_set_qp.cpp
    )
    add_dependencies(termin_qopt_active_set_qp_test
        termin_qopt_generate_oracle_header
    )
    target_include_directories(termin_qopt_active_set_qp_test PRIVATE
        "${TERMIN_QOPT_GENERATED_TEST_DIR}"
    )
    target_link_libraries(termin_qopt_active_set_qp_test PRIVATE termin_qopt)
    add_test(NAME termin_qopt_active_set_qp_test COMMAND termin_qopt_active_set_qp_test)

    add_executable(termin_qopt_hqp_test
        tests/test_hqp.cpp
    )
    add_dependencies(termin_qopt_hqp_test
        termin_qopt_generate_oracle_header
    )
    target_include_directories(termin_qopt_hqp_test PRIVATE
        "${TERMIN_QOPT_GENERATED_TEST_DIR}"
    )
    target_link_libraries(termin_qopt_hqp_test PRIVATE termin_qopt)
    add_test(NAME termin_qopt_hqp_test COMMAND termin_qopt_hqp_test)
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
