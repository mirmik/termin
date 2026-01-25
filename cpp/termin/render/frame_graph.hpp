#pragma once

#include <vector>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <deque>
#include <stdexcept>

#include "termin/render/frame_pass.hpp"

namespace termin {

/**
 * Frame graph error types.
 */
class FrameGraphError : public std::runtime_error {
public:
    using std::runtime_error::runtime_error;
};

class FrameGraphMultiWriterError : public FrameGraphError {
public:
    using FrameGraphError::FrameGraphError;
};

class FrameGraphCycleError : public FrameGraphError {
public:
    using FrameGraphError::FrameGraphError;
};

/**
 * Frame graph for scheduling render passes.
 *
 * Takes a list of FramePass objects, builds a dependency graph based on
 * read/write relationships, and produces a topologically sorted execution order.
 *
 * Features:
 * - Detects multi-writer conflicts (same resource written by multiple passes)
 * - Detects dependency cycles
 * - Handles inplace passes (read and write same physical resource)
 * - Prioritizes normal passes over inplace passes for better scheduling
 */
class FrameGraph {
public:
    /**
     * Construct frame graph from list of passes.
     *
     * Only enabled passes are considered for scheduling.
     * Disabled passes are ignored.
     */
    explicit FrameGraph(const std::vector<FramePass*>& passes) {
        for (auto* p : passes) {
            if (p && p->get_enabled()) {
                passes_.push_back(p);
            }
        }
    }

    /**
     * Build execution schedule.
     *
     * Returns passes in topological order respecting read-after-write dependencies.
     *
     * @throws FrameGraphMultiWriterError if same resource is written by multiple passes
     * @throws FrameGraphCycleError if dependency cycle is detected
     * @throws FrameGraphError for other validation errors
     */
    std::vector<FramePass*> build_schedule() {
        if (passes_.empty()) {
            return {};
        }

        // Build dependency graph
        auto [adjacency, in_degree] = build_dependency_graph();

        size_t n = passes_.size();

        // Two queues: normal passes have priority over inplace passes
        std::deque<size_t> ready_normal;
        std::deque<size_t> ready_inplace;

        for (size_t i = 0; i < n; ++i) {
            if (in_degree[i] == 0) {
                if (passes_[i]->is_inplace()) {
                    ready_inplace.push_back(i);
                } else {
                    ready_normal.push_back(i);
                }
            }
        }

        std::vector<size_t> schedule_indices;
        schedule_indices.reserve(n);

        while (!ready_normal.empty() || !ready_inplace.empty()) {
            size_t idx;
            if (!ready_normal.empty()) {
                idx = ready_normal.front();
                ready_normal.pop_front();
            } else {
                idx = ready_inplace.front();
                ready_inplace.pop_front();
            }

            schedule_indices.push_back(idx);

            for (size_t dep : adjacency[idx]) {
                in_degree[dep]--;
                if (in_degree[dep] == 0) {
                    if (passes_[dep]->is_inplace()) {
                        ready_inplace.push_back(dep);
                    } else {
                        ready_normal.push_back(dep);
                    }
                }
            }
        }

        if (schedule_indices.size() != n) {
            // Cycle detected - find problematic passes
            std::string problematic;
            for (size_t i = 0; i < n; ++i) {
                if (in_degree[i] > 0) {
                    if (!problematic.empty()) problematic += ", ";
                    problematic += passes_[i]->get_pass_name();
                }
            }
            throw FrameGraphCycleError(
                "Frame graph contains a dependency cycle involving passes: " + problematic
            );
        }

        // Convert indices to pass pointers
        std::vector<FramePass*> result;
        result.reserve(n);
        for (size_t idx : schedule_indices) {
            result.push_back(passes_[idx]);
        }

        return result;
    }

    /**
     * Get canonical resource name.
     *
     * Resources that are aliased (via inplace passes) share the same
     * canonical name, indicating they use the same physical FBO.
     */
    std::string canonical_resource(const std::string& name) const {
        auto it = canonical_resources_.find(name);
        return it != canonical_resources_.end() ? it->second : name;
    }

