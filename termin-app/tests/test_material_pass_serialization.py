from termin.render_components import MaterialPass
from termin.render_framework import RenderPipeline
from termin.assets.resources import ResourceManager


def test_material_pass_graph_texture_inputs_survive_pipeline_copy():
    rm = ResourceManager.instance()
    rm.register_builtin_frame_passes()

    material_pass = MaterialPass(output_res="out", pass_name="MaterialPass")
    material_pass.output_res_target = "target"
    material_pass.set_texture_resource("u_input_tex", "input")

    pipeline = RenderPipeline("test")
    pipeline.add_pass(material_pass)

    copied = pipeline.copy(rm)
    copied_pass = copied.passes[0]

    assert sorted(copied_pass.reads) == ["input", "target"]
    assert copied_pass.serialize_data()["texture_resources"] == {"u_input_tex": "input"}
