from termin.editor_tcgui.pipeline_inspector import PipelineInspectorTcgui


class _ResourceManagerStub:
    def get_pipeline(self, _name):
        return None


class _SpecStub:
    def __init__(self, resource="color", format="render_target"):
        self.resource = resource
        self.resource_type = "fbo"
        self.samples = 1
        self.format = format
        self.clear_color = None
        self.clear_depth = None


class _PipelineStub:
    passes = []
    pipeline_specs = []

    def serialize(self):
        return {
            "name": "compiled_graph",
            "passes": [
                {
                    "type": "ColorPass",
                    "pass_name": "Color",
                }
            ],
            "pipeline_specs": [],
        }


def test_pipeline_inspector_file_mode_shows_compiled_result_readonly():
    inspector = PipelineInspectorTcgui(_ResourceManagerStub())

    inspector.set_pipeline(
        _PipelineStub(),
        subtitle="File: Example.pipeline",
        source_path="/tmp/Example.pipeline",
    )

    assert inspector._compiled_title.visible is True
    assert inspector._compiled_output.visible is True
    assert inspector._compiled_output.read_only is True
    assert inspector._details.visible is False
    assert inspector._edit_button.visible is True
    assert '"passes"' in inspector._compiled_output.text
    assert '"ColorPass"' in inspector._compiled_output.text


def test_pipeline_inspector_compile_failure_keeps_log_visible():
    inspector = PipelineInspectorTcgui(_ResourceManagerStub())

    inspector.set_pipeline(
        None,
        subtitle="File: Broken.pipeline",
        source_path="/tmp/Broken.pipeline",
    )

    assert inspector._compiled_title.visible is True
    assert inspector._compiled_output.visible is True
    assert inspector._edit_button.visible is True
    assert inspector._empty.visible is False
    assert "Pipeline compilation failed" in inspector._compiled_output.text


def test_pipeline_inspector_resource_spec_defaults_to_output_render_target():
    inspector = PipelineInspectorTcgui(_ResourceManagerStub())
    pipeline = _PipelineStub()
    pipeline.pipeline_specs = [_SpecStub()]

    inspector.set_pipeline(pipeline)
    inspector._on_spec_selected(0, {})

    assert inspector._spec_format_values[inspector._spec_format.selected_index] == "render_target"
