cmake_minimum_required(VERSION 3.16)
project(termin_prefab VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

option(TERMIN_PREFAB_BUILD_TESTS "Build termin-prefab native tests" ON)
option(TERMIN_BUILD_PYTHON "Build Python bindings" OFF)

if(COMMAND termin_require_package)
    termin_require_package(termin_scene termin_scene::termin_scene)
else()
    find_package(termin_scene REQUIRED)
endif()

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_LIST_DIR}/../cmake")
include(TerminRpath)

add_library(termin_prefab SHARED
    src/prefab_document.cpp
    src/prefab_instance_state.cpp
    src/prefab_override_restore.cpp
    src/prefab_structure_reconcile.cpp
    src/prefab_instantiator.cpp
    src/prefab_override_value.cpp
)
add_library(termin_prefab::termin_prefab ALIAS termin_prefab)

target_compile_definitions(termin_prefab PRIVATE TERMIN_PREFAB_EXPORTS)
target_include_directories(termin_prefab PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)
target_link_libraries(termin_prefab PUBLIC termin_scene::termin_scene)
termin_set_rpath_lib(termin_prefab)

if(TERMIN_BUILD_PYTHON)
    find_package(Python 3.10 COMPONENTS Interpreter Development REQUIRED)
    find_package(nanobind CONFIG REQUIRED)
    nanobind_add_module(_prefab_native NB_SHARED
        cpp/bindings/prefab_module.cpp
    )
    target_link_libraries(_prefab_native PRIVATE
        termin_prefab
        termin_scene::termin_scene
    )
    termin_set_rpath_python(_prefab_native)
endif()

if(TERMIN_PREFAB_BUILD_TESTS)
    enable_testing()
    add_executable(termin_prefab_override_value_test
        tests/test_prefab_override_value.cpp
    )
    target_link_libraries(termin_prefab_override_value_test PRIVATE
        termin_prefab
    )
    set_target_properties(termin_prefab_override_value_test PROPERTIES
        RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    )
    add_test(NAME termin_prefab_override_value_test COMMAND termin_prefab_override_value_test)

    add_executable(termin_prefab_document_validation_test
        tests/test_prefab_document_validation.cpp
    )
    target_link_libraries(termin_prefab_document_validation_test PRIVATE
        termin_prefab
    )
    set_target_properties(termin_prefab_document_validation_test PROPERTIES
        RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    )
    add_test(NAME termin_prefab_document_validation_test COMMAND termin_prefab_document_validation_test)

    add_executable(termin_prefab_instantiator_test
        tests/test_prefab_instantiator.cpp
    )
    target_link_libraries(termin_prefab_instantiator_test PRIVATE
        termin_prefab
        termin_scene::termin_scene
    )
    set_target_properties(termin_prefab_instantiator_test PROPERTIES
        RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    )
    add_test(NAME termin_prefab_instantiator_test COMMAND termin_prefab_instantiator_test)
endif()

include(GNUInstallDirs)
include(CMakePackageConfigHelpers)

install(TARGETS termin_prefab
    EXPORT termin_prefabTargets
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
)
if(TERMIN_BUILD_PYTHON)
    install(TARGETS _prefab_native DESTINATION lib/python/termin/prefab)
endif()
install(DIRECTORY include/ DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})
install(EXPORT termin_prefabTargets
    FILE termin_prefabTargets.cmake
    NAMESPACE termin_prefab::
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_prefab
)
configure_package_config_file(
    cmake/termin_prefabConfig.cmake.in
    ${CMAKE_CURRENT_BINARY_DIR}/termin_prefabConfig.cmake
    INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_prefab
)
write_basic_package_version_file(
    ${CMAKE_CURRENT_BINARY_DIR}/termin_prefabConfigVersion.cmake
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMajorVersion
)
install(FILES
    ${CMAKE_CURRENT_BINARY_DIR}/termin_prefabConfig.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/termin_prefabConfigVersion.cmake
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_prefab
)

termin_label_tests_in_directory("termin-prefab")
