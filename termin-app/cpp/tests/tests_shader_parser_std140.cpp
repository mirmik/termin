#include "guard/guard.h"
#include "termin/render/shader_parser.hpp"

#include <cstdint>
#include <cstring>
#include <string>
#include <vector>

using termin::MaterialProperty;
using termin::MaterialUboLayout;
using termin::ShaderMultyPhaseProgramm;
using termin::compute_std140_layout;
using termin::inject_after_version;
using termin::parse_shader_text;
using termin::std140_pack;
using termin::std140_size_align;
using termin::strip_uniform_decls;
using termin::synthesize_material_ubo_glsl;

static MaterialProperty mk(const char* name, const char* type) {
    return MaterialProperty(name, type, std::monostate{});
}

static MaterialProperty mk_float(const char* name, double v) {
    return MaterialProperty(name, "Float", v);
}

static MaterialProperty mk_int(const char* name, int v) {
    return MaterialProperty(name, "Int", v);
}

static MaterialProperty mk_bool(const char* name, bool v) {
    return MaterialProperty(name, "Bool", v);
}

static MaterialProperty mk_vec(const char* name, const char* type,
                                std::vector<double> values) {
    return MaterialProperty(name, type, std::move(values));
}

// Read a float from a packed buffer at a byte offset.
static float read_float_at(const std::vector<uint8_t>& buf, uint32_t offset) {
    float v = 0.0f;
    std::memcpy(&v, buf.data() + offset, sizeof(float));
    return v;
}

static int32_t read_int_at(const std::vector<uint8_t>& buf, uint32_t offset) {
    int32_t v = 0;
    std::memcpy(&v, buf.data() + offset, sizeof(int32_t));
    return v;
}

TEST_CASE("std140: scalar and vector sizes/alignments")
{
    CHECK_EQ(std140_size_align("Float").first, 4u);
    CHECK_EQ(std140_size_align("Float").second, 4u);

    CHECK_EQ(std140_size_align("Int").first, 4u);
    CHECK_EQ(std140_size_align("Int").second, 4u);

    CHECK_EQ(std140_size_align("Bool").first, 4u);
    CHECK_EQ(std140_size_align("Bool").second, 4u);

    CHECK_EQ(std140_size_align("Vec2").first, 8u);
    CHECK_EQ(std140_size_align("Vec2").second, 8u);

    // Vec3: data size 12, but base alignment 16 — the std140 quirk.
    CHECK_EQ(std140_size_align("Vec3").first, 12u);
    CHECK_EQ(std140_size_align("Vec3").second, 16u);

    CHECK_EQ(std140_size_align("Vec4").first, 16u);
    CHECK_EQ(std140_size_align("Vec4").second, 16u);

    CHECK_EQ(std140_size_align("Color").first, 16u);
    CHECK_EQ(std140_size_align("Color").second, 16u);

    // Texture is not a UBO field.
    CHECK_EQ(std140_size_align("Texture").first, 0u);
    CHECK_EQ(std140_size_align("Texture").second, 0u);
}

TEST_CASE("std140: single float layout is 16-byte block")
{
    std::vector<MaterialProperty> props = {
        mk("u_strength", "Float"),
    };
    MaterialUboLayout layout = compute_std140_layout(props);
    CHECK_EQ(layout.entries.size(), 1u);
    CHECK_EQ(layout.entries[0].name, "u_strength");
    CHECK_EQ(layout.entries[0].offset, 0u);
    CHECK_EQ(layout.entries[0].size, 4u);
    CHECK_EQ(layout.block_size, 16u);
}

TEST_CASE("std140: vec3 followed by float packs into the same vec4 slot")
{
    // vec3 at offset 0 (size 12, align 16), followed by float at offset 12
    // (align 4 fits into the trailing scalar slot of the vec3). Block size
    // rounds up to 16.
    std::vector<MaterialProperty> props = {
        mk("u_color",    "Vec3"),
        mk("u_strength", "Float"),
    };
    MaterialUboLayout layout = compute_std140_layout(props);
    CHECK_EQ(layout.entries.size(), 2u);
    CHECK_EQ(layout.entries[0].offset, 0u);
    CHECK_EQ(layout.entries[0].size, 12u);
    CHECK_EQ(layout.entries[1].offset, 12u);
    CHECK_EQ(layout.entries[1].size, 4u);
    CHECK_EQ(layout.block_size, 16u);
}

