cmake_minimum_required(VERSION 3.14)
project(termin_runtime VERSION 0.1.0 LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
option(TERMIN_RUNTIME_MINIMAL_ONLY
    "Build the core package-v2 loader without desktop resource domains"
    OFF)
option(TERMIN_RUNTIME_RENDER_ONLY
    "Build the portable package-v2 scene/render resource profile"
    ${TERMIN_PLATFORM_WEB})
option(TERMIN_BUILD_PYTHON "Build optional Python/nanobind runtime adapters" OFF)

if(COMMAND termin_require_package)
    termin_require_package(termin_base tcbase::termin_base)
else()
    find_package(termin_base REQUIRED)
endif()
if(NOT TERMIN_RUNTIME_MINIMAL_ONLY)
if(COMMAND termin_require_package)
    termin_require_package(termin_graphics tgfx::termin_graphics tgfx::termin_graphics2)
else()
    find_package(termin_graphics REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_image termin_image::termin_image)
else()
    find_package(termin_image REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_mesh tmesh::termin_mesh)
else()
    find_package(termin_mesh REQUIRED)
endif()
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_scene termin_scene::termin_scene)
else()
    find_package(termin_scene REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_inspect termin_inspect::termin_inspect)
else()
    find_package(termin_inspect REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_bootstrap termin_bootstrap::termin_bootstrap)
else()
    find_package(termin_bootstrap REQUIRED)
endif()
if(NOT TERMIN_RUNTIME_MINIMAL_ONLY)
if(COMMAND termin_require_package)
    termin_require_package(termin_render termin_render::termin_render)
else()
    find_package(termin_render REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_engine termin_engine::termin_engine)
else()
    find_package(termin_engine REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_components_mesh termin_components_mesh::termin_components_mesh)
else()
    find_package(termin_components_mesh REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_components_render termin_components_render::termin_components_render)
else()
    find_package(termin_components_render REQUIRED)
endif()
if(NOT TERMIN_RUNTIME_RENDER_ONLY AND COMMAND termin_require_package)
    termin_require_package(termin_components_foliage termin_components_foliage::termin_components_foliage)
elseif(NOT TERMIN_RUNTIME_RENDER_ONLY)
    find_package(termin_components_foliage REQUIRED)
endif()
if(NOT TERMIN_RUNTIME_RENDER_ONLY AND COMMAND termin_require_package)
    termin_require_package(
        termin_gui_native
        termin_gui_native::termin_gui_native)
elseif(NOT TERMIN_RUNTIME_RENDER_ONLY)
    find_package(termin_gui_native REQUIRED)
endif()
endif()

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_LIST_DIR}/../../cmake")
include(TerminRpath)

set(TERMIN_RUNTIME_SOURCES
    src/runtime_package.cpp
    src/runtime_package_reader.cpp
    src/runtime_shader_inference.cpp
)
if(TERMIN_RUNTIME_MINIMAL_ONLY)
    set(TERMIN_RUNTIME_SOURCES
        src/runtime_package_minimal.cpp
        src/runtime_package_reader.cpp)
endif()
set(TERMIN_RUNTIME_LIBRARY_TYPE SHARED)
if(EMSCRIPTEN)
    set(TERMIN_RUNTIME_LIBRARY_TYPE STATIC)
endif()
add_library(termin_runtime ${TERMIN_RUNTIME_LIBRARY_TYPE} ${TERMIN_RUNTIME_SOURCES})
add_library(termin_runtime::termin_runtime ALIAS termin_runtime)

set_target_properties(termin_runtime PROPERTIES
    POSITION_INDEPENDENT_CODE ON
    WINDOWS_EXPORT_ALL_SYMBOLS OFF
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
)
termin_set_rpath_lib(termin_runtime)

target_compile_definitions(termin_runtime PRIVATE TERMIN_RUNTIME_EXPORTS)
if(TERMIN_RUNTIME_MINIMAL_ONLY)
    target_compile_definitions(termin_runtime PUBLIC TERMIN_RUNTIME_MINIMAL_ONLY)
endif()
if(TERMIN_RUNTIME_RENDER_ONLY)
    target_compile_definitions(termin_runtime PUBLIC TERMIN_RUNTIME_RENDER_ONLY)
endif()

target_include_directories(termin_runtime
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_LIST_DIR}/include>
        $<INSTALL_INTERFACE:include>
)

target_link_libraries(termin_runtime PUBLIC
        tcbase::termin_base
        termin_inspect::termin_inspect
        termin_scene::termin_scene
        termin_bootstrap::termin_bootstrap
)
if(NOT TERMIN_RUNTIME_MINIMAL_ONLY)
target_link_libraries(termin_runtime PUBLIC
        tgfx::termin_graphics
        tgfx::termin_graphics2
        tmesh::termin_mesh
        termin_render::termin_render
        termin_engine::termin_engine
        termin_components_mesh::termin_components_mesh
        termin_components_render::termin_components_render
    PRIVATE
        termin_image::termin_image
)
if(NOT TERMIN_RUNTIME_RENDER_ONLY)
target_link_libraries(termin_runtime PUBLIC
        termin_components_foliage::termin_components_foliage
        termin_gui_native::termin_gui_native
)
endif()
endif()

