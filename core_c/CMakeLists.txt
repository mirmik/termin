cmake_minimum_required(VERSION 3.14)
project(termin_core C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Options
option(TC_BUILD_SHARED "Build shared library" ON)
option(TC_BUILD_TESTS "Build tests" ON)

# Source files
set(TC_SOURCES
    src/tc_core.c
    src/tc_component.c
    src/tc_component_python.c
    src/tc_entity_pool.c
    src/tc_hash_map.c
    src/tc_resource_map.c
    src/tc_scene.c
    src/tc_inspect.c
    src/tc_mesh.c
    src/tc_mesh_registry.c
    src/tc_log.c
    src/tc_profiler.c
)

# Header files (for IDE integration)
set(TC_HEADERS
    include/termin_core.h
    include/tc_types.h
    include/tc_vec3.h
    include/tc_quat.h
    include/tc_pose.h
    include/tc_component.h
    include/tc_component_python.h
    include/tc_entity_pool.h
    include/tc_hash_map.h
    include/tc_resource_map.h
    include/tc_scene.h
    include/tc_inspect.h
    include/tc_mesh.h
    include/tc_mesh_registry.h
)

# Library target
if(TC_BUILD_SHARED)
    add_library(termin_core SHARED ${TC_SOURCES} ${TC_HEADERS})
    target_compile_definitions(termin_core PRIVATE TC_EXPORTS)
else()
    add_library(termin_core STATIC ${TC_SOURCES} ${TC_HEADERS})
endif()

target_include_directories(termin_core
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include>
)

# Find Python and pybind11
find_package(Python3 COMPONENTS Development)

# Find pybind11 via pip
if(WIN32)
    execute_process(
        COMMAND python -m pybind11 --cmakedir
        OUTPUT_VARIABLE pybind11_DIR
        OUTPUT_STRIP_TRAILING_WHITESPACE
    )
else()
    execute_process(
        COMMAND python3 -m pybind11 --cmakedir
        OUTPUT_VARIABLE pybind11_DIR
        OUTPUT_STRIP_TRAILING_WHITESPACE
    )
endif()
find_package(pybind11 QUIET)

# Platform-specific
if(WIN32)
    target_link_libraries(termin_core PRIVATE winmm)
endif()

if(UNIX AND NOT APPLE)
    target_link_libraries(termin_core PRIVATE m)
endif()

# Link Python if found
if(Python3_FOUND)
    target_include_directories(termin_core PRIVATE ${Python3_INCLUDE_DIRS})
    target_link_libraries(termin_core PRIVATE ${Python3_LIBRARIES})
endif()

# Link pybind11 if found
if(pybind11_FOUND)
    target_link_libraries(termin_core PRIVATE pybind11::headers)
endif()

# Compiler warnings
if(MSVC)
    target_compile_options(termin_core PRIVATE /W4)
else()
    target_compile_options(termin_core PRIVATE -Wall -Wextra -Wpedantic)
endif()

# Tests
if(TC_BUILD_TESTS)
    enable_testing()

    # C tests
    add_executable(termin_core_test tests/test_main.c)
    target_link_libraries(termin_core_test termin_core)
    if(UNIX AND NOT APPLE)
        target_link_libraries(termin_core_test m)
    endif()
    add_test(NAME termin_core_test COMMAND termin_core_test)

    # C++ tests (disabled - termin_core.hpp needs updating)
    # add_executable(termin_core_test_cpp tests/test_cpp.cpp)
    # target_link_libraries(termin_core_test_cpp termin_core)
    # set_target_properties(termin_core_test_cpp PROPERTIES
    #     CXX_STANDARD 17
    #     CXX_STANDARD_REQUIRED ON
    # )
    # add_test(NAME termin_core_test_cpp COMMAND termin_core_test_cpp)
endif()

# Install
install(TARGETS termin_core
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
    RUNTIME DESTINATION bin
)

install(FILES ${TC_HEADERS} DESTINATION include/termin_core)
