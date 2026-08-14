cmake_minimum_required(VERSION 3.16)
project(termin_frame_profiler VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

if(COMMAND termin_require_package)
    termin_require_package(termin_gui_native termin_gui_native::termin_gui_native)
    termin_require_package(termin_profiler_remote termin_profiler_remote::termin_profiler_remote)
else()
    find_package(termin_gui_native REQUIRED)
    find_package(termin_profiler_remote REQUIRED)
endif()

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_LIST_DIR}/../../cmake")
include(TerminRpath)

add_library(termin_frame_profiler SHARED
    src/frame_profiler_controller.cpp
    src/frame_profiler_source.cpp
    src/remote_frame_profiler_source.cpp
)
add_library(termin_frame_profiler::termin_frame_profiler ALIAS termin_frame_profiler)
target_compile_definitions(termin_frame_profiler PRIVATE TERMIN_FRAME_PROFILER_EXPORTS)
target_include_directories(termin_frame_profiler PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_LIST_DIR}/include>
    $<INSTALL_INTERFACE:include>
)
target_link_libraries(termin_frame_profiler
    PUBLIC
        termin_gui_native::termin_gui_native
        termin_profiler_remote::termin_profiler_remote
)
termin_set_rpath_lib(termin_frame_profiler)

if(COMMAND termin_require_package)
    termin_require_package(termin_engine termin_engine::termin_engine)
else()
    find_package(termin_engine REQUIRED)
endif()

add_library(termin_frame_profiler_local SHARED src/local_frame_profiler_source.cpp)
add_library(termin_frame_profiler::local ALIAS termin_frame_profiler_local)
target_compile_definitions(termin_frame_profiler_local PRIVATE TERMIN_FRAME_PROFILER_LOCAL_EXPORTS)
target_link_libraries(termin_frame_profiler_local
    PUBLIC termin_frame_profiler::termin_frame_profiler
    PRIVATE termin_engine::termin_engine
)
termin_set_rpath_lib(termin_frame_profiler_local)

if(MSVC)
    target_compile_options(termin_frame_profiler PRIVATE /W3)
else()
    target_compile_options(termin_frame_profiler PRIVATE -Wall -Wextra)
endif()

include(GNUInstallDirs)
include(CMakePackageConfigHelpers)
install(TARGETS termin_frame_profiler termin_frame_profiler_local
    EXPORT termin_frame_profilerTargets
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
)
install(DIRECTORY include/termin DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})
install(EXPORT termin_frame_profilerTargets
    FILE termin_frame_profilerTargets.cmake
    NAMESPACE termin_frame_profiler::
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_frame_profiler
)
configure_package_config_file(
    cmake/termin_frame_profilerConfig.cmake.in
    ${CMAKE_CURRENT_BINARY_DIR}/termin_frame_profilerConfig.cmake
    INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_frame_profiler
)
write_basic_package_version_file(
    ${CMAKE_CURRENT_BINARY_DIR}/termin_frame_profilerConfigVersion.cmake
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMajorVersion
)
install(FILES
    ${CMAKE_CURRENT_BINARY_DIR}/termin_frame_profilerConfig.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/termin_frame_profilerConfigVersion.cmake
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_frame_profiler
)