if(MSVC)
    target_compile_options(termin_runtime PRIVATE /W3 /wd4251 /wd4275)
else()
    target_compile_options(termin_runtime PRIVATE -Wall -Wextra)
endif()
if(EMSCRIPTEN)
    target_compile_options(termin_runtime PRIVATE -fexceptions)
endif()

if(TERMIN_BUILD_PYTHON)
    install(DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/python/termin/runtime/
        DESTINATION lib/python/termin/runtime
        PATTERN "__pycache__" EXCLUDE
        PATTERN "*.pyc" EXCLUDE
        PATTERN "lib" EXCLUDE
    )
endif()

if(TERMIN_BUILD_TESTS AND NOT TERMIN_RUNTIME_MINIMAL_ONLY)
    enable_testing()

    add_executable(termin_runtime_package_loader_test
        tests/test_runtime_package_loader.cpp
    )
    find_program(TERMIN_RUNTIME_TEST_PYTHON NAMES python3 python REQUIRED)
    set(TERMIN_RUNTIME_READER_FIXTURE_ROOT
        "${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/reader-package")
    set(TERMIN_RUNTIME_READER_FIXTURE_BLOB
        "${CMAKE_CURRENT_BINARY_DIR}/reader-package.trpkg")
    add_custom_command(
        OUTPUT "${TERMIN_RUNTIME_READER_FIXTURE_BLOB}"
        COMMAND "${TERMIN_RUNTIME_TEST_PYTHON}"
            "${CMAKE_CURRENT_SOURCE_DIR}/../../editor/termin-project-build/python/termin/project_build/runtime_package_blob.py"
            "${TERMIN_RUNTIME_READER_FIXTURE_ROOT}"
            "${TERMIN_RUNTIME_READER_FIXTURE_BLOB}"
        DEPENDS
            "${CMAKE_CURRENT_SOURCE_DIR}/../../editor/termin-project-build/python/termin/project_build/runtime_package_blob.py"
            "${TERMIN_RUNTIME_READER_FIXTURE_ROOT}/manifest.json"
            "${TERMIN_RUNTIME_READER_FIXTURE_ROOT}/scenes/Main.scene.json"
        VERBATIM)
    add_custom_target(termin_runtime_reader_fixture
        DEPENDS "${TERMIN_RUNTIME_READER_FIXTURE_BLOB}")
    add_dependencies(
        termin_runtime_package_loader_test
        termin_runtime_reader_fixture)
    target_compile_definitions(termin_runtime_package_loader_test PRIVATE
        TERMIN_RUNTIME_READER_FIXTURE_ROOT="${TERMIN_RUNTIME_READER_FIXTURE_ROOT}"
        TERMIN_RUNTIME_READER_FIXTURE_BLOB="${TERMIN_RUNTIME_READER_FIXTURE_BLOB}")
    target_include_directories(termin_runtime_package_loader_test PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/../../termin-thirdparty/guard
    )
    target_link_libraries(termin_runtime_package_loader_test PRIVATE
        termin_runtime
        termin_image::termin_image
    )
    set_target_properties(termin_runtime_package_loader_test PROPERTIES
        RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    )
    add_test(NAME termin_runtime_package_loader_test COMMAND termin_runtime_package_loader_test)
endif()

if(NOT EMSCRIPTEN)
install(TARGETS termin_runtime
    EXPORT termin_runtimeTargets
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
    RUNTIME DESTINATION bin
)

install(DIRECTORY include/
    DESTINATION include
)

install(EXPORT termin_runtimeTargets
    FILE termin_runtimeTargets.cmake
    NAMESPACE termin_runtime::
    DESTINATION lib/cmake/termin_runtime
)

include(CMakePackageConfigHelpers)

set(TERMIN_RUNTIME_CONFIG_FIND_FULL_DEPS "")
if(NOT TERMIN_RUNTIME_MINIMAL_ONLY)
    set(TERMIN_RUNTIME_CONFIG_FIND_FULL_DEPS
"find_dependency(termin_graphics REQUIRED)
find_dependency(termin_mesh REQUIRED)
find_dependency(termin_render REQUIRED)
find_dependency(termin_engine REQUIRED)
find_dependency(termin_components_mesh REQUIRED)
find_dependency(termin_components_render REQUIRED)
find_dependency(termin_components_foliage REQUIRED)
find_dependency(termin_gui_native REQUIRED COMPONENTS core)")
endif()

configure_package_config_file(
    ${CMAKE_CURRENT_LIST_DIR}/cmake/termin_runtimeConfig.cmake.in
    ${CMAKE_CURRENT_BINARY_DIR}/termin_runtimeConfig.cmake
    INSTALL_DESTINATION lib/cmake/termin_runtime
)

write_basic_package_version_file(
    ${CMAKE_CURRENT_BINARY_DIR}/termin_runtimeConfigVersion.cmake
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMajorVersion
)

install(FILES
    ${CMAKE_CURRENT_BINARY_DIR}/termin_runtimeConfig.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/termin_runtimeConfigVersion.cmake
    DESTINATION lib/cmake/termin_runtime
)
endif()

termin_label_tests_in_directory("termin-runtime")
