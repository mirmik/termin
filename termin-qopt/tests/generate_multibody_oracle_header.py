import json
import sys
from pathlib import Path


def _number(value: float) -> str:
    return format(float(value), ".17g")


def _vec2(value: list[float]) -> str:
    return f"{{{_number(value[0])}, {_number(value[1])}}}"


def _vec3(value: list[float]) -> str:
    return (
        f"{{{_number(value[0])}, {_number(value[1])}, {_number(value[2])}}}"
    )


def _quat(value: list[float]) -> str:
    return "{" + ", ".join(_number(component) for component in value) + "}"


def _body3d(body: dict) -> str:
    inertia = body["inertia"]
    inertia_frame = inertia["inertia_frame_local"]
    pose = body["initial_pose"]
    velocity = body["initial_velocity"]
    return "{" + ", ".join(
        [
            "{"
            + ", ".join(
                [
                    _number(inertia["mass"]),
                    _vec3(inertia["principal_moments"]),
                    "{"
                    + ", ".join(
                        [
                            _vec3(inertia_frame["translation"]),
                            _quat(inertia_frame["quaternion_xyzw"]),
                        ]
                    )
                    + "}",
                ]
            )
            + "}",
            "{"
            + ", ".join(
                [
                    _vec3(pose["translation"]),
                    _quat(pose["quaternion_xyzw"]),
                ]
            )
            + "}",
            _vec3(velocity["linear_world"]),
            _vec3(velocity["angular_world"]),
        ]
    ) + "}"


