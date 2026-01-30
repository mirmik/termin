// render_pipeline.cpp - C++ RenderPipeline implementation
#include "termin/render/render_pipeline.hpp"
#include "tc_log.hpp"
#include <cstring>
#include <iostream>

extern "C" {
#include "render/tc_pass.h"
}

namespace termin {

RenderPipeline::RenderPipeline(const std::string& name)
    : name_(name)
{
    // Initialize tc_pipeline fields directly (don't use tc_pipeline_create)
    pipeline_.name = strdup(name.c_str());
    pipeline_.passes = nullptr;
    pipeline_.pass_count = 0;
    pipeline_.pass_capacity = 0;
    pipeline_.cpp_owner = this;     // Point back for casting
    pipeline_.py_wrapper = nullptr; // Set by Python bindings if needed
}

RenderPipeline::~RenderPipeline() {
    // Release all passes (release handles cleanup when ref_count reaches 0)
    for (size_t i = 0; i < pipeline_.pass_count; i++) {
        tc_pass* pass = pipeline_.passes[i];
        if (pass) {
            pass->owner_pipeline = nullptr;
            tc_pass_release(pass);
        }
    }

    free(pipeline_.passes);
    free(pipeline_.name);
}

RenderPipeline::RenderPipeline(RenderPipeline&& other) noexcept
    : pipeline_(other.pipeline_),
      specs_(std::move(other.specs_)),
      name_(std::move(other.name_)),
      fbo_pool_(std::move(other.fbo_pool_)),
      shadow_arrays_(std::move(other.shadow_arrays_))
{
    // Update cpp_owner to point to this
    pipeline_.cpp_owner = this;

    // Clear other
    other.pipeline_.name = nullptr;
    other.pipeline_.passes = nullptr;
    other.pipeline_.pass_count = 0;
    other.pipeline_.pass_capacity = 0;
    other.pipeline_.cpp_owner = nullptr;
}

RenderPipeline& RenderPipeline::operator=(RenderPipeline&& other) noexcept {
    if (this != &other) {
        // Release current passes
        for (size_t i = 0; i < pipeline_.pass_count; i++) {
            tc_pass* pass = pipeline_.passes[i];
            if (pass) {
                pass->owner_pipeline = nullptr;
                tc_pass_release(pass);
            }
        }
        free(pipeline_.passes);
        free(pipeline_.name);

        // Move from other
        pipeline_ = other.pipeline_;
        specs_ = std::move(other.specs_);
        name_ = std::move(other.name_);
        fbo_pool_ = std::move(other.fbo_pool_);
        shadow_arrays_ = std::move(other.shadow_arrays_);
        pipeline_.cpp_owner = this;

        // Clear other
        other.pipeline_.name = nullptr;
        other.pipeline_.passes = nullptr;
        other.pipeline_.pass_count = 0;
        other.pipeline_.pass_capacity = 0;
        other.pipeline_.cpp_owner = nullptr;
    }
    return *this;
}

void RenderPipeline::add_pass(tc_pass* pass) {
    if (!pass) return;

    // Check if pass is already in a pipeline
    if (pass->owner_pipeline) {
        if (pass->owner_pipeline == &pipeline_) {
            tc::Log::warn("RenderPipeline::add_pass: pass '%s' is already in this pipeline '%s'",
                          pass->pass_name ? pass->pass_name : "(unnamed)",
                          name_.c_str());
        } else {
            tc::Log::warn("RenderPipeline::add_pass: pass '%s' is already in another pipeline, removing first",
                          pass->pass_name ? pass->pass_name : "(unnamed)");
            // Remove from old pipeline
            RenderPipeline* old_owner = from_tc_pipeline(pass->owner_pipeline);
            if (old_owner) {
                old_owner->remove_pass(pass);
            }
        }
    }

    // Ensure capacity
    if (pipeline_.pass_count >= pipeline_.pass_capacity) {
        size_t new_capacity = pipeline_.pass_capacity == 0 ? 8 : pipeline_.pass_capacity * 2;
        tc_pass** new_passes = static_cast<tc_pass**>(
            realloc(pipeline_.passes, new_capacity * sizeof(tc_pass*))
        );
        if (!new_passes) return;
        pipeline_.passes = new_passes;
        pipeline_.pass_capacity = new_capacity;
    }

    tc_pass_retain(pass);
    pass->owner_pipeline = &pipeline_;
    pipeline_.passes[pipeline_.pass_count++] = pass;
}

void RenderPipeline::remove_pass(tc_pass* pass) {
    if (!pass) return;

    // Find pass index
    size_t idx = pipeline_.pass_count;
    for (size_t i = 0; i < pipeline_.pass_count; i++) {
        if (pipeline_.passes[i] == pass) {
            idx = i;
            break;
        }
    }
    if (idx >= pipeline_.pass_count) return;

    // Shift elements
    memmove(&pipeline_.passes[idx], &pipeline_.passes[idx + 1],
            (pipeline_.pass_count - idx - 1) * sizeof(tc_pass*));
    pipeline_.pass_count--;

    pass->owner_pipeline = nullptr;
    tc_pass_release(pass);
}

void RenderPipeline::insert_pass_before(tc_pass* pass, tc_pass* before) {
    if (!pass) return;

    // Ensure capacity
    if (pipeline_.pass_count >= pipeline_.pass_capacity) {
        size_t new_capacity = pipeline_.pass_capacity == 0 ? 8 : pipeline_.pass_capacity * 2;
        tc_pass** new_passes = static_cast<tc_pass**>(
            realloc(pipeline_.passes, new_capacity * sizeof(tc_pass*))
        );
        if (!new_passes) return;
        pipeline_.passes = new_passes;
        pipeline_.pass_capacity = new_capacity;
    }

    tc_pass_retain(pass);
    pass->owner_pipeline = &pipeline_;

    if (!before) {
        // Insert at beginning
        memmove(&pipeline_.passes[1], &pipeline_.passes[0],
                pipeline_.pass_count * sizeof(tc_pass*));
        pipeline_.passes[0] = pass;
        pipeline_.pass_count++;
        return;
    }

    // Find before index
    size_t idx = pipeline_.pass_count;
    for (size_t i = 0; i < pipeline_.pass_count; i++) {
        if (pipeline_.passes[i] == before) {
            idx = i;
            break;
        }
    }

    if (idx >= pipeline_.pass_count) {
        // Not found, append
        pipeline_.passes[pipeline_.pass_count++] = pass;
    } else {
        // Insert before idx
        memmove(&pipeline_.passes[idx + 1], &pipeline_.passes[idx],
                (pipeline_.pass_count - idx) * sizeof(tc_pass*));
        pipeline_.passes[idx] = pass;
        pipeline_.pass_count++;
    }
}

tc_pass* RenderPipeline::get_pass(const std::string& name) {
    for (size_t i = 0; i < pipeline_.pass_count; i++) {
        tc_pass* pass = pipeline_.passes[i];
        if (pass && pass->pass_name && name == pass->pass_name) {
            return pass;
        }
    }
    return nullptr;
}

tc_pass* RenderPipeline::get_pass_at(size_t index) {
    if (index >= pipeline_.pass_count) return nullptr;
    return pipeline_.passes[index];
}

size_t RenderPipeline::pass_count() const {
    return pipeline_.pass_count;
}

void RenderPipeline::add_spec(const ResourceSpec& spec) {
    specs_.push_back(spec);
}

void RenderPipeline::clear_specs() {
    specs_.clear();
}

const ResourceSpec* RenderPipeline::get_spec_at(size_t index) const {
    if (index >= specs_.size()) return nullptr;
    return &specs_[index];
}

std::vector<ResourceSpec> RenderPipeline::collect_specs() const {
    std::vector<ResourceSpec> result;

    // Pipeline-level specs
    result.insert(result.end(), specs_.begin(), specs_.end());

    // Pass specs
    for (size_t i = 0; i < pipeline_.pass_count; i++) {
        tc_pass* pass = pipeline_.passes[i];
        if (pass && pass->enabled) {
            ResourceSpec pass_specs[16];
            size_t pass_spec_count = tc_pass_get_resource_specs(pass, pass_specs, 16);
            for (size_t j = 0; j < pass_spec_count; j++) {
                result.push_back(pass_specs[j]);
            }
        }
    }

    return result;
}

RenderPipeline* RenderPipeline::from_tc_pipeline(tc_pipeline* p) {
    if (!p || !p->cpp_owner) return nullptr;
    return static_cast<RenderPipeline*>(p->cpp_owner);
}

} // namespace termin
