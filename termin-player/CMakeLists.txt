cmake_minimum_required(VERSION 3.16)
project(termin_player LANGUAGES CXX)

include(GNUInstallDirs)
list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/../cmake")
include(TerminRpath)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

if(MSVC)
    set(OPTIMIZE_FLAGS /O2 /fp:precise)
else()
    set(OPTIMIZE_FLAGS -O3)
endif()

find_package(Python COMPONENTS Interpreter Development REQUIRED)

set(_termin_player_has_sdl OFF)
if(TARGET termin_display)
    get_target_property(_termin_display_public_defs termin_display INTERFACE_COMPILE_DEFINITIONS)
    if(_termin_display_public_defs AND "TERMIN_DISPLAY_HAS_SDL" IN_LIST _termin_display_public_defs)
        set(_termin_player_has_sdl ON)
    endif()
endif()

if(TARGET termin_modules_python AND _termin_player_has_sdl)
    add_executable(termin_player
        src/app/termin_player.cpp
        src/player_runtime_host.cpp
    )
    target_compile_features(termin_player PRIVATE cxx_std_20)
    target_include_directories(termin_player PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/include
        ${Python_INCLUDE_DIRS}
    )
    target_link_libraries(termin_player PRIVATE
        Python::Python
        termin_bootstrap::termin_bootstrap
        termin_runtime::termin_runtime
        tgfx::termin_graphics2
        termin_display::termin_display
        termin_engine::termin_engine
        termin_render::termin_render
        termin_render_passes::termin_render_passes
        termin_collision::termin_collision
        termin_components_mesh::termin_components_mesh
        termin_components_collision::termin_components_collision
        termin_components_kinematic::termin_components_kinematic
        termin_components_render::termin_components_render
        termin_components_skeleton::termin_components_skeleton
        termin_modules::termin_modules
        termin_modules_python
    )
    if(NOT WIN32 AND NOT APPLE)
        target_link_options(termin_player PRIVATE
            "LINKER:--no-as-needed"
        )
    endif()
    target_compile_options(termin_player PRIVATE $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>)
    set_target_properties(termin_player PROPERTIES
        RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin
    )
    if(WIN32)
        set_target_properties(termin_player PROPERTIES WIN32_EXECUTABLE FALSE)
    endif()
    install(TARGETS termin_player RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})
    set_target_properties(termin_player PROPERTIES
        INSTALL_RPATH "$ORIGIN/../lib;$ORIGIN/lib;$ORIGIN"
        BUILD_RPATH "${CMAKE_BINARY_DIR}/bin"
        BUILD_WITH_INSTALL_RPATH FALSE
    )
    if(COMMAND termin_set_rpath_tool)
        termin_set_rpath_tool(termin_player)
    endif()
elseif(NOT TARGET termin_modules_python)
    message(STATUS "termin_player disabled because termin_modules_python target is unavailable")
else()
    message(STATUS "termin_player disabled because termin_display was built without SDL")
endif()
