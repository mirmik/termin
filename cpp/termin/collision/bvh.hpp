#pragma once

/**
 * @file bvh.hpp
 * @brief Bounding Volume Hierarchy for broad-phase collision detection.
 *
 * Features:
 * - Dynamic insert/remove/update
 * - Fattened AABBs for movement tolerance (reduces tree updates)
 * - SAH (Surface Area Heuristic) for quality splits
 * - O(log n) query operations
 */

#include "termin/geom/aabb.hpp"
#include "termin/geom/ray3.hpp"
#include "termin/colliders/colliders.hpp"
#include <vector>
#include <unordered_map>
#include <algorithm>
#include <limits>
#include <cstdint>

namespace termin {
namespace collision {

using namespace colliders;

/// Margin added to AABBs to reduce updates on small movements
constexpr double BVH_AABB_MARGIN = 0.1;

/// Multiplier for velocity-based AABB extension
constexpr double BVH_VELOCITY_MULTIPLIER = 2.0;

/// Index representing null/invalid node
constexpr int32_t BVH_NULL_NODE = -1;

/**
 * BVH tree node.
 * Internal nodes have two children.
 * Leaf nodes have a collider pointer.
 */
struct BVHNode {
    AABB bounds;              // Node's bounding box
    int32_t parent = BVH_NULL_NODE;
    int32_t left = BVH_NULL_NODE;
    int32_t right = BVH_NULL_NODE;
    Collider* collider = nullptr;  // Only valid for leaf nodes
    int32_t height = 0;       // Height in tree (leaves = 0)

    bool is_leaf() const { return left == BVH_NULL_NODE; }
};

/**
 * Dynamic BVH tree for broad-phase collision detection.
 */
class BVH {
public:
    BVH() = default;

    // ==================== Core operations ====================

    /**
     * Insert a collider into the tree.
     * Returns the node index for future reference.
     */
    int32_t insert(Collider* collider, const AABB& aabb) {
        int32_t node_index = allocate_node();
        BVHNode& node = nodes_[node_index];

        // Fatten the AABB
        node.bounds = fatten_aabb(aabb);
        node.collider = collider;
        node.height = 0;

        insert_leaf(node_index);
        collider_to_node_[collider] = node_index;

        return node_index;
    }

    /**
     * Remove a collider from the tree.
     */
    void remove(Collider* collider) {
        auto it = collider_to_node_.find(collider);
        if (it == collider_to_node_.end()) return;

        int32_t node_index = it->second;
        collider_to_node_.erase(it);

        remove_leaf(node_index);
        free_node(node_index);
    }

    /**
     * Update the collider's position.
     * Returns true if the tree was modified.
     */
    bool update(Collider* collider, const AABB& new_aabb) {
        auto it = collider_to_node_.find(collider);
        if (it == collider_to_node_.end()) return false;

        int32_t node_index = it->second;
        BVHNode& node = nodes_[node_index];

        // Check if the new AABB is still contained in the fattened AABB
        if (contains(node.bounds, new_aabb)) {
            return false;  // No update needed
        }

        // Need to reinsert
        remove_leaf(node_index);
        node.bounds = fatten_aabb(new_aabb);
        insert_leaf(node_index);

        return true;
    }

    // ==================== Queries ====================

    /**
     * Query all colliders whose AABBs overlap with the given AABB.
     */
    template<typename Callback>
    void query_aabb(const AABB& aabb, Callback&& callback) const {
        if (root_ == BVH_NULL_NODE) return;

        std::vector<int32_t> stack;
        stack.reserve(64);
        stack.push_back(root_);

        while (!stack.empty()) {
            int32_t node_index = stack.back();
            stack.pop_back();

            if (node_index == BVH_NULL_NODE) continue;

            const BVHNode& node = nodes_[node_index];
            if (!node.bounds.intersects(aabb)) continue;

            if (node.is_leaf()) {
                callback(node.collider);
            } else {
                stack.push_back(node.left);
                stack.push_back(node.right);
            }
        }
    }

    /**
     * Query all colliders whose AABBs are hit by the ray.
     * Callback receives (collider, t_min, t_max) for the intersection.
     */
    template<typename Callback>
    void query_ray(const Ray3& ray, Callback&& callback) const {
        if (root_ == BVH_NULL_NODE) return;

        Vec3 inv_dir(1.0 / ray.direction.x, 1.0 / ray.direction.y, 1.0 / ray.direction.z);
        const Vec3& dir = ray.direction;

        std::vector<int32_t> stack;
        stack.reserve(64);
        stack.push_back(root_);

        while (!stack.empty()) {
            int32_t node_index = stack.back();
            stack.pop_back();

            if (node_index == BVH_NULL_NODE) continue;

            const BVHNode& node = nodes_[node_index];

            double t_min, t_max;
            if (!ray_intersects_aabb(ray, inv_dir, dir, node.bounds, t_min, t_max)) continue;

            if (node.is_leaf()) {
                callback(node.collider, t_min, t_max);
            } else {
                stack.push_back(node.left);
                stack.push_back(node.right);
            }
        }
    }

