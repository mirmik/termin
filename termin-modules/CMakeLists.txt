cmake_minimum_required(VERSION 3.16)
project(termin_modules VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

option(TERMIN_BUILD_PYTHON "Build Python/nanobind bindings" ON)
option(TERMIN_MODULES_BUILD_TESTS "Build termin-modules tests" ON)

include(GNUInstallDirs)
include(CMakePackageConfigHelpers)

if(COMMAND termin_require_package)
    termin_require_package(termin_base tcbase::termin_base)
else()
    find_package(termin_base REQUIRED)
endif()

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_LIST_DIR}/../cmake")
include(TerminRpath)

# ── Core library (pure C++, no Python dependency) ──
# SHARED to match every other termin subproject. A static core would leave
# `libtermin_modules.so` absent from sdk/lib/, breaking
# `preload_sdk_libs("termin_modules")` in the Python wrapper and forcing
# consumers to pull the core's symbols transitively through
# `libtermin_modules_python.so`.
add_library(termin_modules SHARED
    src/module_cpp_backend.cpp
    src/module_descriptor_parser.cpp
    src/module_runtime.cpp
    src/native_module_abi.cpp
    src/text_encoding.cpp
)
add_library(termin_modules::termin_modules ALIAS termin_modules)

target_compile_features(termin_modules PUBLIC cxx_std_20)
set_target_properties(termin_modules PROPERTIES
    POSITION_INDEPENDENT_CODE ON
    WINDOWS_EXPORT_ALL_SYMBOLS OFF
)
target_compile_definitions(termin_modules PRIVATE TERMIN_MODULES_EXPORTS)
termin_set_rpath_lib(termin_modules)

if(MSVC)
    target_compile_options(termin_modules PRIVATE /wd4251 /wd4275)
endif()

target_include_directories(termin_modules
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include>
)

target_link_libraries(termin_modules
    PUBLIC
        tcbase::termin_base
        ${CMAKE_DL_LIBS}
)

add_executable(termin_module_native_validator
    tools/native_validator.cpp
)
target_link_libraries(termin_module_native_validator PRIVATE termin_modules ${CMAKE_DL_LIBS})
termin_set_rpath_tool(termin_module_native_validator)
set_target_properties(termin_module_native_validator PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
)

# ── Python backend + nanobind bindings ──
if(TERMIN_BUILD_PYTHON)
    if(NOT Python_EXECUTABLE)
        if(WIN32)
            set(Python_EXECUTABLE "python")
        else()
            set(Python_EXECUTABLE "python3")
        endif()
    endif()

    find_package(Python COMPONENTS Interpreter Development REQUIRED)
    find_package(nanobind CONFIG REQUIRED)

    # Shared library: PythonModuleBackend (uses Python C API)
    add_library(termin_modules_python SHARED
        src/module_python_backend.cpp
    )
    target_link_libraries(termin_modules_python PUBLIC termin_modules Python::Python)
    target_include_directories(termin_modules_python PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include>
    )
    set_target_properties(termin_modules_python PROPERTIES
        WINDOWS_EXPORT_ALL_SYMBOLS OFF
    )
    target_compile_definitions(termin_modules_python PRIVATE TERMIN_MODULES_PYTHON_EXPORTS)
    termin_set_rpath_lib(termin_modules_python)

    # Nanobind module
    nanobind_add_module(_termin_modules_native NB_SHARED
        python/bindings/termin_modules_module.cpp
    )
    target_link_libraries(_termin_modules_native PRIVATE termin_modules_python)
    termin_set_rpath_python(_termin_modules_native)

    file(MAKE_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/python/termin_modules)
    configure_file(
        ${CMAKE_CURRENT_SOURCE_DIR}/python/termin_modules/__init__.py
        ${CMAKE_CURRENT_BINARY_DIR}/python/termin_modules/__init__.py
        COPYONLY
    )

    install(TARGETS termin_modules_python
        EXPORT termin_modulesTargets
        LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
        ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
        RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
    )
    install(TARGETS _termin_modules_native DESTINATION ${CMAKE_INSTALL_LIBDIR}/python/termin_modules)
    install(DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/python/termin_modules/
        DESTINATION ${CMAKE_INSTALL_LIBDIR}/python/termin_modules
        FILES_MATCHING PATTERN "*.py"
        PATTERN "lib" EXCLUDE
    )

    add_executable(termin_modules_example
        examples/basic/main.cpp
    )
    target_link_libraries(termin_modules_example PRIVATE termin_modules_python)
    target_compile_definitions(termin_modules_example PRIVATE
        TERMIN_MODULES_EXAMPLE_PROJECT_DIR="${CMAKE_CURRENT_SOURCE_DIR}/examples/basic/project"
    )
