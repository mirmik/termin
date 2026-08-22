#include <termin/physics/mass_properties.hpp>

#include <algorithm>
#include <array>
#include <cmath>
#include <limits>

#include <termin/colliders/box_collider.hpp>
#include <termin/colliders/capsule_collider.hpp>
#include <termin/colliders/convex_hull_collider.hpp>
#include <termin/colliders/sphere_collider.hpp>

namespace termin::physics {
    namespace {

        constexpr double kGeometryEpsilon = 1.0e-12;

        struct SymmetricMatrix3 {
            double value[3][3]{};
        };

        bool finite(double value) {
            return std::isfinite(value);
        }

        Vec3 scaled_local_offset(const colliders::ColliderPrimitive& collider, const Vec3& entity_scale) {
            return entity_scale.cwise_product(collider.transform.lin);
        }

        Vec3 combined_scale(const colliders::ColliderPrimitive& collider, const Vec3& entity_scale) {
            return entity_scale.cwise_product(collider.transform.scale);
        }

        bool valid_inputs(const Vec3& scale, double mass, std::string& diagnostic) {
            if (!finite(mass) || mass <= 0.0) {
                diagnostic = "mass must be finite and positive";
                return false;
            }
            if (!scale.is_finite() || scale.x <= 0.0 || scale.y <= 0.0 || scale.z <= 0.0) {
                diagnostic = "entity and collider scale must be finite and positive";
                return false;
            }
            return true;
        }

        SpatialInertia3
        oriented_properties(double mass, const Vec3& moments, const Vec3& center, const Quat& orientation) {
            SpatialInertia3 result;
            result.mass = mass;
            result.principal_moments = moments;
            result.inertia_frame = Pose3(orientation.normalized(), center);
            return result;
        }

        void rotate_jacobi(SymmetricMatrix3& matrix, double axes[3][3], int p, int q) {
            const double app = matrix.value[p][p];
            const double aqq = matrix.value[q][q];
            const double apq = matrix.value[p][q];
            if (std::abs(apq) <= kGeometryEpsilon) {
                return;
            }

            const double tau = (aqq - app) / (2.0 * apq);
            const double tangent = std::copysign(1.0 / (std::abs(tau) + std::sqrt(1.0 + tau * tau)), tau);
            const double cosine = 1.0 / std::sqrt(1.0 + tangent * tangent);
            const double sine = tangent * cosine;

            for (int axis = 0; axis < 3; ++axis) {
                if (axis == p || axis == q) {
                    continue;
                }
                const double aip = matrix.value[axis][p];
                const double aiq = matrix.value[axis][q];
                matrix.value[axis][p] = matrix.value[p][axis] = cosine * aip - sine * aiq;
                matrix.value[axis][q] = matrix.value[q][axis] = sine * aip + cosine * aiq;
            }

            matrix.value[p][p] = cosine * cosine * app - 2.0 * sine * cosine * apq + sine * sine * aqq;
            matrix.value[q][q] = sine * sine * app + 2.0 * sine * cosine * apq + cosine * cosine * aqq;
            matrix.value[p][q] = matrix.value[q][p] = 0.0;

            for (int row = 0; row < 3; ++row) {
                const double vip = axes[row][p];
                const double viq = axes[row][q];
                axes[row][p] = cosine * vip - sine * viq;
                axes[row][q] = sine * vip + cosine * viq;
            }
        }

