cmake_minimum_required(VERSION 3.16)
project(termin_audio VERSION 0.1.0 LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

option(TERMIN_BUILD_PYTHON "Build termin-audio Python bindings" OFF)
option(TERMIN_AUDIO_BUILD_TESTS "Build termin-audio native tests" ON)

if(COMMAND termin_require_package)
    termin_require_package(termin_base tcbase::termin_base)
else()
    find_package(termin_base REQUIRED)
endif()
find_package(Threads REQUIRED)

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_LIST_DIR}/../cmake")
include(TerminRpath)

set(TERMIN_MINIAUDIO_DIR "${CMAKE_CURRENT_LIST_DIR}/../termin-thirdparty/miniaudio")

add_library(termin_audio SHARED
    src/tc_audio_clip_registry.c
    src/tc_audio_decode.c
    src/tc_audio_engine.c
    src/tc_audio_runtime.c
    ${TERMIN_MINIAUDIO_DIR}/miniaudio.c
)
add_library(termin_audio::termin_audio ALIAS termin_audio)

target_compile_definitions(termin_audio
    PRIVATE
        TERMIN_AUDIO_EXPORTS
        MA_NO_RESOURCE_MANAGER
        MA_NO_ENCODING
        MA_NO_GENERATION
)
target_include_directories(termin_audio
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include>
    PRIVATE
        ${TERMIN_MINIAUDIO_DIR}
)
target_link_libraries(termin_audio
    PUBLIC tcbase::termin_base
    PRIVATE Threads::Threads ${CMAKE_DL_LIBS}
)
if(UNIX AND NOT APPLE)
    target_link_libraries(termin_audio PRIVATE m)
endif()

set_target_properties(termin_audio PROPERTIES
    VERSION ${PROJECT_VERSION}
    SOVERSION 0
)
termin_set_rpath_lib(termin_audio)

if(TERMIN_BUILD_PYTHON)
    find_package(Python 3.8 COMPONENTS Interpreter Development REQUIRED)
    find_package(nanobind CONFIG REQUIRED)
    nanobind_add_module(_audio_native NB_SHARED
        cpp/bindings/audio_module.cpp
    )
    target_link_libraries(_audio_native PRIVATE termin_audio)
    target_include_directories(_audio_native PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/include)
    termin_set_rpath_python(_audio_native)
endif()

if(TERMIN_AUDIO_BUILD_TESTS)
    enable_testing()
    add_executable(termin_audio_runtime_test tests/test_audio_runtime.cpp)
    target_include_directories(termin_audio_runtime_test PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/../termin-thirdparty/guard
    )
    target_link_libraries(termin_audio_runtime_test PRIVATE termin_audio)
    set_target_properties(termin_audio_runtime_test PROPERTIES
        RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    )
    termin_set_rpath_test(termin_audio_runtime_test)
    add_test(NAME termin_audio_runtime_test COMMAND termin_audio_runtime_test)
    if(COMMAND termin_label_tests_in_directory)
        termin_label_tests_in_directory("termin-audio")
    endif()
endif()

include(GNUInstallDirs)
include(CMakePackageConfigHelpers)

install(TARGETS termin_audio
    EXPORT termin_audioTargets
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
)
if(TERMIN_BUILD_PYTHON)
    install(TARGETS _audio_native DESTINATION lib/python/termin/audio)
    install(DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/python/termin/audio/
        DESTINATION lib/python/termin/audio
        PATTERN "__pycache__" EXCLUDE
        PATTERN "*.pyc" EXCLUDE
    )
endif()
install(DIRECTORY include/termin DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})
install(EXPORT termin_audioTargets
    FILE termin_audioTargets.cmake
    NAMESPACE termin_audio::
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_audio
)

configure_package_config_file(
    cmake/termin_audioConfig.cmake.in
    ${CMAKE_CURRENT_BINARY_DIR}/termin_audioConfig.cmake
    INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_audio
)
write_basic_package_version_file(
    ${CMAKE_CURRENT_BINARY_DIR}/termin_audioConfigVersion.cmake
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMajorVersion
)
install(FILES
    ${CMAKE_CURRENT_BINARY_DIR}/termin_audioConfig.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/termin_audioConfigVersion.cmake
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_audio
)
