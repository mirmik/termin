include_guard(GLOBAL)

function(termin_link_font_libraries target)
    set(thirdparty "${CMAKE_CURRENT_FUNCTION_LIST_DIR}/../termin-thirdparty")
    set(BUILD_SHARED_LIBS OFF)
    set(CMAKE_POSITION_INDEPENDENT_CODE ON)
    set(SKIP_INSTALL_ALL ON)

    # Use HarfBuzz's portable OpenType shaper. Its published amalgamation
    # needs neither platform font APIs nor an installed HarfBuzz SDK.
    add_library(termin_harfbuzz STATIC "${thirdparty}/harfbuzz/src/harfbuzz.cc")
    target_include_directories(termin_harfbuzz SYSTEM PUBLIC
        "$<BUILD_INTERFACE:${thirdparty}/harfbuzz/src>")
    # New Clang versions diagnose unused templates in the amalgamation;
    # retain compiler diagnostics without upstream's promotion to errors.
    target_compile_definitions(termin_harfbuzz PRIVATE HB_NO_PRAGMA_GCC_DIAGNOSTIC_ERROR)
    if(MSVC)
        target_compile_options(termin_harfbuzz PRIVATE /bigobj)
    endif()

    # FreeType consumes font bytes from the caller. Disable optional host
    # codecs and shaping integrations on every build, including cross builds.
    foreach(feature ZLIB BZIP2 PNG HARFBUZZ BROTLI)
        set(FT_DISABLE_${feature} ON CACHE BOOL "" FORCE)
    endforeach()
    # Upstream also consults these variables when previously detected by a
    # sibling package, even if the corresponding discovery is disabled.
    foreach(package ZLIB BZIP2 PNG HarfBuzz BROTLIDEC)
        set(${package}_FOUND FALSE)
    endforeach()
    add_subdirectory("${thirdparty}/freetype" "${CMAKE_BINARY_DIR}/termin-thirdparty/freetype" EXCLUDE_FROM_ALL)

    if(EMSCRIPTEN)
        # The Web SDK exports static Termin archives. Include the private
        # object code so downstream links use the same implementation.
        foreach(lib freetype termin_harfbuzz)
            target_sources(${target} PRIVATE $<TARGET_OBJECTS:${lib}>)
            target_include_directories(${target} SYSTEM PRIVATE $<TARGET_PROPERTY:${lib},INTERFACE_INCLUDE_DIRECTORIES>)
        endforeach()
    else()
        target_link_libraries(${target} PRIVATE freetype termin_harfbuzz)
        if(CMAKE_SYSTEM_NAME MATCHES "^(Linux|Android)$")
            # Hosts such as Avalonia may already carry a different FreeType.
            target_link_options(${target} PRIVATE
                "LINKER:--exclude-libs,$<TARGET_FILE_NAME:freetype>:$<TARGET_FILE_NAME:termin_harfbuzz>")
        endif()
    endif()

    install(FILES "${thirdparty}/freetype/docs/FTL.TXT" DESTINATION share/licenses/FreeType)
    install(FILES "${thirdparty}/FreeType-NOTICE.txt" DESTINATION share/licenses/FreeType-NOTICE)
    install(FILES "${thirdparty}/harfbuzz/COPYING" DESTINATION share/licenses/HarfBuzz)
    install(FILES "${thirdparty}/harfbuzz/src/ms-use/COPYING" DESTINATION share/licenses/HarfBuzz-MS-USE)
endfunction()