        bool principal_axes(SymmetricMatrix3 matrix, Vec3& moments, Quat& orientation, std::string& diagnostic) {
            double axes[3][3] = {
                {1.0, 0.0, 0.0},
                {0.0, 1.0, 0.0},
                {0.0, 0.0, 1.0},
            };

            for (int iteration = 0; iteration < 32; ++iteration) {
                int p = 0;
                int q = 1;
                double largest = std::abs(matrix.value[0][1]);
                for (const auto pair : std::array<std::array<int, 2>, 3>{std::array<int, 2>{0, 1}, {0, 2}, {1, 2}}) {
                    const double candidate = std::abs(matrix.value[pair[0]][pair[1]]);
                    if (candidate > largest) {
                        largest = candidate;
                        p = pair[0];
                        q = pair[1];
                    }
                }
                if (largest <= kGeometryEpsilon) {
                    break;
                }
                rotate_jacobi(matrix, axes, p, q);
            }

            std::array<int, 3> order{0, 1, 2};
            std::sort(
                order.begin(), order.end(), [&](int a, int b) { return matrix.value[a][a] < matrix.value[b][b]; });

            Vec3 vectors[3];
            double values[3];
            for (int output_axis = 0; output_axis < 3; ++output_axis) {
                const int source_axis = order[output_axis];
                values[output_axis] = matrix.value[source_axis][source_axis];
                vectors[output_axis] = Vec3(axes[0][source_axis], axes[1][source_axis], axes[2][source_axis]);

                int dominant = 0;
                if (std::abs(vectors[output_axis].y) > std::abs(vectors[output_axis][dominant])) {
                    dominant = 1;
                }
                if (std::abs(vectors[output_axis].z) > std::abs(vectors[output_axis][dominant])) {
                    dominant = 2;
                }
                if (vectors[output_axis][dominant] < 0.0) {
                    vectors[output_axis] = -vectors[output_axis];
                }
            }

            if (vectors[0].cross(vectors[1]).dot(vectors[2]) < 0.0) {
                vectors[2] = -vectors[2];
            }

            moments = Vec3(values[0], values[1], values[2]);
            if (!moments.is_finite() || moments.x <= kGeometryEpsilon || moments.y <= kGeometryEpsilon ||
                moments.z <= kGeometryEpsilon) {
                diagnostic = "principal moments are non-finite or non-positive";
                return false;
            }

            const double rotation[9] = {
                vectors[0].x,
                vectors[1].x,
                vectors[2].x,
                vectors[0].y,
                vectors[1].y,
                vectors[2].y,
                vectors[0].z,
                vectors[1].z,
                vectors[2].z,
            };
            orientation = Quat::from_rotation_matrix(rotation);
            return orientation.is_finite();
        }

        bool convex_hull_properties(const colliders::ConvexHullCollider& hull,
                                    const Vec3& entity_scale,
                                    double mass,
                                    SpatialInertia3& result,
                                    std::string& diagnostic) {
            if (hull.faces.size() < 4 || hull.vertices.size() < 4) {
                diagnostic = "convex hull must contain a closed non-degenerate surface";
                return false;
            }

            const Vec3 scale = combined_scale(hull, entity_scale);
            const Vec3 offset = scaled_local_offset(hull, entity_scale);
            auto transformed_vertex = [&](int index) {
                const Vec3 vertex = hull.vertices[index].cwise_product(scale);
                return offset + hull.transform.ang.rotate(vertex);
            };

            double volume = 0.0;
            Vec3 first_moment;
            double xx = 0.0;
            double yy = 0.0;
            double zz = 0.0;
            double xy = 0.0;
            double xz = 0.0;
            double yz = 0.0;

            for (const colliders::ConvexFace& face : hull.faces) {
                const Vec3 a = transformed_vertex(face.a);
                const Vec3 b = transformed_vertex(face.b);
                const Vec3 c = transformed_vertex(face.c);
                const double tetra_volume = a.dot(b.cross(c)) / 6.0;
                volume += tetra_volume;
                first_moment += (a + b + c) * (tetra_volume / 4.0);

                auto square_integral = [&](double av, double bv, double cv) {
                    return tetra_volume * (av * av + bv * bv + cv * cv + av * bv + av * cv + bv * cv) / 10.0;
                };
                auto product_integral = [&](double au, double bu, double cu, double av, double bv, double cv) {
                    return tetra_volume *
                           (2.0 * (au * av + bu * bv + cu * cv) + au * bv + av * bu + au * cv + av * cu + bu * cv +
                            bv * cu) /
                           20.0;
                };

                xx += square_integral(a.x, b.x, c.x);
                yy += square_integral(a.y, b.y, c.y);
                zz += square_integral(a.z, b.z, c.z);
                xy += product_integral(a.x, b.x, c.x, a.y, b.y, c.y);
                xz += product_integral(a.x, b.x, c.x, a.z, b.z, c.z);
                yz += product_integral(a.y, b.y, c.y, a.z, b.z, c.z);
            }

            if (!finite(volume) || std::abs(volume) <= kGeometryEpsilon) {
                diagnostic = "convex hull has zero or non-finite enclosed volume";
                return false;
            }
            if (volume < 0.0) {
                volume = -volume;
                first_moment = -first_moment;
                xx = -xx;
                yy = -yy;
                zz = -zz;
                xy = -xy;
                xz = -xz;
                yz = -yz;
            }

            const Vec3 center = first_moment / volume;
            if (!center.is_finite()) {
                diagnostic = "convex hull center of mass is non-finite";
                return false;
            }

            const double density = mass / volume;
            SymmetricMatrix3 inertia;
            inertia.value[0][0] = density * (yy + zz) - mass * (center.y * center.y + center.z * center.z);
            inertia.value[1][1] = density * (xx + zz) - mass * (center.x * center.x + center.z * center.z);
            inertia.value[2][2] = density * (xx + yy) - mass * (center.x * center.x + center.y * center.y);
            inertia.value[0][1] = inertia.value[1][0] = -density * xy + mass * center.x * center.y;
            inertia.value[0][2] = inertia.value[2][0] = -density * xz + mass * center.x * center.z;
            inertia.value[1][2] = inertia.value[2][1] = -density * yz + mass * center.y * center.z;

            Vec3 moments;
            Quat orientation;
            if (!principal_axes(inertia, moments, orientation, diagnostic)) {
                return false;
            }
            result = oriented_properties(mass, moments, center, orientation);
            return true;
        }

    } // namespace

