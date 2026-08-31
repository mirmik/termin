# Core package composition for the repository-level build.
#
# This file is intentionally not a standalone CMake project. Global build
# policy, SDK profiles, dependencies, and installation are owned by the
# repository root.

if(TERMIN_BUILD_PYTHON)
    execute_process(
        COMMAND "${Python_EXECUTABLE}" -c
            "import nanobind, pathlib; print(pathlib.Path(nanobind.__file__).resolve().parent / 'cmake')"
        OUTPUT_VARIABLE TERMIN_NANOBIND_CMAKE_DIR
        OUTPUT_STRIP_TRAILING_WHITESPACE
        RESULT_VARIABLE TERMIN_NANOBIND_CMAKE_RESULT
    )
    if(NOT TERMIN_NANOBIND_CMAKE_RESULT EQUAL 0
       OR NOT EXISTS "${TERMIN_NANOBIND_CMAKE_DIR}/nanobind-config.cmake")
        message(FATAL_ERROR
            "nanobind is unavailable for the canonical Python interpreter: "
            "${Python_EXECUTABLE}")
    endif()
    file(TO_CMAKE_PATH
        "${TERMIN_NANOBIND_CMAKE_DIR}"
        TERMIN_NANOBIND_CMAKE_DIR)
    set(nanobind_DIR
        "${TERMIN_NANOBIND_CMAKE_DIR}"
        CACHE PATH "Canonical nanobind CMake package directory" FORCE)

    add_subdirectory(termin-nanobind-sdk)
    include(termin-nanobind-sdk/cmake/TerminNanobindProfile.cmake)
    add_subdirectory(termin-python-host)
endif()

add_subdirectory(termin-base)
add_subdirectory(termin-dispatch)
add_subdirectory(termin-inspect)
