cmake_minimum_required(VERSION 3.14)
project(termin_core C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

# Options
option(TC_BUILD_SHARED "Build shared library" ON)
option(TC_BUILD_TESTS "Build tests" ON)

# Source files
set(TC_SOURCES
    src/tc_core.c
    src/tc_component.c
    src/tc_component_python.c
    src/tc_entity_pool.c
    src/tc_scene.c
    src/tc_inspect.c
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
    include/tc_scene.h
    include/tc_inspect.h
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

# Platform-specific
if(WIN32)
    target_link_libraries(termin_core PRIVATE winmm)
endif()

if(UNIX AND NOT APPLE)
    target_link_libraries(termin_core PRIVATE m)
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
    add_test(NAME termin_core_test COMMAND termin_core_test)

    # C++ tests
    add_executable(termin_core_test_cpp tests/test_cpp.cpp)
    target_link_libraries(termin_core_test_cpp termin_core)
    set_target_properties(termin_core_test_cpp PROPERTIES
        CXX_STANDARD 17
        CXX_STANDARD_REQUIRED ON
    )
    add_test(NAME termin_core_test_cpp COMMAND termin_core_test_cpp)
endif()

# Install
install(TARGETS termin_core
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
    RUNTIME DESTINATION bin
)

install(FILES ${TC_HEADERS} DESTINATION include/termin_core)