def generate(source: Path, destination: Path) -> None:
    document = json.loads(source.read_text(encoding="utf-8"))
    if document.get("schema_version") != 1:
        raise ValueError("unsupported multibody oracle schema")
    case = next(
        item
        for item in document["cases"]
        if item["kind"] == "double_pendulum_2d"
    )
    if len(case["bodies"]) != 2:
        raise ValueError("double pendulum fixture must contain two bodies")
    free_fall_3d = next(
        item for item in document["cases"] if item["kind"] == "free_fall_3d"
    )
    anchored_3d = next(
        item
        for item in document["cases"]
        if item["kind"] == "anchored_point_3d"
    )
    fixed_revolute_3d = next(
        item
        for item in document["cases"]
        if item["kind"] == "fixed_revolute_3d"
    )
    double_revolute_3d = next(
        item
        for item in document["cases"]
        if item["kind"] == "double_pendulum_revolute_3d"
    )

    sample_steps = ", ".join(str(value) for value in case["sample_steps"])
    bodies = []
    for body in case["bodies"]:
        bodies.append(
            "{" + ", ".join(
                [
                    _number(body["mass"]),
                    _number(body["inertia"]),
                    _vec2(body["center_of_mass_local"]),
                    "{"
                    + ", ".join(_number(value) for value in body["initial_pose"])
                    + "}",
                    "{"
                    + ", ".join(
                        _number(value) for value in body["initial_velocity"]
                    )
                    + "}",
                ]
            ) + "}"
        )

    output = f"""#pragma once

#include <array>
#include <cstddef>

struct OracleVec2 {{
  double x;
  double y;
}};

struct OracleBody2D {{
  double mass;
  double inertia;
  OracleVec2 center_of_mass_local;
  std::array<double, 3> initial_pose;
  std::array<double, 3> initial_velocity;
}};

struct OracleDoublePendulum2D {{
  double time_step;
  std::size_t steps;
  std::size_t sample_steps[{len(case["sample_steps"])}];
  OracleVec2 gravity;
  OracleBody2D bodies[2];
  OracleVec2 world_anchor;
  OracleVec2 body_a_fixed_anchor;
  OracleVec2 body_a_revolute_anchor;
  OracleVec2 body_b_revolute_anchor;
  double constraint_linf;
  double relative_energy_drift;
  double finite_state_limit;
}};

struct OracleVec3 {{
  double x;
  double y;
  double z;
}};

struct OracleQuat {{
  double x;
  double y;
  double z;
  double w;
}};

struct OraclePose3 {{
  OracleVec3 translation;
  OracleQuat quaternion;
}};

struct OracleSpatialInertia3D {{
  double mass;
  OracleVec3 principal_moments;
  OraclePose3 inertia_frame_local;
}};

struct OracleBody3D {{
  OracleSpatialInertia3D inertia;
  OraclePose3 initial_pose;
  OracleVec3 initial_linear_velocity;
  OracleVec3 initial_angular_velocity;
}};

struct OracleFreeFall3D {{
  double time_step;
  std::size_t steps;
  OracleVec3 gravity;
  OracleBody3D body;
  std::array<double, 6> expected_spatial_inertia_diagonal;
  double acceleration_linf;
  double quaternion_norm;
}};

struct OracleAnchoredPoint3D {{
  double time_step;
  std::size_t steps;
  OracleVec3 gravity;
  OracleBody3D body;
  OracleVec3 world_anchor;
  OracleVec3 body_anchor_local;
  std::size_t relative_rotational_dofs;
  double constraint_linf;
  double relative_energy_drift;
  double quaternion_norm;
  double finite_state_limit;
}};

struct OracleFixedRevolute3D {{
  double time_step;
  std::size_t steps;
  OracleVec3 gravity;
  OracleBody3D body;
  OracleVec3 world_anchor;
  OracleVec3 world_axis;
  OracleVec3 body_anchor_local;
  OracleVec3 body_axis_local;
  std::size_t constraint_rows;
  std::size_t relative_rotational_dofs;
  double constraint_linf;
  double reaction_axis_work;
  double quaternion_norm;
}};

struct OracleDoubleRevolute3D {{
  double time_step;
  std::size_t steps;
  OracleVec3 gravity;
  OracleBody3D bodies[2];
  OracleVec3 world_anchor;
  OracleVec3 world_axis;
  OracleVec3 body_fixed_anchor;
  OracleVec3 body_fixed_axis;
  OracleVec3 body_a_anchor;
  OracleVec3 body_a_axis;
  OracleVec3 body_b_anchor;
  OracleVec3 body_b_axis;
  std::size_t constraint_rows;
  std::size_t relative_rotational_dofs;
  double constraint_linf;
  double relative_energy_drift;
  double reaction_axis_work;
  double quaternion_norm;
  double finite_state_limit;
}};

inline constexpr OracleDoublePendulum2D kDoublePendulumOracle{{
  {_number(case["time_step"])},
  {case["steps"]},
  {{{sample_steps}}},
  {_vec2(case["gravity"])},
  {{{bodies[0]}, {bodies[1]}}},
  {_vec2(case["fixed_joint"]["world_anchor"])},
  {_vec2(case["fixed_joint"]["body_anchor_local"])},
  {_vec2(case["revolute_joint"]["body_a_anchor_local"])},
  {_vec2(case["revolute_joint"]["body_b_anchor_local"])},
  {_number(case["bounds"]["constraint_linf"])},
  {_number(case["bounds"]["relative_energy_drift"])},
  {_number(case["bounds"]["finite_state_limit"])},
}};

inline constexpr OracleFreeFall3D kFreeFall3DOracle{{
  {_number(free_fall_3d["time_step"])},
  {free_fall_3d["steps"]},
  {_vec3(free_fall_3d["gravity"])},
  {_body3d(free_fall_3d["body"])},
  {{{", ".join(
      _number(value)
      for value in free_fall_3d[
          "analytic_spatial_inertia_identity_orientation"
      ]["diagonal"]
  )}}},
  {_number(free_fall_3d["bounds"]["acceleration_linf"])},
  {_number(free_fall_3d["bounds"]["quaternion_norm"])},
}};

inline constexpr OracleAnchoredPoint3D kAnchoredPoint3DOracle{{
  {_number(anchored_3d["time_step"])},
  {anchored_3d["steps"]},
  {_vec3(anchored_3d["gravity"])},
  {_body3d(anchored_3d["body"])},
  {_vec3(anchored_3d["fixed_point_joint"]["world_anchor"])},
  {_vec3(anchored_3d["fixed_point_joint"]["body_anchor_local"])},
  {anchored_3d["fixed_point_joint"]["relative_rotational_dofs"]},
  {_number(anchored_3d["bounds"]["constraint_linf"])},
  {_number(anchored_3d["bounds"]["relative_energy_drift"])},
  {_number(anchored_3d["bounds"]["quaternion_norm"])},
  {_number(anchored_3d["bounds"]["finite_state_limit"])},
}};

inline constexpr OracleFixedRevolute3D kFixedRevolute3DOracle{{
  {_number(fixed_revolute_3d["time_step"])},
  {fixed_revolute_3d["steps"]},
  {_vec3(fixed_revolute_3d["gravity"])},
  {_body3d(fixed_revolute_3d["body"])},
  {_vec3(fixed_revolute_3d["fixed_revolute_joint"]["world_anchor"])},
  {_vec3(fixed_revolute_3d["fixed_revolute_joint"]["world_axis"])},
  {_vec3(fixed_revolute_3d["fixed_revolute_joint"]["body_anchor_local"])},
  {_vec3(fixed_revolute_3d["fixed_revolute_joint"]["body_axis_local"])},
  {fixed_revolute_3d["fixed_revolute_joint"]["constraint_rows"]},
  {fixed_revolute_3d["fixed_revolute_joint"]["relative_rotational_dofs"]},
  {_number(fixed_revolute_3d["bounds"]["constraint_linf"])},
  {_number(fixed_revolute_3d["bounds"]["reaction_axis_work"])},
  {_number(fixed_revolute_3d["bounds"]["quaternion_norm"])},
}};

inline constexpr OracleDoubleRevolute3D kDoubleRevolute3DOracle{{
  {_number(double_revolute_3d["time_step"])},
  {double_revolute_3d["steps"]},
  {_vec3(double_revolute_3d["gravity"])},
  {{{_body3d(double_revolute_3d["bodies"][0])},
     {_body3d(double_revolute_3d["bodies"][1])}}},
  {_vec3(double_revolute_3d["fixed_revolute_joint"]["world_anchor"])},
  {_vec3(double_revolute_3d["fixed_revolute_joint"]["world_axis"])},
  {_vec3(double_revolute_3d["fixed_revolute_joint"]["body_anchor_local"])},
  {_vec3(double_revolute_3d["fixed_revolute_joint"]["body_axis_local"])},
  {_vec3(double_revolute_3d["revolute_joint"]["body_a_anchor_local"])},
  {_vec3(double_revolute_3d["revolute_joint"]["body_a_axis_local"])},
  {_vec3(double_revolute_3d["revolute_joint"]["body_b_anchor_local"])},
  {_vec3(double_revolute_3d["revolute_joint"]["body_b_axis_local"])},
  {double_revolute_3d["revolute_joint"]["constraint_rows"]},
  {double_revolute_3d["revolute_joint"]["relative_rotational_dofs"]},
  {_number(double_revolute_3d["bounds"]["constraint_linf"])},
  {_number(double_revolute_3d["bounds"]["relative_energy_drift"])},
  {_number(double_revolute_3d["bounds"]["reaction_axis_work"])},
  {_number(double_revolute_3d["bounds"]["quaternion_norm"])},
  {_number(double_revolute_3d["bounds"]["finite_state_limit"])},
}};
"""
    destination.write_text(output, encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(
            "usage: generate_multibody_oracle_header.py SOURCE DESTINATION"
        )
    generate(Path(sys.argv[1]), Path(sys.argv[2]))


if __name__ == "__main__":
    main()