TEST_CASE("std140: float vec3 forces vec3 to next 16-byte boundary")
{
    // float at 0 (size 4), then vec3 needs align 16 so it jumps to 16.
    // vec3 occupies 16..28. Block size rounds up to 32.
    std::vector<MaterialProperty> props = {
        mk("u_strength", "Float"),
        mk("u_color",    "Vec3"),
    };
    MaterialUboLayout layout = compute_std140_layout(props);
    CHECK_EQ(layout.entries[0].offset, 0u);
    CHECK_EQ(layout.entries[1].offset, 16u);
    CHECK_EQ(layout.block_size, 32u);
}

TEST_CASE("std140: mixed types in realistic material")
{
    std::vector<MaterialProperty> props = {
        mk("u_albedo",    "Color"),  // vec4 at 0
        mk("u_metallic",  "Float"),  // float at 16
        mk("u_roughness", "Float"),  // float at 20
        mk("u_ao",        "Float"),  // float at 24
        mk("u_emissive",  "Vec3"),   // vec3 needs 16 align → 32..44
        mk("u_opacity",   "Float"),  // float at 44
    };
    MaterialUboLayout layout = compute_std140_layout(props);
    CHECK_EQ(layout.entries.size(), 6u);
    CHECK_EQ(layout.entries[0].offset, 0u);   // u_albedo
    CHECK_EQ(layout.entries[1].offset, 16u);  // u_metallic
    CHECK_EQ(layout.entries[2].offset, 20u);  // u_roughness
    CHECK_EQ(layout.entries[3].offset, 24u);  // u_ao
    CHECK_EQ(layout.entries[4].offset, 32u);  // u_emissive (jumps from 28 to 32)
    CHECK_EQ(layout.entries[5].offset, 44u);  // u_opacity (fits trailing slot)
    CHECK_EQ(layout.block_size, 48u);         // round up from 48
}

TEST_CASE("std140: Texture properties are skipped")
{
    std::vector<MaterialProperty> props = {
        mk("u_strength", "Float"),
        mk("u_albedo",   "Texture"),
        mk("u_tint",     "Color"),
    };
    MaterialUboLayout layout = compute_std140_layout(props);
    // Only Float + Color end up in the block.
    CHECK_EQ(layout.entries.size(), 2u);
    CHECK_EQ(layout.entries[0].name, "u_strength");
    CHECK_EQ(layout.entries[1].name, "u_tint");
    CHECK_EQ(layout.entries[1].offset, 16u);  // Color aligned to 16
    CHECK_EQ(layout.block_size, 32u);
}

TEST_CASE("synthesize: emits GLSL block with correct types and order")
{
    std::vector<MaterialProperty> props = {
        mk("u_strength", "Float"),
        mk("u_tint",     "Color"),
    };
    MaterialUboLayout layout = compute_std140_layout(props);
    std::string glsl = synthesize_material_ubo_glsl(layout);

    CHECK(glsl.find("layout(std140) uniform MaterialParams") != std::string::npos);
    CHECK(glsl.find("float u_strength;") != std::string::npos);
    CHECK(glsl.find("vec4 u_tint;") != std::string::npos);
    // u_strength declared before u_tint (order preserved).
    CHECK(glsl.find("u_strength") < glsl.find("u_tint"));
}

TEST_CASE("synthesize: empty layout yields empty string")
{
    MaterialUboLayout layout;
    CHECK_EQ(synthesize_material_ubo_glsl(layout), std::string{});
}

TEST_CASE("strip_uniform_decls: removes named uniforms but keeps others")
{
    std::string src =
        "#version 330 core\n"
        "uniform float u_strength;\n"
        "uniform sampler2D u_input;\n"
        "uniform vec4 u_tint;\n"
        "void main() { }\n";

    std::string out = strip_uniform_decls(src, {"u_strength", "u_tint"});
    CHECK(out.find("u_strength") == std::string::npos);
    CHECK(out.find("u_tint") == std::string::npos);
    CHECK(out.find("u_input") != std::string::npos);
    CHECK(out.find("void main()") != std::string::npos);
}

