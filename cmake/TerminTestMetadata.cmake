include_guard(GLOBAL)

# C and C++ assertions are part of the native test contract.  CMake defines
# NDEBUG for optimized configurations, so undo that definition on test-only
# build targets after their ordinary configuration has been applied.  Keep the
# policy target-local: libraries, tools, examples, and other production targets
# must retain their selected configuration's normal NDEBUG semantics.
function(termin_enable_test_assertions target)
    if(NOT TARGET "${target}")
        message(FATAL_ERROR
            "Cannot enable test assertions for unknown target ${target}")
    endif()

    get_property(
        _termin_assertion_policy
        TARGET "${target}"
        PROPERTY TERMIN_TEST_ASSERTION_POLICY
    )
    if(_termin_assertion_policy STREQUAL "TEST_ASSERTIONS")
        return()
    elseif(_termin_assertion_policy STREQUAL "PRESERVE_RELEASE_SEMANTICS")
        message(FATAL_ERROR
            "Target ${target} is registered with conflicting CTest assertion policies")
    endif()

    if(MSVC)
        target_compile_options("${target}" PRIVATE /UNDEBUG)
    else()
        target_compile_options("${target}" PRIVATE -UNDEBUG)
    endif()
    set_property(
        TARGET "${target}"
        PROPERTY TERMIN_TEST_ASSERTION_POLICY TEST_ASSERTIONS
    )
endfunction()

# Keep native diagnostics fatal even when a test executable returns success.
# CTest retains the complete output (including constructor/destructor errors)
# in LastTest.log and the central runner's JUnit report.
function(termin_require_gpu_validation test)
    set_property(TEST "${test}" APPEND PROPERTY ENVIRONMENT
        "TGFX2_GPU_VALIDATION_REQUIRED=1"
        "TGFX2_VULKAN_VALIDATION=1")
    set_property(TEST "${test}" APPEND PROPERTY FAIL_REGULAR_EXPRESSION
        "\\[GPU validation error\\]")

    get_property(_termin_labels TEST "${test}" PROPERTY LABELS)
    if("termin:capability:vulkan" IN_LIST _termin_labels)
        # A selected Vulkan profile requires its runtime and validation layer.
        # SKIP_REGULAR_EXPRESSION takes precedence over failure in CTest, so
        # the old runtime-unavailable patterns must become failures as well.
        get_property(_termin_skip TEST "${test}" PROPERTY SKIP_REGULAR_EXPRESSION)
        if(_termin_skip)
            set_property(TEST "${test}" APPEND PROPERTY FAIL_REGULAR_EXPRESSION
                "${_termin_skip}")
            set_property(TEST "${test}" PROPERTY SKIP_REGULAR_EXPRESSION "")
        endif()
        set_property(TEST "${test}" PROPERTY SKIP_RETURN_CODE)
    endif()
endfunction()

function(_termin_test_backend_capability_is_configured capability output)
    if(capability STREQUAL "vulkan")
        set(_termin_available "${TGFX2_ENABLE_VULKAN}")
    elseif(capability STREQUAL "opengl")
        set(_termin_available "${TGFX2_ENABLE_OPENGL}")
    elseif(capability STREQUAL "d3d11")
        set(_termin_available "${TGFX2_ENABLE_D3D11}")
    elseif(capability STREQUAL "glfw")
        set(_termin_available "${TERMIN_TGFX2_GLFW_AVAILABLE}")
    else()
        message(FATAL_ERROR
            "Unknown configured CTest backend capability: ${capability}")
    endif()
    set("${output}" "${_termin_available}" PARENT_SCOPE)
endfunction()

