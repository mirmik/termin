cmake_minimum_required(VERSION 3.16)
project(termin_framegraph_remote_target VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

if(COMMAND termin_require_package)
    termin_require_package(termin_base tcbase::termin_base)
    termin_require_package(termin_engine termin_engine::termin_engine)
    termin_require_package(termin_framegraph_remote termin_framegraph_remote::termin_framegraph_remote)
else()
    find_package(termin_base REQUIRED)
    find_package(termin_engine REQUIRED)
    find_package(termin_framegraph_remote REQUIRED)
endif()
find_package(Threads REQUIRED)

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_LIST_DIR}/../cmake")
include(TerminRpath)

add_library(termin_framegraph_remote_target SHARED
    src/target_service.cpp
)
add_library(termin_framegraph_remote_target::termin_framegraph_remote_target
    ALIAS termin_framegraph_remote_target)
target_compile_definitions(termin_framegraph_remote_target PRIVATE
    TERMIN_FRAMEGRAPH_REMOTE_TARGET_EXPORTS)
target_include_directories(termin_framegraph_remote_target PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_LIST_DIR}/include>
    $<INSTALL_INTERFACE:include>
)
target_link_libraries(termin_framegraph_remote_target
    PUBLIC
        termin_framegraph_remote::termin_framegraph_remote
    PRIVATE
        tcbase::termin_base
        termin_engine::termin_engine
        Threads::Threads
)
if(WIN32)
    target_compile_definitions(termin_framegraph_remote_target PRIVATE NOMINMAX)
    target_link_libraries(termin_framegraph_remote_target PRIVATE ws2_32)
endif()
termin_set_rpath_lib(termin_framegraph_remote_target)

if(MSVC)
    target_compile_options(termin_framegraph_remote_target PRIVATE /W3)
else()
    target_compile_options(termin_framegraph_remote_target PRIVATE -Wall -Wextra)
endif()

if(TERMIN_BUILD_TESTS)
    add_executable(termin_framegraph_remote_target_service_test
        tests/test_target_service.cpp
    )
    target_include_directories(termin_framegraph_remote_target_service_test PRIVATE
        ${CMAKE_CURRENT_LIST_DIR}/../termin-thirdparty/guard
    )
    target_link_libraries(termin_framegraph_remote_target_service_test PRIVATE
        termin_framegraph_remote_target
        termin_engine::termin_engine
    )
    if(WIN32)
        target_link_libraries(termin_framegraph_remote_target_service_test PRIVATE ws2_32)
    endif()
    termin_set_rpath_test(termin_framegraph_remote_target_service_test)
    add_test(NAME termin_framegraph_remote_target_service_test
        COMMAND termin_framegraph_remote_target_service_test)
    termin_label_tests_in_directory("termin-framegraph-remote-target")
endif()

include(GNUInstallDirs)
install(TARGETS termin_framegraph_remote_target
    EXPORT termin_framegraph_remote_targetTargets
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
)
install(DIRECTORY include/termin DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})
install(EXPORT termin_framegraph_remote_targetTargets
    FILE termin_framegraph_remote_targetTargets.cmake
    NAMESPACE termin_framegraph_remote_target::
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_framegraph_remote_target
)

include(CMakePackageConfigHelpers)
configure_package_config_file(
    cmake/termin_framegraph_remote_targetConfig.cmake.in
    ${CMAKE_CURRENT_BINARY_DIR}/termin_framegraph_remote_targetConfig.cmake
    INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_framegraph_remote_target
)
write_basic_package_version_file(
    ${CMAKE_CURRENT_BINARY_DIR}/termin_framegraph_remote_targetConfigVersion.cmake
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMajorVersion
)
install(FILES
    ${CMAKE_CURRENT_BINARY_DIR}/termin_framegraph_remote_targetConfig.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/termin_framegraph_remote_targetConfigVersion.cmake
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_framegraph_remote_target
)