TEST_CASE("strip_uniform_decls: partial prefix match is not removed")
{
    std::string src =
        "uniform float u_strength;\n"
        "uniform float u_strength2;\n";
    std::string out = strip_uniform_decls(src, {"u_strength"});
    // u_strength2 must survive, only the exact u_strength line is dropped.
    CHECK(out.find("u_strength2") != std::string::npos);
    CHECK(out.find("u_strength;") == std::string::npos);
}

TEST_CASE("inject_after_version: places block right after #version")
{
    std::string src =
        "#version 330 core\n"
        "void main() { }\n";
    std::string out = inject_after_version(src, "INJECTED\n");
    // Block must come immediately after the version line.
    size_t version_end = out.find('\n', out.find("#version")) + 1;
    CHECK_EQ(out.substr(version_end, 9), std::string("INJECTED\n"));
}

TEST_CASE("inject_after_version: prepends when there is no version line")
{
    std::string src = "void main() { }\n";
    std::string out = inject_after_version(src, "INJECTED\n");
    CHECK_EQ(out.substr(0, 9), std::string("INJECTED\n"));
}

TEST_CASE("parse_shader_text: material_ubo feature rewrites stage sources")
{
    const std::string shader_text =
        "@program TestShader\n"
        "@features material_ubo\n"
        "@phase opaque\n"
        "@property Float u_strength = 1.0\n"
        "@property Color u_tint = Color(1.0, 1.0, 1.0, 1.0)\n"
        "@property Texture2D u_albedo = \"white\"\n"
        "@stage vertex\n"
        "#version 330 core\n"
        "void main() { gl_Position = vec4(0); }\n"
        "@endstage\n"
        "@stage fragment\n"
        "#version 330 core\n"
        "uniform float u_strength;\n"
        "uniform vec4 u_tint;\n"
        "uniform sampler2D u_albedo;\n"
        "out vec4 FragColor;\n"
        "void main() { FragColor = texture(u_albedo, vec2(0)) * u_tint * u_strength; }\n"
        "@endstage\n"
        "@endphase\n";

    ShaderMultyPhaseProgramm prog = parse_shader_text(shader_text);
    CHECK(prog.has_feature("material_ubo"));
    CHECK_EQ(prog.phases.size(), 1u);

    const auto& phase = prog.phases[0];
    // Layout: only Float and Color enter the UBO; sampler stays out.
    CHECK_EQ(phase.material_ubo_layout.entries.size(), 2u);
    CHECK_EQ(phase.material_ubo_layout.entries[0].name, "u_strength");
    CHECK_EQ(phase.material_ubo_layout.entries[1].name, "u_tint");

    // Fragment source must have the generated block and no raw decls for
    // u_strength / u_tint, but sampler2D u_albedo survives.
    const auto& frag = phase.stages.at("fragment").source;
    CHECK(frag.find("layout(std140) uniform MaterialParams") != std::string::npos);
    CHECK(frag.find("uniform float u_strength;") == std::string::npos);
    CHECK(frag.find("uniform vec4 u_tint;") == std::string::npos);
    CHECK(frag.find("sampler2D u_albedo;") != std::string::npos);

    // The generated block must come after #version.
    size_t ver_pos = frag.find("#version");
    size_t block_pos = frag.find("layout(std140)");
    CHECK(ver_pos != std::string::npos);
    CHECK(block_pos != std::string::npos);
    CHECK(ver_pos < block_pos);
}

TEST_CASE("parse_shader_text: no material_ubo feature leaves sources untouched")
{
    const std::string shader_text =
        "@program LegacyShader\n"
        "@phase opaque\n"
        "@property Float u_strength = 1.0\n"
        "@stage fragment\n"
        "#version 330 core\n"
        "uniform float u_strength;\n"
        "void main() { }\n"
        "@endstage\n"
        "@endphase\n";

    ShaderMultyPhaseProgramm prog = parse_shader_text(shader_text);
    CHECK(!prog.has_feature("material_ubo"));
    CHECK(prog.phases[0].material_ubo_layout.empty());

    const auto& frag = prog.phases[0].stages.at("fragment").source;
    // Legacy path: the raw uniform decl must still be present.
    CHECK(frag.find("uniform float u_strength;") != std::string::npos);
    CHECK(frag.find("MaterialParams") == std::string::npos);
}

// ============================================================================
// std140_pack: value serialization into packed byte buffer
// ============================================================================

