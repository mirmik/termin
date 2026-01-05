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
@property Float u_grid_scale = 50.0 range(10.0, 200.0)
@property Color u_grid_color = Color(0.0, 0.9, 0.4, 1.0)

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

uniform sampler2D u_color;
uniform vec2 u_resolution;
uniform float u_time_modifier;
uniform float u_grid_intensity;
uniform float u_grid_scale;
uniform vec4 u_grid_color;

out vec4 FragColor;

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

// Draw screen-space grid
float grid(vec2 uv, float scale, float line_width) {
    vec2 grid_uv = uv * scale;
    vec2 grid_frac = fract(grid_uv);

    // Check if near grid line
    float line_x = step(grid_frac.x, line_width) + step(1.0 - line_width, grid_frac.x);
    float line_y = step(grid_frac.y, line_width) + step(1.0 - line_width, grid_frac.y);

    return clamp(line_x + line_y, 0.0, 1.0);
}

void main() {
    vec3 color = texture(u_color, v_uv).rgb;

    // Apply time-based color modification
    vec3 modified = get_modified_color(color, u_time_modifier);

    // Draw grid when time is slowed/paused
    if (u_time_modifier < 1.0 && u_grid_intensity > 0.0) {
        // Adjust aspect ratio for grid
        vec2 aspect_uv = v_uv;
        aspect_uv.x *= u_resolution.x / u_resolution.y;

        float line_width = 0.02;
        float g = grid(aspect_uv, u_grid_scale, line_width);

        // Grid visibility depends on how much time is slowed
        float grid_alpha = g * u_grid_intensity * (1.0 - u_time_modifier);
        modified = mix(modified, u_grid_color.rgb, grid_alpha);
    }

    FragColor = vec4(modified, 1.0);
}
@endstage

@endphase