    /**
     * Get FBO alias groups.
     *
     * Returns map from canonical name to set of all aliased names.
     */
    std::unordered_map<std::string, std::unordered_set<std::string>> fbo_alias_groups() const {
        std::unordered_map<std::string, std::unordered_set<std::string>> groups;
        for (const auto& [res, canon] : canonical_resources_) {
            groups[canon].insert(res);
        }
        return groups;
    }

private:
    std::vector<FramePass*> passes_;
    std::unordered_map<std::string, std::string> canonical_resources_;

    struct DependencyGraph {
        std::vector<std::vector<size_t>> adjacency;
        std::vector<int> in_degree;
    };

    DependencyGraph build_dependency_graph() {
        size_t n = passes_.size();

        // writer_for[resource] = index of pass that writes it
        std::unordered_map<std::string, size_t> writer_for;
        // readers_for[resource] = list of pass indices that read it
        std::unordered_map<std::string, std::vector<size_t>> readers_for;
        // modified_inputs = resources that are input to an inplace pass
        std::unordered_set<std::string> modified_inputs;
        // canonical name mapping
        std::unordered_map<std::string, std::string> canonical;

        // First pass: collect writers, readers, validate inplace
        for (size_t idx = 0; idx < n; ++idx) {
            FramePass* p = passes_[idx];

            // Validate inplace aliases
            auto aliases = p->get_inplace_aliases();
            for (const auto& [src, dst] : aliases) {
                if (p->reads.find(src) == p->reads.end()) {
                    throw FrameGraphError(
                        "Inplace alias source '" + src + "' not in reads of pass '" + p->get_pass_name() + "'"
                    );
                }
                if (p->writes.find(dst) == p->writes.end()) {
                    throw FrameGraphError(
                        "Inplace alias target '" + dst + "' not in writes of pass '" + p->get_pass_name() + "'"
                    );
                }
                if (modified_inputs.count(src)) {
                    throw FrameGraphError(
                        "Resource '" + src + "' is already modified by another inplace pass"
                    );
                }
                modified_inputs.insert(src);
            }

            // Collect writers
            for (const auto& res : p->writes) {
                if (writer_for.count(res)) {
                    size_t other_idx = writer_for[res];
                    throw FrameGraphMultiWriterError(
                        "Resource '" + res + "' is written by multiple passes: '" +
                        passes_[other_idx]->get_pass_name() + "' and '" + p->get_pass_name() + "'"
                    );
                }
                writer_for[res] = idx;
                if (canonical.find(res) == canonical.end()) {
                    canonical[res] = res;
                }
            }

            // Collect readers
            for (const auto& res : p->reads) {
                readers_for[res].push_back(idx);
                if (canonical.find(res) == canonical.end()) {
                    canonical[res] = res;
                }
            }
        }

        // Process inplace aliases to unify canonical names
        for (FramePass* p : passes_) {
            for (const auto& [src, dst] : p->get_inplace_aliases()) {
                std::string src_canon = canonical[src];
                canonical[dst] = src_canon;
            }
        }

        canonical_resources_ = canonical;

        // Build adjacency list and in-degree
        std::vector<std::vector<size_t>> adjacency(n);
        std::vector<int> in_degree(n, 0);

        for (const auto& [res, w_idx] : writer_for) {
            auto it = readers_for.find(res);
            if (it == readers_for.end()) continue;

            for (size_t r_idx : it->second) {
                if (r_idx == w_idx) continue;  // No self-loops

                // Check if edge already exists
                bool exists = false;
                for (size_t existing : adjacency[w_idx]) {
                    if (existing == r_idx) {
                        exists = true;
                        break;
                    }
                }

                if (!exists) {
                    adjacency[w_idx].push_back(r_idx);
                    in_degree[r_idx]++;
                }
            }
        }

        return {std::move(adjacency), std::move(in_degree)};
    }
};

} // namespace termin
