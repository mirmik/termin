from termin.project_build.diagnostics import BuildDiagnostic, build_error, build_warning, format_diagnostics
from termin.project_build.runtime_package_exporter import RuntimePackageExportDiagnostic


def test_build_diagnostic_serializes_to_runtime_diagnostic_shape() -> None:
    diagnostic = BuildDiagnostic("error", "project", "invalid project")

    assert diagnostic.to_dict() == {
        "level": "error",
        "path": "project",
        "message": "invalid project",
    }


def test_build_diagnostic_can_copy_existing_diagnostic_shape() -> None:
    export_diagnostic = RuntimePackageExportDiagnostic("warning", "mesh.json", "missing tangent")

    assert BuildDiagnostic.from_diagnostic(export_diagnostic) == BuildDiagnostic(
        "warning",
        "mesh.json",
        "missing tangent",
    )


def test_build_diagnostic_helpers_create_levels() -> None:
    assert build_error("entry.scene", "missing") == BuildDiagnostic("error", "entry.scene", "missing")
    assert build_warning("profile", "deprecated") == BuildDiagnostic("warning", "profile", "deprecated")


def test_format_diagnostics_uses_common_message_shape() -> None:
    diagnostics = [
        BuildDiagnostic("error", "entry.scene", "missing"),
        BuildDiagnostic("warning", "profile", "deprecated"),
    ]

    assert format_diagnostics("Build failed:", diagnostics) == (
        "Build failed:\n"
        "- error: entry.scene: missing\n"
        "- warning: profile: deprecated"
    )
