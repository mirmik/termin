cmake_minimum_required(VERSION 3.16)
project(termin_input VERSION 0.1.0 LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

option(TERMIN_BUILD_PYTHON "Build Python-related input bridge code" OFF)
option(TERMIN_INPUT_BUILD_TESTS "Build termin-input tests" ON)

if(COMMAND termin_require_package)
    termin_require_package(termin_base tcbase::termin_base)
else()
    find_package(termin_base REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_scene termin_scene::termin_scene)
else()
    find_package(termin_scene REQUIRED)
endif()

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_LIST_DIR}/../cmake")
include(TerminRpath)

set(TERMIN_INPUT_SOURCES
    src/tc_input_capability.c
    src/tc_input_component.c
    src/tc_input_scene.c
    src/tc_input_entity_pool.c
    src/tc_component_python_input.c
)

set(TERMIN_INPUT_CXX_SOURCES
    src/input_device_registry.cpp
    src/xr_input.cpp
    cpp/entity/input_handler.cpp
)

add_library(termin_input SHARED
    ${TERMIN_INPUT_SOURCES}
    ${TERMIN_INPUT_CXX_SOURCES}
)
add_library(termin_input::termin_input ALIAS termin_input)

target_compile_definitions(termin_input PRIVATE TERMIN_INPUT_EXPORTS TC_EXPORTS)

target_include_directories(termin_input
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include>
)

target_link_libraries(termin_input
    PUBLIC
        tcbase::termin_base
        termin_scene::termin_scene
)

termin_set_rpath_lib(termin_input)

if(TERMIN_BUILD_PYTHON)
    if(NOT Python_EXECUTABLE)
        if(WIN32)
            set(Python_EXECUTABLE "python")
        else()
            set(Python_EXECUTABLE "python3")
        endif()
    endif()
    find_package(Python 3.14 COMPONENTS Interpreter Development REQUIRED)
    find_package(nanobind CONFIG REQUIRED)

    nanobind_add_module(_input_native NB_SHARED
        cpp/bindings/input_module.cpp
    )
    target_link_libraries(_input_native PRIVATE termin_input)

    termin_set_rpath_python(_input_native)

    install(TARGETS _input_native DESTINATION lib/python/termin/input)
    install(DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/python/termin/input/
        DESTINATION lib/python/termin/input
        PATTERN "__pycache__" EXCLUDE
        PATTERN "*.pyc" EXCLUDE
        PATTERN "lib" EXCLUDE
    )
endif()

if(TERMIN_INPUT_BUILD_TESTS)
    enable_testing()

    add_executable(termin_input_capability_test tests/test_input_capability.c)
    target_include_directories(termin_input_capability_test PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/../termin-thirdparty/guard
    )
    target_link_libraries(termin_input_capability_test PRIVATE termin_input)
    add_test(NAME termin_input_capability_test COMMAND termin_input_capability_test)
    set_target_properties(termin_input_capability_test
        PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    )
endif()

include(GNUInstallDirs)
include(CMakePackageConfigHelpers)

install(TARGETS termin_input
    EXPORT termin_inputTargets
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
)

install(DIRECTORY include/
    DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
)

install(EXPORT termin_inputTargets
    FILE termin_inputTargets.cmake
    NAMESPACE termin_input::
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_input
)

configure_package_config_file(
    ${CMAKE_CURRENT_SOURCE_DIR}/cmake/termin_inputConfig.cmake.in
    ${CMAKE_CURRENT_BINARY_DIR}/termin_inputConfig.cmake
    INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_input
)

write_basic_package_version_file(
    ${CMAKE_CURRENT_BINARY_DIR}/termin_inputConfigVersion.cmake
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMajorVersion
)

install(FILES
    ${CMAKE_CURRENT_BINARY_DIR}/termin_inputConfig.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/termin_inputConfigVersion.cmake
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_input
)

termin_label_tests_in_directory("termin-input")