    /**
     * Get all potentially overlapping pairs.
     * Callback receives (attached_a, attached_b) for each pair.
     */
    template<typename Callback>
    void query_all_pairs(Callback&& callback) const {
        if (root_ == BVH_NULL_NODE) return;

        // Collect all leaf nodes
        std::vector<int32_t> leaves;
        leaves.reserve(node_count_);

        std::vector<int32_t> stack;
        stack.reserve(64);
        stack.push_back(root_);

        while (!stack.empty()) {
            int32_t node_index = stack.back();
            stack.pop_back();

            if (node_index == BVH_NULL_NODE) continue;

            const BVHNode& node = nodes_[node_index];
            if (node.is_leaf()) {
                leaves.push_back(node_index);
            } else {
                stack.push_back(node.left);
                stack.push_back(node.right);
            }
        }

        // For each leaf, query the tree for overlaps
        for (int32_t leaf_index : leaves) {
            const BVHNode& leaf = nodes_[leaf_index];
            query_aabb(leaf.bounds, [&](Collider* other) {
                // Avoid duplicate pairs and self-collision
                // Use center position for deterministic ordering
                if (collider_less(leaf.collider, other)) {
                    callback(leaf.collider, other);
                }
            });
        }
    }

private:
    /// Детерминированное сравнение коллайдеров по позиции центра
    static bool collider_less(const Collider* a, const Collider* b) {
        Vec3 ca = a->center();
        Vec3 cb = b->center();
        if (ca.x != cb.x) return ca.x < cb.x;
        if (ca.y != cb.y) return ca.y < cb.y;
        if (ca.z != cb.z) return ca.z < cb.z;
        // Если центры совпадают — fallback на указатель (редкий случай)
        return a < b;
    }

public:

    // ==================== Accessors ====================

    int32_t root() const { return root_; }
    size_t node_count() const { return node_count_; }
    bool empty() const { return root_ == BVH_NULL_NODE; }

    const BVHNode& node(int32_t index) const { return nodes_[index]; }

    /**
     * Compute tree height (for debugging).
     */
    int32_t compute_height() const {
        return compute_height(root_);
    }

    /**
     * Validate tree structure (for debugging).
     */
    bool validate() const {
        return validate_structure(root_);
    }

private:
    std::vector<BVHNode> nodes_;
    std::unordered_map<Collider*, int32_t> collider_to_node_;
    int32_t root_ = BVH_NULL_NODE;
    int32_t free_list_ = BVH_NULL_NODE;
    size_t node_count_ = 0;

    // ==================== Node allocation ====================

    int32_t allocate_node() {
        if (free_list_ != BVH_NULL_NODE) {
            int32_t node_index = free_list_;
            free_list_ = nodes_[node_index].parent;  // parent used as next pointer
            nodes_[node_index] = BVHNode{};
            ++node_count_;
            return node_index;
        }

        int32_t node_index = static_cast<int32_t>(nodes_.size());
        nodes_.push_back(BVHNode{});
        ++node_count_;
        return node_index;
    }

    void free_node(int32_t node_index) {
        nodes_[node_index].parent = free_list_;
        free_list_ = node_index;
        --node_count_;
    }

    // ==================== Tree operations ====================

    void insert_leaf(int32_t leaf_index) {
        if (root_ == BVH_NULL_NODE) {
            root_ = leaf_index;
            nodes_[leaf_index].parent = BVH_NULL_NODE;
            return;
        }

        // Find best sibling using SAH
        AABB leaf_aabb = nodes_[leaf_index].bounds;
        int32_t sibling = find_best_sibling(leaf_aabb);

        // Create new parent
        int32_t old_parent = nodes_[sibling].parent;
        int32_t new_parent = allocate_node();
        nodes_[new_parent].parent = old_parent;
        nodes_[new_parent].bounds = leaf_aabb.merge(nodes_[sibling].bounds);
        nodes_[new_parent].height = nodes_[sibling].height + 1;

        if (old_parent != BVH_NULL_NODE) {
            if (nodes_[old_parent].left == sibling) {
                nodes_[old_parent].left = new_parent;
            } else {
                nodes_[old_parent].right = new_parent;
            }
        } else {
            root_ = new_parent;
        }

        nodes_[new_parent].left = sibling;
        nodes_[new_parent].right = leaf_index;
        nodes_[sibling].parent = new_parent;
        nodes_[leaf_index].parent = new_parent;

        // Walk back up and refit
        refit_ancestors(new_parent);
    }