endif()

# ── Install core library ──
install(TARGETS termin_modules
    EXPORT termin_modulesTargets
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
)

install(TARGETS termin_module_native_validator
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
)

install(DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/include/
    DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
)

write_basic_package_version_file(
    ${CMAKE_CURRENT_BINARY_DIR}/termin_modulesConfigVersion.cmake
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMajorVersion
)

configure_package_config_file(
    ${CMAKE_CURRENT_SOURCE_DIR}/cmake/termin_modulesConfig.cmake.in
    ${CMAKE_CURRENT_BINARY_DIR}/termin_modulesConfig.cmake
    INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_modules
)

install(EXPORT termin_modulesTargets
    FILE termin_modulesTargets.cmake
    NAMESPACE termin_modules::
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_modules
)

install(FILES
    ${CMAKE_CURRENT_BINARY_DIR}/termin_modulesConfig.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/termin_modulesConfigVersion.cmake
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_modules
)

# ── Tests ──
if(TERMIN_MODULES_BUILD_TESTS)
    enable_testing()

    add_library(termin_modules_shadow_test_dependency SHARED
        tests/shadow_test_dependency.cpp
    )
    add_library(termin_modules_shadow_test_module SHARED
        tests/shadow_test_module.cpp
    )
    target_link_libraries(
        termin_modules_shadow_test_module
        PRIVATE termin_modules_shadow_test_dependency termin_modules
    )
    set_target_properties(
        termin_modules_shadow_test_module
        PROPERTIES BUILD_RPATH "$ORIGIN"
    )

    foreach(abi_case IN ITEMS missing_descriptor mismatch init_failure shutdown_retry)
        add_library(termin_modules_abi_${abi_case} SHARED
            tests/abi_contract_test_module.cpp
        )
        target_link_libraries(termin_modules_abi_${abi_case} PRIVATE termin_modules)
        string(TOUPPER "${abi_case}" abi_case_upper)
        target_compile_definitions(termin_modules_abi_${abi_case} PRIVATE
            "TERMIN_ABI_TEST_${abi_case_upper}=1"
        )
        set_target_properties(termin_modules_abi_${abi_case} PROPERTIES
            LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
            RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
            ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
        )
        termin_set_rpath_lib(termin_modules_abi_${abi_case})
    endforeach()

    add_executable(termin_modules_runtime_test
        tests/test_module_runtime.cpp
    )

    target_include_directories(termin_modules_runtime_test PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/../termin-thirdparty/guard
    )

    target_link_libraries(termin_modules_runtime_test PRIVATE termin_modules)
    add_dependencies(
        termin_modules_runtime_test
        termin_module_native_validator
        termin_modules_shadow_test_module
        termin_modules_abi_missing_descriptor
        termin_modules_abi_mismatch
        termin_modules_abi_init_failure
        termin_modules_abi_shutdown_retry
    )
    target_compile_definitions(termin_modules_runtime_test PRIVATE
        TERMIN_MODULES_TEST_BUILD_ROOT="${CMAKE_BINARY_DIR}"
        TERMIN_MODULES_TEST_CXX_COMPILER="${CMAKE_CXX_COMPILER}"
        TERMIN_MODULES_TEST_SHADOW_MODULE="$<TARGET_FILE:termin_modules_shadow_test_module>"
        TERMIN_MODULES_TEST_SHADOW_DEPENDENCY="$<TARGET_FILE:termin_modules_shadow_test_dependency>"
        TERMIN_MODULES_TEST_ABI_MISSING="$<TARGET_FILE:termin_modules_abi_missing_descriptor>"
        TERMIN_MODULES_TEST_ABI_MISMATCH="$<TARGET_FILE:termin_modules_abi_mismatch>"
        TERMIN_MODULES_TEST_ABI_INIT_FAILURE="$<TARGET_FILE:termin_modules_abi_init_failure>"
        TERMIN_MODULES_TEST_ABI_SHUTDOWN_RETRY="$<TARGET_FILE:termin_modules_abi_shutdown_retry>"
    )
    set_target_properties(termin_modules_runtime_test PROPERTIES
        RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    )

    add_test(NAME termin_modules_runtime_test COMMAND termin_modules_runtime_test)
endif()
