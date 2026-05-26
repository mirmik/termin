from termin.render_components import MaterialPass
from termin.render_framework import RenderPipeline
from termin.assets.resources import ResourceManager
from termin.materials import TcMaterial


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


def test_material_pass_accepts_serialized_material_reference():
    mat = TcMaterial.create("MaterialPassSerializedRefMaterial", "")
    material_pass = MaterialPass(
        output_res="out",
        pass_name="MaterialPass",
        material={
            "uuid": mat.uuid,
            "name": mat.name,
            "type": "uuid",
        },
    )

    assert material_pass.material.is_valid
    assert material_pass.material.uuid == mat.uuid
