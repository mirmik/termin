# Keep launcher ownership in the cache so reconfiguration can undo Termin's
# ccache setting without removing launchers supplied by the caller/toolchain.
if(TERMIN_USE_CCACHE AND NOT MSVC)
    find_program(TERMIN_CCACHE_PROGRAM ccache)
    if(NOT TERMIN_CCACHE_PROGRAM)
        message(STATUS "Termin: ccache requested but not found")
    endif()
endif()

foreach(_termin_language C CXX)
    set(_termin_launcher "CMAKE_${_termin_language}_COMPILER_LAUNCHER")
    set(_termin_owned_launcher "_TERMIN_${_termin_language}_CCACHE_LAUNCHER")

    # Older Termin configurations cached the discovered ccache path without an
    # ownership marker. Adopt that exact value when reopening those build trees.
    if(NOT DEFINED ${_termin_owned_launcher}
       AND TERMIN_CCACHE_PROGRAM
       AND "${${_termin_launcher}}" STREQUAL "${TERMIN_CCACHE_PROGRAM}")
        set(${_termin_owned_launcher} "${TERMIN_CCACHE_PROGRAM}" CACHE INTERNAL
            "Compiler launcher installed by Termin")
    endif()

    # An explicit replacement belongs to the caller, even if Termin originally
    # populated this language's launcher.
    if(DEFINED ${_termin_owned_launcher}
       AND NOT "${${_termin_launcher}}" STREQUAL "${${_termin_owned_launcher}}")
        unset(${_termin_owned_launcher} CACHE)
    endif()

    if(NOT TERMIN_USE_CCACHE OR MSVC)
        if(DEFINED ${_termin_owned_launcher})
            set(${_termin_launcher} "" CACHE STRING "${_termin_language} compiler launcher" FORCE)
            set(${_termin_launcher} "")
            unset(${_termin_owned_launcher} CACHE)
            message(STATUS "Termin: disabled ${_termin_language} ccache compiler launcher")
        endif()
    elseif(TERMIN_CCACHE_PROGRAM AND NOT ${_termin_launcher})
        set(${_termin_launcher} "${TERMIN_CCACHE_PROGRAM}" CACHE STRING
            "${_termin_language} compiler launcher" FORCE)
        set(${_termin_launcher} "${TERMIN_CCACHE_PROGRAM}")
        set(${_termin_owned_launcher} "${TERMIN_CCACHE_PROGRAM}" CACHE INTERNAL
            "Compiler launcher installed by Termin")
        message(STATUS "Termin: using ${_termin_language} ccache compiler launcher: ${TERMIN_CCACHE_PROGRAM}")
    endif()
endforeach()
