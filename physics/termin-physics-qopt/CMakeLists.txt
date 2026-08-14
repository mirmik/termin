cmake_minimum_required(VERSION 3.16)
project(termin_physics_qopt VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)


if(COMMAND termin_require_package)
    termin_require_package(termin_base tcbase::termin_base)
    termin_require_package(termin_qopt termin_qopt::termin_qopt)
    termin_require_package(termin_robotics termin_robotics::termin_robotics)
else()
    find_package(termin_base CONFIG REQUIRED)
    find_package(termin_qopt CONFIG REQUIRED)
    find_package(termin_robotics CONFIG REQUIRED)
endif()

add_library(termin_physics_qopt SHARED
    src/articulation3d_dynamics.cpp
    src/articulation3d_motor.cpp
    src/contact3d.cpp
    src/contact_friction.cpp
    src/dynamics.cpp
    src/dynamics_topology.cpp
    src/multibody2d.cpp
    src/multibody3d_contributions.cpp
    src/point_kinematics3d.cpp
    src/robotics_control.cpp
)
add_library(termin_physics_qopt::termin_physics_qopt ALIAS termin_physics_qopt)
target_compile_features(termin_physics_qopt PUBLIC cxx_std_20)
target_compile_definitions(termin_physics_qopt PRIVATE TERMIN_PHYSICS_QOPT_EXPORTS)
target_include_directories(termin_physics_qopt PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)
target_link_libraries(termin_physics_qopt PUBLIC
    tcbase::termin_base
    termin_qopt::termin_qopt
    termin_robotics::termin_robotics
)
set_target_properties(termin_physics_qopt PROPERTIES
    VERSION ${PROJECT_VERSION}
    SOVERSION 0
    WINDOWS_EXPORT_ALL_SYMBOLS OFF
)

if(COMMAND termin_set_rpath_lib)
    termin_set_rpath_lib(termin_physics_qopt)
else()
    list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_LIST_DIR}/../../cmake")
    include(TerminRpath)
    termin_set_rpath_lib(termin_physics_qopt)
endif()

if(TERMIN_BUILD_TESTS)
    enable_testing()
    find_package(Python COMPONENTS Interpreter REQUIRED)

    set(TERMIN_PHYSICS_QOPT_GENERATED_TEST_DIR
        "${CMAKE_CURRENT_BINARY_DIR}/generated-tests"
    )
    set(TERMIN_PHYSICS_QOPT_MULTIBODY_ORACLE_HEADER
        "${TERMIN_PHYSICS_QOPT_GENERATED_TEST_DIR}/multibody_oracle_case.hpp"
    )
    add_custom_command(
        OUTPUT "${TERMIN_PHYSICS_QOPT_MULTIBODY_ORACLE_HEADER}"
        COMMAND ${CMAKE_COMMAND} -E make_directory
            "${TERMIN_PHYSICS_QOPT_GENERATED_TEST_DIR}"
        COMMAND ${Python_EXECUTABLE}
            "${CMAKE_CURRENT_SOURCE_DIR}/tests/generate_multibody_oracle_header.py"
            "${CMAKE_CURRENT_SOURCE_DIR}/tests/multibody_oracle.json"
            "${TERMIN_PHYSICS_QOPT_MULTIBODY_ORACLE_HEADER}"
        DEPENDS
            tests/generate_multibody_oracle_header.py
            tests/multibody_oracle.json
        VERBATIM
    )
    add_custom_target(termin_physics_qopt_generate_multibody_oracle_header
        DEPENDS "${TERMIN_PHYSICS_QOPT_MULTIBODY_ORACLE_HEADER}"
    )

    function(termin_physics_qopt_add_test suffix)
        set(_target "termin_physics_qopt_${suffix}_test")
        add_executable(${_target} "tests/test_${suffix}.cpp")
        target_link_libraries(${_target} PRIVATE termin_physics_qopt)
        add_test(NAME ${_target} COMMAND ${_target})
    endfunction()

    foreach(_test IN ITEMS
            dynamics
            contact_friction
            multibody2d
            multibody3d
            multibody3d_assembly
            multibody3d_energy
            articulation3d
            articulation3d_motor
            point_kinematics3d
            contact3d
            double_pendulum2d)
        termin_physics_qopt_add_test(${_test})
    endforeach()

    foreach(_target IN ITEMS
            termin_physics_qopt_multibody3d_test
            termin_physics_qopt_double_pendulum2d_test)
        add_dependencies(${_target}
            termin_physics_qopt_generate_multibody_oracle_header)
        target_include_directories(${_target} PRIVATE
            "${TERMIN_PHYSICS_QOPT_GENERATED_TEST_DIR}")
    endforeach()

    add_executable(termin_physics_qopt_double_pendulum2d_example
        examples/double_pendulum2d.cpp)
    target_link_libraries(termin_physics_qopt_double_pendulum2d_example PRIVATE
        termin_physics_qopt)
    add_test(NAME termin_physics_qopt_double_pendulum2d_example
        COMMAND termin_physics_qopt_double_pendulum2d_example)

    add_executable(termin_physics_qopt_dynamic_joint_control_example
        examples/dynamic_joint_control.cpp)
    target_link_libraries(termin_physics_qopt_dynamic_joint_control_example
        PRIVATE termin_physics_qopt)
    add_test(NAME termin_physics_qopt_dynamic_joint_control_example
        COMMAND termin_physics_qopt_dynamic_joint_control_example)
endif()

include(GNUInstallDirs)
install(TARGETS termin_physics_qopt
    EXPORT termin_physics_qoptTargets
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
)
install(DIRECTORY include/termin DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})
install(EXPORT termin_physics_qoptTargets
    FILE termin_physics_qoptTargets.cmake
    NAMESPACE termin_physics_qopt::
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_physics_qopt
)

include(CMakePackageConfigHelpers)
configure_package_config_file(
    cmake/termin_physics_qoptConfig.cmake.in
    ${CMAKE_CURRENT_BINARY_DIR}/termin_physics_qoptConfig.cmake
    INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_physics_qopt
)
write_basic_package_version_file(
    ${CMAKE_CURRENT_BINARY_DIR}/termin_physics_qoptConfigVersion.cmake
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMajorVersion
)
install(FILES
    ${CMAKE_CURRENT_BINARY_DIR}/termin_physics_qoptConfig.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/termin_physics_qoptConfigVersion.cmake
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_physics_qopt
)

if(COMMAND termin_label_tests_in_directory)
    termin_label_tests_in_directory("termin-physics-qopt")
endif()
