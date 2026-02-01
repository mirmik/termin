// material_pass.hpp - Post-processing pass using a Material
//
// C++ port of Python MaterialPass. Uses TcMaterial for rendering with
// optional before_draw callback for custom uniform setup.

#pragma once

#include "termin/render/frame_pass.hpp"
#include "termin/render/graphics_backend.hpp"
#include "termin/render/handles.hpp"

#include <string>
#include <unordered_map>
#include <functional>
#include <set>

extern "C" {
#include "tc_material.h"
}

namespace termin {

class TcShader;

// Callback signature for before_draw
// Called after shader is bound but before drawing, allows setting custom uniforms
using BeforeDrawCallback = std::function<void(TcShader*)>;

// MaterialPass - Post-processing pass using a Material asset
//
// Renders a fullscreen quad with the specified material's shader.
// Supports:
// - Binding framegraph resources as textures
// - before_draw callback for custom uniform setup
// - Material uniforms and textures
class MaterialPass : public CxxFramePass {
public:
    // Fields stored directly (no duplication with base)
    std::string material_name_;
    std::string output_res_ = "color";

    // Texture resources: uniform_name -> resource_name
    std::unordered_map<std::string, std::string> texture_resources_;

    // Extra resources: resource_name -> uniform_name
    std::unordered_map<std::string, std::string> extra_resources_;

private:
    // Material handle
    tc_material_handle material_handle_;

    // Callback invoked before drawing
    BeforeDrawCallback before_draw_callback_;

    // Fullscreen quad VAO (lazily created)
    static uint32_t s_quad_vao;
    static uint32_t s_quad_vbo;

public:
    MaterialPass();
    ~MaterialPass() override;

    // Material name
    const std::string& material_name() const { return material_name_; }
    void set_material_name(const std::string& name);

    // Output resource name
    const std::string& output_res() const { return output_res_; }
    void set_output_res(const std::string& res) { output_res_ = res; }

    // Texture resource bindings
    void set_texture_resource(const std::string& uniform_name, const std::string& resource_name);
    void add_resource(const std::string& resource_name, const std::string& uniform_name = "");
    void remove_resource(const std::string& resource_name);

    // Before draw callback
    void set_before_draw(BeforeDrawCallback callback);
    BeforeDrawCallback before_draw() const { return before_draw_callback_; }

    // CxxFramePass overrides
    void execute(ExecuteContext& ctx) override;
    std::set<const char*> compute_reads() const override;
    std::set<const char*> compute_writes() const override;
    void destroy() override;

private:
    // Load material by name
    void load_material();

    // Draw fullscreen quad
    void draw_fullscreen_quad(GraphicsBackend* graphics);

    // Ensure quad VAO exists
    static void ensure_quad_vao();
};

} // namespace termin
