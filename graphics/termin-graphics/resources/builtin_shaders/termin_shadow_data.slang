import termin_prelude;
import termin_lighting;

public static const int MAX_SHADOW_MAPS = 16;

public struct ShadowBlock {
    public int u_shadow_map_count;
    // Explicit matrix rows keep the std140 footprint stable without nested
    // RowMajor/MatrixStride decorations, which older mobile Vulkan drivers
    // can miscompile for arrays of matrices.
    public float4 u_light_space_matrix[MAX_SHADOW_MAPS * 4];
    public int u_shadow_light_index[MAX_SHADOW_MAPS];
    public int u_shadow_cascade_index[MAX_SHADOW_MAPS];
    public float u_shadow_split_near[MAX_SHADOW_MAPS];
    public float u_shadow_split_far[MAX_SHADOW_MAPS];
    // Row 1 of the camera view matrix. Termin uses +Y as view-space depth.
    public float4 u_camera_view_depth;
    // xy = 1 / shadow-map dimensions. float4 keeps array stride explicit and
    // identical across std140, HLSL constant buffers and older Vulkan drivers.
    public float4 u_shadow_texel_size[MAX_SHADOW_MAPS];
};

[[TerminScope("pass")]]
public ConstantBuffer<ShadowBlock> shadow_block;

public static const int SHADOW_METHOD_HARD = 0;
public static const int SHADOW_METHOD_PCF = 1;
public static const int SHADOW_METHOD_POISSON = 2;

public static const int POISSON_SAMPLE_COUNT = 16;
public static const float2 POISSON_DISK[POISSON_SAMPLE_COUNT] = {
    float2(-0.94201624, -0.39906216),
    float2( 0.94558609, -0.76890725),
    float2(-0.09418410, -0.92938870),
    float2( 0.34495938,  0.29387760),
    float2(-0.91588581,  0.45771432),
    float2(-0.81544232, -0.87912464),
    float2(-0.38277543,  0.27676845),
    float2( 0.97484398,  0.75648379),
    float2( 0.44323325, -0.97511554),
    float2( 0.53742981, -0.47373420),
    float2(-0.26496911, -0.41893023),
    float2( 0.79197514,  0.19090188),
    float2(-0.24188840,  0.99706507),
    float2(-0.81409955,  0.91437590),
    float2( 0.19984126,  0.78641367),
    float2( 0.14383161, -0.14100790),
};

public float shadow_bias_depth(int sm) {
    float depth_range = max(
        shadow_block.u_shadow_split_far[sm] - shadow_block.u_shadow_split_near[sm],
        0.0001);
    return max(get_shadow_bias(), 0.0) / depth_range;
}
