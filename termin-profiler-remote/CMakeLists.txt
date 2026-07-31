cmake_minimum_required(VERSION 3.16)
project(termin_profiler_remote VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

if(COMMAND termin_require_package)
    termin_require_package(termin_base tcbase::termin_base)
else()
    find_package(termin_base REQUIRED)
endif()

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_LIST_DIR}/../cmake")
include(TerminRpath)

add_library(termin_profiler_remote SHARED src/wire_codec.cpp)
add_library(termin_profiler_remote::termin_profiler_remote ALIAS termin_profiler_remote)
target_compile_definitions(termin_profiler_remote PRIVATE TERMIN_PROFILER_REMOTE_EXPORTS)
target_include_directories(termin_profiler_remote PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_LIST_DIR}/include>
    $<INSTALL_INTERFACE:include>
)
target_link_libraries(termin_profiler_remote PRIVATE tcbase::termin_base)
termin_set_rpath_lib(termin_profiler_remote)

if(MSVC)
    target_compile_options(termin_profiler_remote PRIVATE /W3)
else()
    target_compile_options(termin_profiler_remote PRIVATE -Wall -Wextra)
endif()

if(TERMIN_BUILD_TESTS)
    add_executable(termin_profiler_remote_wire_codec_test tests/test_wire_codec.cpp)
    target_include_directories(termin_profiler_remote_wire_codec_test PRIVATE
        ${CMAKE_CURRENT_LIST_DIR}/../termin-thirdparty/guard
    )
    target_link_libraries(termin_profiler_remote_wire_codec_test PRIVATE
        termin_profiler_remote
    )
    termin_set_rpath_test(termin_profiler_remote_wire_codec_test)
    add_test(NAME termin_profiler_remote_wire_codec_test
        COMMAND termin_profiler_remote_wire_codec_test)
    termin_label_tests_in_directory("termin-profiler-remote")
endif()

include(GNUInstallDirs)
install(TARGETS termin_profiler_remote
    EXPORT termin_profiler_remoteTargets
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
)
install(DIRECTORY include/termin DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})
install(EXPORT termin_profiler_remoteTargets
    FILE termin_profiler_remoteTargets.cmake
    NAMESPACE termin_profiler_remote::
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_profiler_remote
)

include(CMakePackageConfigHelpers)
configure_package_config_file(
    cmake/termin_profiler_remoteConfig.cmake.in
    ${CMAKE_CURRENT_BINARY_DIR}/termin_profiler_remoteConfig.cmake
    INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_profiler_remote
)
write_basic_package_version_file(
    ${CMAKE_CURRENT_BINARY_DIR}/termin_profiler_remoteConfigVersion.cmake
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMajorVersion
)
install(FILES
    ${CMAKE_CURRENT_BINARY_DIR}/termin_profiler_remoteConfig.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/termin_profiler_remoteConfigVersion.cmake
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_profiler_remote
)
