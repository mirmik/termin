// render_pipeline.hpp - C++ wrapper for tc_pipeline with specs storage
#pragma once

#include "termin/render/resource_spec.hpp"
#include <vector>
#include <string>

extern "C" {
#include "tc_pipeline.h"
}

namespace termin {

/**
 * C++ render pipeline wrapper.
 *
 * Owns a tc_pipeline and stores ResourceSpecs.
 * tc_pipeline->py_wrapper points back to this object for casting.
 */
class RenderPipeline {
public:
    tc_pipeline pipeline_;
    std::vector<ResourceSpec> specs_;
    std::string name_;

    RenderPipeline(const std::string& name = "default");
    ~RenderPipeline();

    // Non-copyable
    RenderPipeline(const RenderPipeline&) = delete;
    RenderPipeline& operator=(const RenderPipeline&) = delete;

    // Move
    RenderPipeline(RenderPipeline&& other) noexcept;
    RenderPipeline& operator=(RenderPipeline&& other) noexcept;

    // Access tc_pipeline
    tc_pipeline* ptr() { return &pipeline_; }
    const tc_pipeline* ptr() const { return &pipeline_; }

    // Name
    const std::string& name() const { return name_; }
    void set_name(const std::string& name) { name_ = name; }

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

    // Collect all specs (pipeline + pass specs) into tc_resource_spec array
    size_t collect_specs(tc_resource_spec* out_specs, size_t max_count) const;

    // Cast from tc_pipeline* (uses cpp_owner field)
    static RenderPipeline* from_tc_pipeline(tc_pipeline* p);
};

} // namespace termin