    void remove_leaf(int32_t leaf_index) {
        if (leaf_index == root_) {
            root_ = BVH_NULL_NODE;
            return;
        }

        int32_t parent = nodes_[leaf_index].parent;
        int32_t grandparent = nodes_[parent].parent;
        int32_t sibling = (nodes_[parent].left == leaf_index)
                              ? nodes_[parent].right
                              : nodes_[parent].left;

        if (grandparent != BVH_NULL_NODE) {
            if (nodes_[grandparent].left == parent) {
                nodes_[grandparent].left = sibling;
            } else {
                nodes_[grandparent].right = sibling;
            }
            nodes_[sibling].parent = grandparent;
            free_node(parent);

            refit_ancestors(grandparent);
        } else {
            root_ = sibling;
            nodes_[sibling].parent = BVH_NULL_NODE;
            free_node(parent);
        }
    }

    int32_t find_best_sibling(const AABB& leaf_aabb) const {
        int32_t best = root_;
        double best_cost = std::numeric_limits<double>::max();

        std::vector<std::pair<int32_t, double>> stack;  // (node, inherited_cost)
        stack.reserve(64);
        stack.push_back({root_, 0.0});

        while (!stack.empty()) {
            auto [node_index, inherited_cost] = stack.back();
            stack.pop_back();

            const BVHNode& node = nodes_[node_index];
            AABB combined = leaf_aabb.merge(node.bounds);
            double direct_cost = combined.surface_area();

            // Cost of choosing this node as sibling
            double cost = direct_cost + inherited_cost;
            if (cost < best_cost) {
                best_cost = cost;
                best = node_index;
            }

            // Inheritance cost for children
            double delta_cost = combined.surface_area() - node.bounds.surface_area();
            double child_inherited = inherited_cost + delta_cost;

            // Lower bound: if even a point leaf can't beat current best, prune
            double lower_bound = leaf_aabb.surface_area() + child_inherited;
            if (lower_bound >= best_cost) continue;

            if (!node.is_leaf()) {
                stack.push_back({node.left, child_inherited});
                stack.push_back({node.right, child_inherited});
            }
        }

        return best;
    }

    void refit_ancestors(int32_t node_index) {
        while (node_index != BVH_NULL_NODE) {
            node_index = balance(node_index);

            BVHNode& node = nodes_[node_index];
            if (!node.is_leaf()) {
                node.bounds = nodes_[node.left].bounds.merge(nodes_[node.right].bounds);
                node.height = 1 + std::max(nodes_[node.left].height, nodes_[node.right].height);
            }

            node_index = node.parent;
        }
    }

    int32_t balance(int32_t index) {
        BVHNode& A = nodes_[index];
        if (A.is_leaf() || A.height < 2) {
            return index;
        }

        int32_t iB = A.left;
        int32_t iC = A.right;
        BVHNode& B = nodes_[iB];
        BVHNode& C = nodes_[iC];

        int32_t balance_factor = C.height - B.height;

        // Rotate C up
        if (balance_factor > 1) {
            int32_t iF = C.left;
            int32_t iG = C.right;
            BVHNode& F = nodes_[iF];
            BVHNode& G = nodes_[iG];

            C.left = index;
            C.parent = A.parent;
            A.parent = iC;

            if (C.parent != BVH_NULL_NODE) {
                if (nodes_[C.parent].left == index) {
                    nodes_[C.parent].left = iC;
                } else {
                    nodes_[C.parent].right = iC;
                }
            } else {
                root_ = iC;
            }

            if (F.height > G.height) {
                C.right = iF;
                A.right = iG;
                G.parent = index;
                A.bounds = B.bounds.merge(G.bounds);
                C.bounds = A.bounds.merge(F.bounds);
                A.height = 1 + std::max(B.height, G.height);
                C.height = 1 + std::max(A.height, F.height);
            } else {
                C.right = iG;
                A.right = iF;
                F.parent = index;
                A.bounds = B.bounds.merge(F.bounds);
                C.bounds = A.bounds.merge(G.bounds);
                A.height = 1 + std::max(B.height, F.height);
                C.height = 1 + std::max(A.height, G.height);
            }

            return iC;
        }

        // Rotate B up
        if (balance_factor < -1) {
            int32_t iD = B.left;
            int32_t iE = B.right;
            BVHNode& D = nodes_[iD];
            BVHNode& E = nodes_[iE];

            B.left = index;
            B.parent = A.parent;
            A.parent = iB;

            if (B.parent != BVH_NULL_NODE) {
                if (nodes_[B.parent].left == index) {
                    nodes_[B.parent].left = iB;
                } else {
                    nodes_[B.parent].right = iB;
                }
            } else {
                root_ = iB;
            }

            if (D.height > E.height) {
                B.right = iD;
                A.left = iE;
                E.parent = index;
                A.bounds = C.bounds.merge(E.bounds);
                B.bounds = A.bounds.merge(D.bounds);
                A.height = 1 + std::max(C.height, E.height);
                B.height = 1 + std::max(A.height, D.height);
            } else {
                B.right = iE;
                A.left = iD;
                D.parent = index;
                A.bounds = C.bounds.merge(D.bounds);
                B.bounds = A.bounds.merge(E.bounds);
                A.height = 1 + std::max(C.height, D.height);
                B.height = 1 + std::max(A.height, E.height);
            }

            return iB;
        }

        return index;
    }

