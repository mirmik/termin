from termin.default_assets.render.pipeline_dependencies import material_pass_materials


def test_material_pass_dependencies_read_canonical_uuid_reference_name():
    graph = {
        "nodes": [
            {
                "type": "MaterialPass",
                "params": {
                    "material": {
                        "uuid": "material-uuid",
                        "name": "PostEffect",
                        "type": "uuid",
                        "kind": "tc_material",
                    }
                },
            }
        ]
    }

    assert material_pass_materials(graph) == {"PostEffect"}
