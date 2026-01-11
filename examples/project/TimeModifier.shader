@program TimeModifier

// ============================================================
// Time Modifier Post-Process Shader
// ============================================================
//
// Post-processing effect for ChronoSquad time mechanics.
// Changes color based on world time modifier:
//   - time_modifier < 0: blue tint (reverse time)
//   - time_modifier = 0: grayscale (pause)
//   - 0 < time_modifier < 1: grayscale to color gradient
//   - time_modifier = 1: normal color
//   - time_modifier > 1: red tint (fast forward)
//
// Also draws a grid overlay when time is paused (time_modifier < 1).
//
// ============================================================

@phase opaque
@priority 0
@glDepthTest false
@glDepthMask false
@glCull false

@property Float u_time_modifier = 1.0 range(-2.0, 3.0)
@property Float u_grid_intensity = 0.3 range(0.0, 1.0)
@property Float u_grid_scale = 1.0 range(0.1, 10.0)
@property Float u_grid_line_width = 0.03 range(0.01, 0.1)
@property Color u_grid_color = Color(0.0, 0.9, 0.4, 1.0)

@property Texture2D u_input_tex = "white"
@property Texture2D u_depth_texture = "depth_default"
@property Texture2D u_normal_texture = "normal_default"

@stage vertex
#version 330 core

layout(location = 0) in vec2 a_pos;
layout(location = 1) in vec2 a_uv;

out vec2 v_uv;

void main() {
    v_uv = a_uv;
    gl_Position = vec4(a_pos, 0.0, 1.0);
}
@endstage

@stage fragment
#version 330 core

in vec2 v_uv;

uniform sampler2D u_input_tex;
uniform sampler2D u_depth_texture;
uniform sampler2D u_normal_texture;
uniform vec2 u_resolution;
uniform float u_time_modifier;
uniform float u_grid_intensity;
uniform float u_grid_scale;
uniform float u_grid_line_width;
uniform vec4 u_grid_color;

uniform float u_near;
uniform float u_far;
uniform mat4 u_inv_view;
uniform mat4 u_inv_proj;

out vec4 FragColor;

// Reconstruct world position from depth and screen UV
vec3 reconstruct_world_pos(vec2 uv, float linear_depth) {
    // Screen UV to NDC xy (-1 to 1)
    vec2 ndc_xy = uv * 2.0 - 1.0;

    // Unproject near and far points
    vec4 near_ndc = vec4(ndc_xy, -1.0, 1.0);
    vec4 far_ndc = vec4(ndc_xy, 1.0, 1.0);

    vec4 near_view = u_inv_proj * near_ndc;
    vec4 far_view = u_inv_proj * far_ndc;
    near_view /= near_view.w;
    far_view /= far_view.w;

    // Interpolate between near and far based on linear depth
    vec3 view_pos = mix(near_view.xyz, far_view.xyz, linear_depth);

    // Transform to world space
    vec4 world_pos = u_inv_view * vec4(view_pos, 1.0);

    return world_pos.xyz;
}

// Convert color based on time modifier
vec3 get_modified_color(vec3 color, float time_mod) {
    // Grayscale value
    float grayscale = dot(color, vec3(0.2126, 0.7152, 0.0722));
    vec3 gray = vec3(grayscale);

    if (time_mod < 0.0) {
        // Reverse time: blue/cyan tint
        float modifier = -time_mod * 0.1;
        modifier = clamp(modifier, 0.0, 1.0);
        vec3 blue_tint = vec3(gray.r * 0.5, gray.g * 0.7, grayscale * 1.5);
        return mix(gray, blue_tint, modifier);
    }
    else if (time_mod < 1.0) {
        // Pause/slow: grayscale to color gradient
        float gray_coeff = 1.0 - time_mod;
        return mix(color, gray, gray_coeff);
    }
    else if (time_mod > 1.0) {
        // Fast forward: red tint
        float modifier = (time_mod - 1.0) * 0.05;
        modifier = clamp(modifier, 0.0, 1.0);
        vec3 red_tint = vec3(color.r * 1.5, color.g * 0.5, color.b * 0.5);
        return mix(color, red_tint, modifier);
    }

    // Normal speed (time_mod == 1.0)
    return color;
}

// World-space grid based on ChronoCore original
// Returns 1.0 if pixel is on grid line, 0.0 otherwise
// Uses surface normal to avoid drawing lines on surfaces parallel to that line
float world_grid(vec3 world_pos, vec3 normal, float scale, float line_width) {
    // Compute fractional position in grid cells
    float frac_x = fract(world_pos.x / scale);
    float frac_y = fract(world_pos.y / scale);
    float frac_z = fract(world_pos.z / scale);

    // Check if near grid line on any axis
    bool on_x = (frac_x < line_width) || (frac_x > 1.0 - line_width);
    bool on_y = (frac_y < line_width) || (frac_y > 1.0 - line_width);
    bool on_z = (frac_z < line_width) || (frac_z > 1.0 - line_width);

    // Only draw grid line if surface is NOT parallel to that axis
    // (i.e., normal component is not dominant)
    // Threshold 0.9 means: skip line if surface is nearly perpendicular to view axis
    bool show_x = abs(normal.x) < 0.9 && on_x;
    bool show_y = abs(normal.y) < 0.9 && on_y;
    bool show_z = abs(normal.z) < 0.9 && on_z;

    return (show_x || show_y || show_z) ? 1.0 : 0.0;
}

vec4 doit()
{
    vec3 normal_shifted = texture(u_normal_texture, v_uv).rgb;
    vec3 normal = normal_shifted * 2.0 - 1.0;

    vec3 color = texture(u_input_tex, v_uv).rgb;
    float linear_depth = texture(u_depth_texture, v_uv).r;

    // Reconstruct world position
    vec3 world_pos = reconstruct_world_pos(v_uv, linear_depth);

    //return vec4(world_pos, 1.0); // DEBUG: visualize world position

    // Apply time-based color modification
    vec3 modified = get_modified_color(color, u_time_modifier);
    
    // Draw world-space grid when time is slowed/paused
    if (u_time_modifier < 1.0 && u_grid_intensity > 0.0) {
        // Skip grid for sky (very far pixels)
        if (linear_depth < 0.99) {
            float g = world_grid(world_pos, normal, u_grid_scale, u_grid_line_width);

            // if (g < 0.5) {
            //     return vec4(0.0, 0.0, 0.0, 1.0);
            // }
            // else {
            //     return vec4(1.0, 1.0, 1.0, 1.0);
            // }

            // Grid visibility depends on how much time is slowed
            float grid_alpha = g * u_grid_intensity * (1.0 - u_time_modifier);
            modified = mix(modified, u_grid_color.rgb, grid_alpha);
        }
    }
    //return vec4(1.0, 0.0, 0.0, 1.0);
    
    //modified = vec3(modified.r, modified.g, 0.0); // DEBUG: visualize red and green channels only

    return vec4(modified, 1.0); 
    //return vec4(1.0, 0.0, 0.0, 1.0); // DEBUG: visualize red channel only


}

void main() {
    // FragColor = vec4(u_time_modifier, , 0.0, 1.0); // DEBUG: visualize red channel only
    // return;

    FragColor = doit();
}
@endstage

@endphase
