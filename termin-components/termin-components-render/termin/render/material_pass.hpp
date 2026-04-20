// material_pass.hpp - Post-processing pass using a Material.
//
// Uses TcMaterial for rendering. Per-frame uniform updates come via
// TcMaterial::set_uniform_* on the referenced material (Unity-style
// Material.SetFloat / SetMatrix / ...); the pass itself is agnostic.

#pragma once

#include <set>
#include <string>
#include <unordered_map>

#include <termin/render/execute_context.hpp>
#include <termin/render/frame_pass.hpp>
#include <tgfx/handles.hpp>
#include <tgfx/tgfx_material_handle.hpp>

namespace termin {

class MaterialPass : public CxxFramePass {
public:
    TcMaterial material;
    std::string output_res = "color";
    std::unordered_map<std::string, std::string> texture_resources;
    std::unordered_map<std::string, std::string> extra_resources;

    INSPECT_FIELD(MaterialPass, material, "Material", "tc_material")
    INSPECT_FIELD(MaterialPass, output_res, "Output Resource", "string")

private:
    static uint32_t s_quad_vao;
    static uint32_t s_quad_vbo;

public:
    MaterialPass();
    ~MaterialPass() override;

    void set_texture_resource(const std::string& uniform_name, const std::string& resource_name);
    void add_resource(const std::string& resource_name, const std::string& uniform_name = "");
    void remove_resource(const std::string& resource_name);

    void execute(ExecuteContext& ctx) override;
    std::set<const char*> compute_reads() const override;
    std::set<const char*> compute_writes() const override;
    void destroy() override;
};

} // namespace termin
