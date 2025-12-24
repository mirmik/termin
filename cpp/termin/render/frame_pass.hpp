#pragma once

#include <string>
#include <set>
#include <vector>
#include <utility>
#include <functional>
#include <any>

namespace termin {

/**
 * Base class for frame passes in the render graph.
 *
 * A frame pass declares which resources it reads and writes.
 * The FrameGraph uses this information to build a dependency graph
 * and execute passes in topological order.
 *
 * Inplace passes read and write the same physical resource under
 * different names (e.g., read "empty", write "color").
 */
class FramePass {
public:
    std::string pass_name;
    std::set<std::string> reads;
    std::set<std::string> writes;
    bool enabled = true;

    // Debug configuration
    std::string debug_internal_symbol;

    FramePass() = default;

    FramePass(
        std::string name,
        std::set<std::string> reads_set = {},
        std::set<std::string> writes_set = {}
    ) : pass_name(std::move(name)),
        reads(std::move(reads_set)),
        writes(std::move(writes_set)) {}

    virtual ~FramePass() = default;

    /**
     * Returns list of inplace aliases: pairs of (read_name, write_name)
     * where both names refer to the same physical resource.
     *
     * Empty list means the pass is not inplace.
     */
    virtual std::vector<std::pair<std::string, std::string>> get_inplace_aliases() const {
        return {};
    }

    /**
     * Whether this pass is inplace (reads and writes same resource).
     */
    bool is_inplace() const {
        return !get_inplace_aliases().empty();
    }

    /**
     * Returns list of internal debug symbols available for this pass.
     * Used for debugging intermediate render states.
     */
    virtual std::vector<std::string> get_internal_symbols() const {
        return {};
    }

    /**
     * Set active internal debug point.
     */
    void set_debug_internal_point(const std::string& symbol) {
        debug_internal_symbol = symbol;
    }

    /**
     * Clear internal debug point.
     */
    void clear_debug_internal_point() {
        debug_internal_symbol.clear();
    }

    /**
     * Get current internal debug point.
     */
    const std::string& get_debug_internal_point() const {
        return debug_internal_symbol;
    }

    /**
     * Returns set of all resources this pass needs (reads + writes).
     * Subclasses can override if requirements are dynamic.
     */
    virtual std::set<std::string> required_resources() const {
        std::set<std::string> result = reads;
        result.insert(writes.begin(), writes.end());
        return result;
    }
};

} // namespace termin