# Keep CTest metadata machine-readable.  The repository planner uses these
# labels to join CTest's concrete registrations back to the module/test-suite
# inventory; do not replace them with ad-hoc target-name parsing in scripts.
function(termin_label_tests_in_directory module)
    get_property(_termin_directory_tests DIRECTORY PROPERTY TESTS)
    foreach(_termin_test IN LISTS _termin_directory_tests)
        set_property(TEST "${_termin_test}" APPEND PROPERTY LABELS
            "termin:module:${module}"
            "termin:tier:automatic"
            "termin:capability:host")
        if(TARGET "${_termin_test}")
            termin_set_test_build_target("${_termin_test}" "${_termin_test}")
        endif()

        get_property(_termin_labels TEST "${_termin_test}" PROPERTY LABELS)
        termin_require_gpu_validation("${_termin_test}")
        set(_termin_build_target "")
        set(_termin_preserve_release_semantics FALSE)
        set(_termin_requires_python_bindings FALSE)
        set(_termin_requires_window FALSE)
        set(_termin_requires_unconfigured_backend FALSE)
        foreach(_termin_label IN LISTS _termin_labels)
            if(_termin_label MATCHES "^termin:build-target:(.+)$")
                if(_termin_build_target)
                    message(FATAL_ERROR
                        "CTest registration ${_termin_test} has multiple "
                        "termin:build-target labels")
                endif()
                set(_termin_build_target "${CMAKE_MATCH_1}")
            elseif(_termin_label STREQUAL
                   "termin:assert-policy:preserve-release-semantics")
                set(_termin_preserve_release_semantics TRUE)
            elseif(_termin_label STREQUAL
                   "termin:capability:python-bindings")
                set(_termin_requires_python_bindings TRUE)
            elseif(_termin_label STREQUAL "termin:capability:window")
                set(_termin_requires_window TRUE)
            elseif(_termin_label MATCHES
                   "^termin:capability:(vulkan|opengl|d3d11|glfw)$")
                _termin_test_backend_capability_is_configured(
                    "${CMAKE_MATCH_1}"
                    _termin_backend_available)
                if(NOT _termin_backend_available)
                    set(_termin_requires_unconfigured_backend TRUE)
                endif()
            endif()
        endforeach()
        if(NOT _termin_build_target)
            message(FATAL_ERROR
                "CTest registration ${_termin_test} has no build target")
        endif()
        if(_termin_preserve_release_semantics)
            get_property(
                _termin_assertion_policy
                TARGET "${_termin_build_target}"
                PROPERTY TERMIN_TEST_ASSERTION_POLICY
            )
            if(_termin_assertion_policy STREQUAL "TEST_ASSERTIONS")
                message(FATAL_ERROR
                    "Target ${_termin_build_target} is registered with "
                    "conflicting CTest assertion policies")
            endif()
            set_property(
                TARGET "${_termin_build_target}"
                PROPERTY TERMIN_TEST_ASSERTION_POLICY
                PRESERVE_RELEASE_SEMANTICS
            )
        else()
            termin_enable_test_assertions("${_termin_build_target}")
        endif()
        if(NOT _termin_requires_python_bindings
           AND NOT _termin_requires_unconfigured_backend)
            set_property(
                GLOBAL APPEND PROPERTY
                TERMIN_NATIVE_TEST_TARGETS_WITH_WINDOW
                "${_termin_build_target}"
            )
            if(NOT _termin_requires_window)
                set_property(
                    GLOBAL APPEND PROPERTY
                    TERMIN_NATIVE_TEST_TARGETS
                    "${_termin_build_target}"
                )
            endif()
        endif()
    endforeach()
endfunction()

function(termin_add_test_labels test)
    set_property(TEST "${test}" APPEND PROPERTY LABELS ${ARGN})
endfunction()

function(termin_set_test_build_target test target)
    cmake_parse_arguments(
        _termin_test_target
        "PRESERVE_RELEASE_SEMANTICS"
        ""
        ""
        ${ARGN}
    )
    if(_termin_test_target_UNPARSED_ARGUMENTS)
        message(FATAL_ERROR
            "Unknown termin_set_test_build_target arguments: "
            "${_termin_test_target_UNPARSED_ARGUMENTS}")
    endif()
    if(NOT TARGET "${target}")
        message(FATAL_ERROR
            "CTest registration ${test} names unknown build target ${target}")
    endif()
    set_property(TEST "${test}" APPEND PROPERTY LABELS
        "termin:build-target:${target}")
    if(_termin_test_target_PRESERVE_RELEASE_SEMANTICS)
        set_property(TEST "${test}" APPEND PROPERTY LABELS
            "termin:assert-policy:preserve-release-semantics")
    endif()
endfunction()