    // ==================== Helpers ====================

    AABB fatten_aabb(const AABB& aabb) const {
        Vec3 margin(BVH_AABB_MARGIN, BVH_AABB_MARGIN, BVH_AABB_MARGIN);
        return AABB(aabb.min_point - margin, aabb.max_point + margin);
    }

    bool contains(const AABB& outer, const AABB& inner) const {
        return outer.min_point.x <= inner.min_point.x &&
               outer.min_point.y <= inner.min_point.y &&
               outer.min_point.z <= inner.min_point.z &&
               outer.max_point.x >= inner.max_point.x &&
               outer.max_point.y >= inner.max_point.y &&
               outer.max_point.z >= inner.max_point.z;
    }

    bool ray_intersects_aabb(const Ray3& ray, const Vec3& inv_dir, const Vec3& dir,
                             const AABB& aabb, double& t_min, double& t_max) const 
    {
        t_min = -std::numeric_limits<double>::infinity();
        t_max = std::numeric_limits<double>::infinity();

        if (std::abs(dir.x) >= 1e-8) { 
            double tx1 = (aabb.min_point.x - ray.origin.x) * inv_dir.x;
            double tx2 = (aabb.max_point.x - ray.origin.x) * inv_dir.x;
            t_min = std::max(t_min, std::min(tx1, tx2));
            t_max = std::min(t_max, std::max(tx1, tx2));
            if (t_max < t_min) return false;
        }
        else {
            // Ray is parallel to x slabs; check if origin is within slabs
            if (ray.origin.x < aabb.min_point.x || ray.origin.x > aabb.max_point.x) {
                return false;
            }
        }

        if (std::abs(dir.y) >= 1e-8) {
            double ty1 = (aabb.min_point.y - ray.origin.y) * inv_dir.y;
            double ty2 = (aabb.max_point.y - ray.origin.y) * inv_dir.y;
            t_min = std::max(t_min, std::min(ty1, ty2));
            t_max = std::min(t_max, std::max(ty1, ty2));
            if (t_max < t_min) return false;
        }
        else {
            // Ray is parallel to y slabs; check if origin is within slabs
            if (ray.origin.y < aabb.min_point.y || ray.origin.y > aabb.max_point.y) {
                return false;
            }
        }

        if (std::abs(dir.z) >= 1e-8) {
            double tz1 = (aabb.min_point.z - ray.origin.z) * inv_dir.z;
            double tz2 = (aabb.max_point.z - ray.origin.z) * inv_dir.z;
            t_min = std::max(t_min, std::min(tz1, tz2));
            t_max = std::min(t_max, std::max(tz1, tz2));
            if (t_max < t_min) return false;
        }
        else {
            // Ray is parallel to z slabs; check if origin is within slabs
            if (ray.origin.z < aabb.min_point.z || ray.origin.z > aabb.max_point.z) {
                return false;
            }
        }

        return t_max >= std::max(t_min, 0.0);
    }

    int32_t compute_height(int32_t node_index) const {
        if (node_index == BVH_NULL_NODE) return 0;
        const BVHNode& node = nodes_[node_index];
        if (node.is_leaf()) return 0;
        return 1 + std::max(compute_height(node.left), compute_height(node.right));
    }

    bool validate_structure(int32_t node_index) const {
        if (node_index == BVH_NULL_NODE) return true;

        const BVHNode& node = nodes_[node_index];

        if (node.is_leaf()) {
            return node.collider != nullptr;
        }

        // Check children exist
        if (node.left == BVH_NULL_NODE || node.right == BVH_NULL_NODE) {
            return false;
        }

        // Check parent pointers
        if (nodes_[node.left].parent != node_index) return false;
        if (nodes_[node.right].parent != node_index) return false;

        // Check bounds contain children
        AABB combined = nodes_[node.left].bounds.merge(nodes_[node.right].bounds);
        if (!contains(node.bounds, combined)) return false;

        return validate_structure(node.left) && validate_structure(node.right);
    }
};

} // namespace collision
} // namespace termin