TEST_CASE("std140_pack: single float writes 4 bytes at offset 0")
{
    std::vector<MaterialProperty> schema = { mk("u_strength", "Float") };
    std::vector<MaterialProperty> values = { mk_float("u_strength", 0.75) };
    MaterialUboLayout layout = compute_std140_layout(schema);

    std::vector<uint8_t> buf(layout.block_size, 0);
    std140_pack(layout, values, buf.data());

    CHECK_EQ(buf.size(), 16u);
    CHECK_EQ(read_float_at(buf, 0), 0.75f);
    // Remaining bytes untouched (zero).
    for (uint32_t i = 4; i < buf.size(); ++i) {
        CHECK_EQ(buf[i], 0u);
    }
}

TEST_CASE("std140_pack: vec3 + float packs into same 16-byte slot")
{
    std::vector<MaterialProperty> schema = {
        mk("u_color",    "Vec3"),
        mk("u_strength", "Float"),
    };
    std::vector<MaterialProperty> values = {
        mk_vec("u_color", "Vec3", {0.2, 0.4, 0.6}),
        mk_float("u_strength", 0.9),
    };
    MaterialUboLayout layout = compute_std140_layout(schema);
    CHECK_EQ(layout.block_size, 16u);

    std::vector<uint8_t> buf(layout.block_size, 0);
    std140_pack(layout, values, buf.data());

    CHECK_EQ(read_float_at(buf, 0),  0.2f);
    CHECK_EQ(read_float_at(buf, 4),  0.4f);
    CHECK_EQ(read_float_at(buf, 8),  0.6f);
    CHECK_EQ(read_float_at(buf, 12), 0.9f);  // float in the trailing slot
}

TEST_CASE("std140_pack: float + vec3 jumps vec3 to offset 16")
{
    std::vector<MaterialProperty> schema = {
        mk("u_strength", "Float"),
        mk("u_color",    "Vec3"),
    };
    std::vector<MaterialProperty> values = {
        mk_float("u_strength", 1.5),
        mk_vec("u_color", "Vec3", {0.1, 0.2, 0.3}),
    };
    MaterialUboLayout layout = compute_std140_layout(schema);
    CHECK_EQ(layout.block_size, 32u);

    std::vector<uint8_t> buf(layout.block_size, 0);
    std140_pack(layout, values, buf.data());

    CHECK_EQ(read_float_at(buf, 0),  1.5f);
    // Bytes [4..16) are padding — must remain zero.
    for (uint32_t i = 4; i < 16; ++i) CHECK_EQ(buf[i], 0u);
    CHECK_EQ(read_float_at(buf, 16), 0.1f);
    CHECK_EQ(read_float_at(buf, 20), 0.2f);
    CHECK_EQ(read_float_at(buf, 24), 0.3f);
    CHECK_EQ(read_float_at(buf, 28), 0.0f);  // padding slot
}

TEST_CASE("std140_pack: Color packs 4 floats at aligned offset")
{
    std::vector<MaterialProperty> schema = {
        mk("u_strength", "Float"),
        mk("u_tint",     "Color"),
    };
    std::vector<MaterialProperty> values = {
        mk_float("u_strength", 2.0),
        mk_vec("u_tint", "Color", {0.9, 0.8, 0.7, 0.6}),
    };
    MaterialUboLayout layout = compute_std140_layout(schema);
    CHECK_EQ(layout.block_size, 32u);

    std::vector<uint8_t> buf(layout.block_size, 0);
    std140_pack(layout, values, buf.data());

    CHECK_EQ(read_float_at(buf, 0),  2.0f);
    // [4..16) padding.
    CHECK_EQ(read_float_at(buf, 16), 0.9f);
    CHECK_EQ(read_float_at(buf, 20), 0.8f);
    CHECK_EQ(read_float_at(buf, 24), 0.7f);
    CHECK_EQ(read_float_at(buf, 28), 0.6f);
}

TEST_CASE("std140_pack: Int and Bool")
{
    std::vector<MaterialProperty> schema = {
        mk("u_count",  "Int"),
        mk("u_enable", "Bool"),
    };
    std::vector<MaterialProperty> values = {
        mk_int("u_count", 42),
        mk_bool("u_enable", true),
    };
    MaterialUboLayout layout = compute_std140_layout(schema);
    CHECK_EQ(layout.block_size, 16u);

    std::vector<uint8_t> buf(layout.block_size, 0);
    std140_pack(layout, values, buf.data());

    CHECK_EQ(read_int_at(buf, 0), 42);
    CHECK_EQ(read_int_at(buf, 4), 1);  // Bool(true) → int 1
}

