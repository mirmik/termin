import pytest

from termin.visualization.render.shader_parser import parse_shader_text


def test_parse_render_state_directives():
    shader_text = "\n".join(
        [
            "@program demo",
            "@phase main",
            "@priority 3",
            "@glDepthMask false",
            "@glDepthTest true",
            "@glBlend on",
            "@glCull off",
            "@stage vertex",
            "void main() {}",
            "@endstage",
            "@endphase",
        ]
    )

    parsed = parse_shader_text(shader_text)
    assert parsed["program"] == "demo"
    assert len(parsed["phases"]) == 1

    phase = parsed["phases"][0]
    assert phase["phase_mark"] == "main"
    assert phase["priority"] == 3
    assert phase["glDepthMask"] is False
    assert phase["glDepthTest"] is True
    assert phase["glBlend"] is True
    assert phase["glCull"] is False
    assert phase["stages"]["vertex"] == "void main() {}\n"


def test_render_state_directives_require_phase():
    directives = ("@glDepthTest true", "@glBlend true", "@glCull true")
    for directive in directives:
        with pytest.raises(ValueError):
            parse_shader_text(f"{directive}\n")


def test_render_state_directives_require_value():
    directives = ("@glDepthTest", "@glBlend", "@glCull")
    shader_body = "\n".join(["@phase main", "{directive}", "@endphase"])
    for directive in directives:
        with pytest.raises(ValueError):
            parse_shader_text(shader_body.format(directive=directive))


def test_parse_multiple_phases_and_stages():
    shader_text = "\n".join(
        [
            "@program composite",
            "@phase geometry",
            "@priority 1",
            "@glDepthTest on",
            "@stage vertex",
            "// vertex stage",
            "void main() {}",
            "@endstage",
            "@stage fragment",
            "// fragment stage",
            "void main() {",
            "  gl_FragColor = vec4(1.0);",
            "}",
            "@endstage",
            "@endphase",
            "@phase overlay",
            "@glDepthMask off",
            "@glDepthTest off",
            "@glBlend true",
            "@stage vertex",
            "// overlay vertex",
            "@endstage",
            "@endphase",
        ]
    )

    parsed = parse_shader_text(shader_text)
    assert parsed["program"] == "composite"
    assert len(parsed["phases"]) == 2

    geometry = parsed["phases"][0]
    assert geometry["phase_mark"] == "geometry"
    assert geometry["priority"] == 1
    assert geometry["glDepthTest"] is True
    assert geometry["glDepthMask"] is None
    assert geometry["glBlend"] is None
    assert geometry["glCull"] is None
    assert geometry["stages"]["vertex"] == "// vertex stage\nvoid main() {}\n"
    assert geometry["stages"]["fragment"] == "// fragment stage\nvoid main() {\n  gl_FragColor = vec4(1.0);\n}\n"

    overlay = parsed["phases"][1]
    assert overlay["phase_mark"] == "overlay"
    assert overlay["priority"] == 0  # default value
    assert overlay["glDepthMask"] is False
    assert overlay["glDepthTest"] is False
    assert overlay["glBlend"] is True
    assert overlay["glCull"] is None
    assert overlay["stages"]["vertex"] == "// overlay vertex\n"
