import termin.loaders.fbx_loader as fbx_loader

data = fbx_loader.load_fbx_file("examples/data/FBX/animcube.fbx")

print("Loaded FBX file:")
print(f"Number of meshes: {len(data.meshes)}")
print(f"Number of materials: {len(data.materials)}")
print(f"Number of animations: {len(data.animations)}")

for i, mesh in enumerate(data.meshes):
    print(f" Mesh {i}: {mesh.name}, vertices: {len(mesh.vertices)}, indices: {len(mesh.indices)}, material index: {mesh.material_index}")

for i, anim in enumerate(data.animations):
    print(f" Animation {i}: {anim.name}, duration: {anim.duration}")
    for ch in anim.channels:
        print(f"  Channel for node: {ch.node_name}, pos keys: {len(ch.pos_keys)}, rot keys: {len(ch.rot_keys)}, scale keys: {len(ch.scale_keys)}")