TEST_CASE("std140_pack: realistic PBR material")
{
    std::vector<MaterialProperty> schema = {
        mk("u_albedo",    "Color"),
        mk("u_metallic",  "Float"),
        mk("u_roughness", "Float"),
        mk("u_ao",        "Float"),
        mk("u_emissive",  "Vec3"),
        mk("u_opacity",   "Float"),
    };
    std::vector<MaterialProperty> values = {
        mk_vec("u_albedo", "Color", {0.1, 0.2, 0.3, 1.0}),
        mk_float("u_metallic",  0.5),
        mk_float("u_roughness", 0.25),
        mk_float("u_ao",        1.0),
        mk_vec("u_emissive", "Vec3", {10.0, 20.0, 30.0}),
        mk_float("u_opacity",   0.8),
    };
    MaterialUboLayout layout = compute_std140_layout(schema);
    CHECK_EQ(layout.block_size, 48u);

    std::vector<uint8_t> buf(layout.block_size, 0);
    std140_pack(layout, values, buf.data());

    CHECK_EQ(read_float_at(buf, 0),  0.1f);
    CHECK_EQ(read_float_at(buf, 4),  0.2f);
    CHECK_EQ(read_float_at(buf, 8),  0.3f);
    CHECK_EQ(read_float_at(buf, 12), 1.0f);
    CHECK_EQ(read_float_at(buf, 16), 0.5f);   // u_metallic
    CHECK_EQ(read_float_at(buf, 20), 0.25f);  // u_roughness
    CHECK_EQ(read_float_at(buf, 24), 1.0f);   // u_ao
    // Offset 28 is padding to align u_emissive vec3 at 32.
    CHECK_EQ(read_float_at(buf, 28), 0.0f);
    CHECK_EQ(read_float_at(buf, 32), 10.0f);  // u_emissive
    CHECK_EQ(read_float_at(buf, 36), 20.0f);
    CHECK_EQ(read_float_at(buf, 40), 30.0f);
    CHECK_EQ(read_float_at(buf, 44), 0.8f);   // u_opacity trailing slot
}

TEST_CASE("std140_pack: missing value leaves the slot alone")
{
    std::vector<MaterialProperty> schema = {
        mk("u_a", "Float"),
        mk("u_b", "Float"),
    };
    // Only provide u_b — u_a should remain whatever was in the buffer.
    std::vector<MaterialProperty> values = { mk_float("u_b", 7.0) };
    MaterialUboLayout layout = compute_std140_layout(schema);

    std::vector<uint8_t> buf(layout.block_size, 0);
    // Pre-fill u_a slot with a sentinel value — packer must not touch it.
    float sentinel = -12.5f;
    std::memcpy(buf.data() + 0, &sentinel, sizeof(float));

    std140_pack(layout, values, buf.data());

    CHECK_EQ(read_float_at(buf, 0), sentinel);  // untouched
    CHECK_EQ(read_float_at(buf, 4), 7.0f);
}

TEST_CASE("std140_pack: type mismatch is skipped")
{
    std::vector<MaterialProperty> schema = { mk("u_strength", "Float") };
    // Wrong type provided — should not be written.
    std::vector<MaterialProperty> values = { mk_vec("u_strength", "Vec3", {1, 2, 3}) };
    MaterialUboLayout layout = compute_std140_layout(schema);

    std::vector<uint8_t> buf(layout.block_size, 0);
    std140_pack(layout, values, buf.data());

    // Buffer remains zero — mismatched type is ignored.
    for (uint32_t i = 0; i < buf.size(); ++i) CHECK_EQ(buf[i], 0u);
}

TEST_CASE("std140_pack: Texture properties in values list are ignored")
{
    std::vector<MaterialProperty> schema = {
        mk("u_strength", "Float"),
    };
    std::vector<MaterialProperty> values = {
        // Texture is in values but not in layout — schema is the floor.
        mk("u_albedo", "Texture"),
        mk_float("u_strength", 0.5),
    };
    MaterialUboLayout layout = compute_std140_layout(schema);

    std::vector<uint8_t> buf(layout.block_size, 0);
    std140_pack(layout, values, buf.data());

    CHECK_EQ(read_float_at(buf, 0), 0.5f);
}
