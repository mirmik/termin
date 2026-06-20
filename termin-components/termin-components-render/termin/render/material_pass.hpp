// material_pass.hpp - Post-processing pass using a Material.
//
// Uses TcMaterial for rendering. Per-frame uniform updates come via
// TcMaterial::set_uniform_* on the referenced material (Unity-style
// Material.SetFloat / SetMatrix / ...); the pass itself is agnostic.

#pragma once

#include <set>
#include <string>
#include <unordered_map>
#include <vector>

#include <termin/render/execute_context.hpp>
#include <termin/render/frame_pass.hpp>
#include <tgfx/handles.hpp>
#include <tgfx/tgfx_material_handle.hpp>

namespace termin {

class ENTITY_API MaterialPass : public CxxFramePass {
public:
    TcMaterial material;
    std::string output_res = "color";
    std::string output_res_target;
    std::unordered_map<std::string, std::string> texture_resources;
    std::unordered_map<std::string, std::string> extra_resources;

    tc_value serialize_texture_resources() const;
    void deserialize_texture_resources(const tc_value* value);
    tc_value serialize_extra_resources() const;
    void deserialize_extra_resources(const tc_value* value);

    INSPECT_FIELD(MaterialPass, material, "Material", "tc_material")
    INSPECT_FIELD(MaterialPass, output_res, "Output Resource", "string")
    INSPECT_FIELD(MaterialPass, output_res_target, "Output Target", "string")
    INSPECT_TYPE_METADATA(MaterialPass, graph, make_pass_graph_metadata(
        {{"output_res_target", "fbo"}},
        {{"output_res", "fbo"}},
        {{"output_res_target", "output_res"}}
    ))

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
    bool set_graph_resource_input(
        const std::string& socket_name,
        const std::string& resource_name
    ) override;
    std::vector<std::pair<std::string, std::string>> get_inplace_aliases() const override;
    void destroy() override;
};

SERIALIZABLE_FIELD(MaterialPass, texture_resources, serialize_texture_resources(), deserialize_texture_resources(val))
SERIALIZABLE_FIELD(MaterialPass, extra_resources, serialize_extra_resources(), deserialize_extra_resources(val))

} // namespace termin
