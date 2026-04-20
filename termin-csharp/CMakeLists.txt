cmake_minimum_required(VERSION 3.16)
project(termin_csharp LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

include(GNUInstallDirs)

option(TERMIN_CSHARP_BUILD_NATIVE "Build native SWIG bridge for C# bindings" ON)
option(TERMIN_CSHARP_BUILD_MANAGED "Build managed C# projects with dotnet" OFF)
option(TERMIN_CSHARP_BUILD_TESTS "Build Termin.Test project with dotnet" OFF)

if(WIN32)
    set(TERMIN_CSHARP_RUNTIME_DIR "${CMAKE_CURRENT_SOURCE_DIR}/Termin.Native/runtimes/win-x64/native")
else()
    set(TERMIN_CSHARP_RUNTIME_DIR "${CMAKE_CURRENT_SOURCE_DIR}/Termin.Native/runtimes/linux-x64/native")
endif()

file(MAKE_DIRECTORY "${TERMIN_CSHARP_RUNTIME_DIR}")
file(MAKE_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/Termin.Native/Generated")

if(TERMIN_CSHARP_BUILD_NATIVE)
    find_package(SWIG REQUIRED COMPONENTS csharp)
    include(UseSWIG)

    find_package(OpenGL REQUIRED)
    find_package(termin REQUIRED)
    find_package(termin_scene REQUIRED)
    find_package(termin_collision REQUIRED)
    find_package(termin_components_collision REQUIRED)
    find_package(termin_components_kinematic REQUIRED)
    find_package(termin_render REQUIRED)
    find_package(tcplot REQUIRED)

    set(CMAKE_SWIG_OUTDIR "${CMAKE_CURRENT_SOURCE_DIR}/Termin.Native/Generated")

    set_source_files_properties(
        ${CMAKE_CURRENT_SOURCE_DIR}/termin.i
        PROPERTIES
        CPLUSPLUS ON
        SWIG_USE_TARGET_INCLUDE_DIRECTORIES ON
        SWIG_FLAGS "-namespace;Termin.Native"
    )

    swig_add_library(termin_csharp_native
        TYPE SHARED
        LANGUAGE csharp
        SOURCES
            ${CMAKE_CURRENT_SOURCE_DIR}/termin.i
            ${CMAKE_CURRENT_SOURCE_DIR}/src/tc_component_csharp.cpp
            ${CMAKE_CURRENT_SOURCE_DIR}/src/tc_inspect_csharp.cpp
            ${CMAKE_CURRENT_SOURCE_DIR}/../termin-app/cpp/termin/render/tc_opengl.cpp
    )

    set_target_properties(${SWIG_MODULE_termin_csharp_native_REAL_NAME} PROPERTIES
        OUTPUT_NAME "termin"
        # Per-config overrides bypass Visual Studio's default
        # "$(Configuration)" subfolder append. Without these the DLL
        # lands in runtimes/win-x64/native/Release/termin.dll — and
        # .NET's RID resolver expects it at runtimes/win-x64/native/,
        # so the process fails to load termin.dll at startup with
        # DllNotFoundException. Flatten the output path explicitly.
        LIBRARY_OUTPUT_DIRECTORY         "${TERMIN_CSHARP_RUNTIME_DIR}"
        LIBRARY_OUTPUT_DIRECTORY_DEBUG   "${TERMIN_CSHARP_RUNTIME_DIR}"
        LIBRARY_OUTPUT_DIRECTORY_RELEASE "${TERMIN_CSHARP_RUNTIME_DIR}"
        RUNTIME_OUTPUT_DIRECTORY         "${TERMIN_CSHARP_RUNTIME_DIR}"
        RUNTIME_OUTPUT_DIRECTORY_DEBUG   "${TERMIN_CSHARP_RUNTIME_DIR}"
        RUNTIME_OUTPUT_DIRECTORY_RELEASE "${TERMIN_CSHARP_RUNTIME_DIR}"
        ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/lib"
    )

    target_include_directories(${SWIG_MODULE_termin_csharp_native_REAL_NAME} PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/include
    )
    target_compile_definitions(${SWIG_MODULE_termin_csharp_native_REAL_NAME} PRIVATE TCBASE_EXPORTS TC_EXPORTS)

    target_link_libraries(${SWIG_MODULE_termin_csharp_native_REAL_NAME} PRIVATE
        OpenGL::GL
        termin::trent
        termin::entity_lib
        termin::render_lib
        termin_scene::termin_scene
        termin_collision::termin_collision
        termin_components_collision::termin_components_collision
        termin_components_kinematic::termin_components_kinematic
        termin_render::termin_render
        tcplot::tcplot
    )

    set(_termin_csharp_runtime_targets
        termin::trent
        termin::entity_lib
        termin::render_lib
        tcbase::termin_base
        termin_inspect::termin_inspect
        termin_scene::termin_scene
        termin_input::termin_input
        termin_collision::termin_collision
        termin_components_collision::termin_components_collision
        termin_components_kinematic::termin_components_kinematic
        termin_render::termin_render
        tgfx::termin_graphics
        tgfx::termin_graphics2
        termin_modules::termin_modules
        tmesh::termin_mesh
        tcplot::tcplot
    )

    foreach(_dep IN LISTS _termin_csharp_runtime_targets)
        add_custom_command(TARGET ${SWIG_MODULE_termin_csharp_native_REAL_NAME} POST_BUILD
            COMMAND ${CMAKE_COMMAND} -E copy_if_different
                $<TARGET_FILE:${_dep}>
                "${TERMIN_CSHARP_RUNTIME_DIR}/"
            VERBATIM
        )
    endforeach()
endif()

if(TERMIN_CSHARP_BUILD_MANAGED)
    find_program(DOTNET_EXECUTABLE dotnet REQUIRED)

    # `dotnet build` без `-c` собирает csproj в Debug по умолчанию,
    # даже если cmake запущен с --config Release. AppsUIMonorepo-овский
    # update-sdk.ps1 ищет Termin.Native.dll в bin/Release/ — если мы
    # не пробросим конфигурацию сюда, он молча находит старый Release-
    # билд или не находит вообще. Пробрасываем через $<CONFIG>.
    add_custom_target(termin_csharp_managed ALL
        COMMAND ${DOTNET_EXECUTABLE} build ${CMAKE_CURRENT_SOURCE_DIR}/Termin.Native/Termin.Native.csproj -c $<CONFIG>
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        VERBATIM
    )

    if(TERMIN_CSHARP_BUILD_NATIVE)
        add_dependencies(termin_csharp_managed ${SWIG_MODULE_termin_csharp_native_REAL_NAME})
    endif()

    if(TERMIN_CSHARP_BUILD_TESTS)
        add_custom_target(termin_csharp_tests ALL
            COMMAND ${DOTNET_EXECUTABLE} build ${CMAKE_CURRENT_SOURCE_DIR}/Termin.Test/Termin.Test.csproj -c $<CONFIG>
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            VERBATIM
        )
        add_dependencies(termin_csharp_tests termin_csharp_managed)
    endif()
endif()