    bool try_compute_mass_properties(const colliders::ColliderPrimitive& collider,
                                     const Vec3& entity_scale,
                                     double mass,
                                     SpatialInertia3& result,
                                     std::string& diagnostic) {
        diagnostic.clear();
        const Vec3 scale = combined_scale(collider, entity_scale);
        if (!valid_inputs(scale, mass, diagnostic)) {
            return false;
        }

        const Vec3 center = scaled_local_offset(collider, entity_scale);
        if (const auto* box = dynamic_cast<const colliders::BoxCollider*>(&collider)) {
            const Vec3 size = (box->half_size * 2.0).cwise_product(scale);
            if (size.x <= kGeometryEpsilon || size.y <= kGeometryEpsilon || size.z <= kGeometryEpsilon) {
                diagnostic = "box dimensions must be positive";
                return false;
            }
            const Vec3 moments(mass * (size.y * size.y + size.z * size.z) / 12.0,
                               mass * (size.x * size.x + size.z * size.z) / 12.0,
                               mass * (size.x * size.x + size.y * size.y) / 12.0);
            result = oriented_properties(mass, moments, center, collider.transform.ang);
            return true;
        }

        if (const auto* sphere = dynamic_cast<const colliders::SphereCollider*>(&collider)) {
            const double radius = sphere->radius * scale.min_component();
            if (!finite(radius) || radius <= kGeometryEpsilon) {
                diagnostic = "sphere radius must be finite and positive";
                return false;
            }
            const double moment = 0.4 * mass * radius * radius;
            result = oriented_properties(mass, Vec3(moment, moment, moment), center, Quat::identity());
            return true;
        }

        if (const auto* capsule = dynamic_cast<const colliders::CapsuleCollider*>(&collider)) {
            const double half_height = capsule->half_height * scale.z;
            const double radius = capsule->radius * std::min(scale.x, scale.y);
            if (!finite(half_height) || half_height < 0.0 || !finite(radius) || radius <= kGeometryEpsilon) {
                diagnostic = "capsule radius must be positive and half-height non-negative";
                return false;
            }

            constexpr double pi = 3.14159265358979323846;
            const double cylinder_volume = 2.0 * pi * radius * radius * half_height;
            const double sphere_volume = 4.0 * pi * radius * radius * radius / 3.0;
            const double total_volume = cylinder_volume + sphere_volume;
            const double cylinder_mass = mass * cylinder_volume / total_volume;
            const double sphere_mass = mass * sphere_volume / total_volume;
            const double axial = radius * radius * (0.5 * cylinder_mass + 0.4 * sphere_mass);
            const double transverse =
                cylinder_mass * (3.0 * radius * radius + 4.0 * half_height * half_height) / 12.0 +
                sphere_mass * (0.4 * radius * radius + 0.75 * half_height * radius + half_height * half_height);
            result = oriented_properties(mass, Vec3(transverse, transverse, axial), center, collider.transform.ang);
            return true;
        }

        if (const auto* hull = dynamic_cast<const colliders::ConvexHullCollider*>(&collider)) {
            return convex_hull_properties(*hull, entity_scale, mass, result, diagnostic);
        }

        diagnostic = "unsupported collider type";
        return false;
    }

} // namespace termin::physics
