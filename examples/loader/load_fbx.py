import termin.loaders.fbx_loader as fbx_loader
from termin.mesh.mesh import mesh3_from_assimp, show_mesh
from termin.visualization.animation.clip import AnimationClip

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


m = mesh3_from_assimp(data.meshes[0])
print(f"Converted first mesh to Mesh object: vertices={len(m.vertices)}, indices={len(m.triangles)}")

for raw_clip in data.animations:
    conv = AnimationClip.from_assimp_clip(raw_clip)
    print(f"Converted animation clip: {conv}")
    print(f"Channels: {list(conv.channels.values())}")


show_mesh(m)