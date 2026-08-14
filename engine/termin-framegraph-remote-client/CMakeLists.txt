cmake_minimum_required(VERSION 3.16)
project(termin_framegraph_remote_client VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

if(COMMAND termin_require_package)
    termin_require_package(termin_base tcbase::termin_base)
    termin_require_package(termin_framegraph_remote termin_framegraph_remote::termin_framegraph_remote)
else()
    find_package(termin_base REQUIRED)
    find_package(termin_framegraph_remote REQUIRED)
endif()
find_package(Threads REQUIRED)

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_LIST_DIR}/../../cmake")
include(TerminRpath)

add_library(termin_framegraph_remote_client SHARED src/client.cpp)
add_library(termin_framegraph_remote_client::termin_framegraph_remote_client
    ALIAS termin_framegraph_remote_client)
target_compile_definitions(termin_framegraph_remote_client PRIVATE
    TERMIN_FRAMEGRAPH_REMOTE_CLIENT_EXPORTS)
target_include_directories(termin_framegraph_remote_client PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_LIST_DIR}/include>
    $<INSTALL_INTERFACE:include>
)
target_link_libraries(termin_framegraph_remote_client
    PUBLIC termin_framegraph_remote::termin_framegraph_remote
    PRIVATE tcbase::termin_base Threads::Threads
)
if(WIN32)
    target_compile_definitions(termin_framegraph_remote_client PRIVATE NOMINMAX)
    target_link_libraries(termin_framegraph_remote_client PRIVATE ws2_32)
endif()
termin_set_rpath_lib(termin_framegraph_remote_client)

if(MSVC)
    target_compile_options(termin_framegraph_remote_client PRIVATE /W3)
else()
    target_compile_options(termin_framegraph_remote_client PRIVATE -Wall -Wextra)
endif()

include(GNUInstallDirs)
install(TARGETS termin_framegraph_remote_client
    EXPORT termin_framegraph_remote_clientTargets
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
)
install(DIRECTORY include/termin DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})
install(EXPORT termin_framegraph_remote_clientTargets
    FILE termin_framegraph_remote_clientTargets.cmake
    NAMESPACE termin_framegraph_remote_client::
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_framegraph_remote_client
)

include(CMakePackageConfigHelpers)
configure_package_config_file(
    cmake/termin_framegraph_remote_clientConfig.cmake.in
    ${CMAKE_CURRENT_BINARY_DIR}/termin_framegraph_remote_clientConfig.cmake
    INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_framegraph_remote_client
)
write_basic_package_version_file(
    ${CMAKE_CURRENT_BINARY_DIR}/termin_framegraph_remote_clientConfigVersion.cmake
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMajorVersion
)
install(FILES
    ${CMAKE_CURRENT_BINARY_DIR}/termin_framegraph_remote_clientConfig.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/termin_framegraph_remote_clientConfigVersion.cmake
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_framegraph_remote_client
)
