@vertex
fn vs_main(@builtin(vertex_index) index: u32) -> @builtin(position) vec4<f32> {
    let positions = array<vec2<f32>, 3>(
        vec2<f32>(0.0, -0.7),
        vec2<f32>(-0.7, 0.7),
        vec2<f32>(0.7, 0.7));
    return vec4<f32>(positions[index], 0.0, 1.0);
}

@fragment
fn fs_main() -> @location(0) vec4<f32> {
    return vec4<f32>(0.95, 0.32, 0.12, 1.0);
}
