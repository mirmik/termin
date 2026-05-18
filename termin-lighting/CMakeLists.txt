cmake_minimum_required(VERSION 3.16)
project(termin_lighting VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

option(TERMIN_BUILD_PYTHON "Build Python binding _lighting_native" OFF)

if(COMMAND termin_require_package)
    termin_require_package(termin_base tcbase::termin_base)
else()
    find_package(termin_base REQUIRED)
endif()

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_LIST_DIR}/../cmake")
include(TerminRpath)

add_library(termin_lighting INTERFACE)
add_library(termin_lighting::termin_lighting ALIAS termin_lighting)

target_include_directories(termin_lighting INTERFACE
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)

target_link_libraries(termin_lighting INTERFACE
    tcbase::termin_base
)

if(TERMIN_BUILD_PYTHON)
    if(NOT Python_EXECUTABLE)
        if(WIN32)
            set(Python_EXECUTABLE "python")
        else()
            set(Python_EXECUTABLE "python3")
        endif()
    endif()
    find_package(Python 3.8 COMPONENTS Interpreter Development REQUIRED)
    find_package(nanobind CONFIG REQUIRED)
    if(COMMAND termin_require_package)
    termin_require_package(termin_scene termin_scene::termin_scene)
else()
    find_package(termin_scene REQUIRED)
endif()

    nanobind_add_module(_lighting_native NB_SHARED
        cpp/bindings/lighting_bindings.cpp
    )
    target_link_libraries(_lighting_native PRIVATE
        termin_lighting::termin_lighting
        termin_scene::termin_scene
    )
    termin_set_rpath_python(_lighting_native)
    install(TARGETS _lighting_native DESTINATION lib/python/termin/lighting)
    install(DIRECTORY ${CMAKE_CURRENT_LIST_DIR}/python/termin/lighting/
            DESTINATION lib/python/termin/lighting
            FILES_MATCHING PATTERN "*.py")
endif()

include(GNUInstallDirs)

install(TARGETS termin_lighting
    EXPORT termin_lightingTargets
)

install(DIRECTORY include/
    DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
)

install(EXPORT termin_lightingTargets
    FILE termin_lightingTargets.cmake
    NAMESPACE termin_lighting::
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_lighting
)

include(CMakePackageConfigHelpers)

configure_package_config_file(
    cmake/termin_lightingConfig.cmake.in
    ${CMAKE_CURRENT_BINARY_DIR}/termin_lightingConfig.cmake
    INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_lighting
)

write_basic_package_version_file(
    ${CMAKE_CURRENT_BINARY_DIR}/termin_lightingConfigVersion.cmake
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMajorVersion
)

install(FILES
    ${CMAKE_CURRENT_BINARY_DIR}/termin_lightingConfig.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/termin_lightingConfigVersion.cmake
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/termin_lighting
)
