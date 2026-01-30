// render_pipeline.hpp - C++ wrapper for tc_pipeline with specs storage
#pragma once

#include "termin/render/resource_spec.hpp"
#include "termin/render/fbo_pool.hpp"
#include "termin/lighting/shadow.hpp"
#include <vector>
#include <string>
#include <memory>

extern "C" {
#include "render/tc_pipeline.h"
}

namespace termin {

/**
 * C++ render pipeline wrapper.
 *
 * Uses tc_pipeline_handle from the pipeline pool.
 * Stores ResourceSpecs and manages FBO pool.
 */
class RenderPipeline {
public:
    tc_pipeline_handle handle_;
    std::vector<ResourceSpec> specs_;
    std::string name_;
    FBOPool fbo_pool_;
    std::unordered_map<std::string, std::unique_ptr<ShadowMapArrayResource>> shadow_arrays_;

    RenderPipeline(const std::string& name = "default");
    ~RenderPipeline();

    // Non-copyable
    RenderPipeline(const RenderPipeline&) = delete;
    RenderPipeline& operator=(const RenderPipeline&) = delete;

    // Move
    RenderPipeline(RenderPipeline&& other) noexcept;
    RenderPipeline& operator=(RenderPipeline&& other) noexcept;

    // Access tc_pipeline
    tc_pipeline* ptr() { return tc_pipeline_get_ptr(handle_); }
    const tc_pipeline* ptr() const { return tc_pipeline_get_ptr(handle_); }

    // Access handle
    tc_pipeline_handle handle() const { return handle_; }

    // Check if valid
    bool is_valid() const { return tc_pipeline_pool_alive(handle_); }

    // Name
    const std::string& name() const { return name_; }
    void set_name(const std::string& name);

    // Pass management (delegates to tc_pipeline)
    void add_pass(tc_pass* pass);
    void remove_pass(tc_pass* pass);
    void insert_pass_before(tc_pass* pass, tc_pass* before);
    tc_pass* get_pass(const std::string& name);
    tc_pass* get_pass_at(size_t index);
    size_t pass_count() const;

    // Specs management
    void add_spec(const ResourceSpec& spec);
    void clear_specs();
    size_t spec_count() const { return specs_.size(); }
    const ResourceSpec* get_spec_at(size_t index) const;
    const std::vector<ResourceSpec>& specs() const { return specs_; }

    // Collect all specs (pipeline + pass specs)
    std::vector<ResourceSpec> collect_specs() const;

    // FBO pool access
    FBOPool& fbo_pool() { return fbo_pool_; }
    const FBOPool& fbo_pool() const { return fbo_pool_; }

    // Get specific FBO by name (for C# bindings)
    FramebufferHandle* get_fbo(const std::string& name) {
        return fbo_pool_.get(name);
    }

    // Shadow arrays access
    std::unordered_map<std::string, std::unique_ptr<ShadowMapArrayResource>>& shadow_arrays() {
        return shadow_arrays_;
    }

    // Cast from handle (uses cpp_owner field)
    static RenderPipeline* from_handle(tc_pipeline_handle h);
};

} // namespace termin
