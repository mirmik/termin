cmake_minimum_required(VERSION 3.16)
project(termin_robotics VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

option(TERMIN_ROBOTICS_BUILD_PYTHON "Build termin-robotics Python bindings" ${TERMIN_BUILD_PYTHON})

if(COMMAND termin_require_package)
    termin_require_package(termin_base tcbase::termin_base)
    termin_require_package(termin_qopt termin_qopt::termin_qopt)
else()
    find_package(termin_base CONFIG REQUIRED)
    find_package(termin_qopt CONFIG REQUIRED)
endif()

add_library(termin_robotics SHARED
    src/articulation3d.cpp
    src/tasks.cpp
    src/velocity_control.cpp
    src/inverse_dynamics_control.cpp
)
add_library(termin_robotics::termin_robotics ALIAS termin_robotics)
target_compile_features(termin_robotics PUBLIC cxx_std_20)
target_compile_definitions(termin_robotics PRIVATE TERMIN_ROBOTICS_EXPORTS)
target_include_directories(termin_robotics PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)
target_link_libraries(termin_robotics PUBLIC
    tcbase::termin_base
    termin_qopt::termin_qopt
)
set_target_properties(termin_robotics PROPERTIES
    VERSION ${PROJECT_VERSION}
    SOVERSION 0
    WINDOWS_EXPORT_ALL_SYMBOLS OFF
)

if(COMMAND termin_set_rpath_lib)
    termin_set_rpath_lib(termin_robotics)
else()
    list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_LIST_DIR}/../../cmake")
    include(TerminRpath)
    termin_set_rpath_lib(termin_robotics)
endif()

if(TERMIN_BUILD_TESTS)
    enable_testing()
    add_executable(termin_robotics_articulation3d_test
        tests/test_articulation3d.cpp
    )
    target_link_libraries(termin_robotics_articulation3d_test PRIVATE
        termin_robotics
    )
    add_test(NAME termin_robotics_articulation3d_test
        COMMAND termin_robotics_articulation3d_test)

    add_executable(termin_robotics_tasks_test
        tests/test_tasks.cpp
    )
    target_link_libraries(termin_robotics_tasks_test PRIVATE
        termin_robotics
    )
    add_test(NAME termin_robotics_tasks_test
        COMMAND termin_robotics_tasks_test)

    add_executable(termin_robotics_velocity_control_test
        tests/test_velocity_control.cpp
    )
    target_link_libraries(termin_robotics_velocity_control_test PRIVATE
        termin_robotics
    )
    add_test(NAME termin_robotics_velocity_control_test
        COMMAND termin_robotics_velocity_control_test)

    add_executable(termin_robotics_inverse_dynamics_control_test
        tests/test_inverse_dynamics_control.cpp
    )
    target_link_libraries(termin_robotics_inverse_dynamics_control_test PRIVATE
        termin_robotics
    )
    add_test(NAME termin_robotics_inverse_dynamics_control_test
        COMMAND termin_robotics_inverse_dynamics_control_test)

    add_executable(termin_robotics_kinematic_point_control_example
        examples/kinematic_point_control.cpp)
    target_link_libraries(termin_robotics_kinematic_point_control_example
        PRIVATE termin_robotics)
    add_test(NAME termin_robotics_kinematic_point_control_example
        COMMAND termin_robotics_kinematic_point_control_example)
endif()

if(TERMIN_ROBOTICS_BUILD_PYTHON)
    find_package(Python 3.14 COMPONENTS Interpreter Development REQUIRED)
    find_package(nanobind CONFIG REQUIRED)
    nanobind_add_module(_robotics_native NB_SHARED python/robotics_bindings.cpp)
    target_link_libraries(_robotics_native PRIVATE termin_robotics)
    install(TARGETS _robotics_native DESTINATION lib/python/termin/robotics)
    install(DIRECTORY python/termin/robotics/
        DESTINATION lib/python/termin/robotics
        PATTERN "__pycache__" EXCLUDE
        PATTERN "*.pyc" EXCLUDE)
endif()

include(GNUInstallDirs)
install(TARGETS termin_robotics
    EXPORT termin_roboticsTargets
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
)
install(DIRECTORY include/termin DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})
install(EXPORT termin_roboticsTargets
    FILE termin_roboticsTargets.cmake
    NAMESPACE termin_robotics::
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_robotics
)

include(CMakePackageConfigHelpers)
configure_package_config_file(
    cmake/termin_roboticsConfig.cmake.in
    ${CMAKE_CURRENT_BINARY_DIR}/termin_roboticsConfig.cmake
    INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_robotics
)
write_basic_package_version_file(
    ${CMAKE_CURRENT_BINARY_DIR}/termin_roboticsConfigVersion.cmake
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMajorVersion
)
install(FILES
    ${CMAKE_CURRENT_BINARY_DIR}/termin_roboticsConfig.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/termin_roboticsConfigVersion.cmake
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_robotics
)

if(COMMAND termin_label_tests_in_directory)
    termin_label_tests_in_directory("termin-robotics")
endif()
