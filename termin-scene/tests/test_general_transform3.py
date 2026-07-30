import subprocess
import sys
import textwrap


def test_exact_and_logical_transform_apis() -> None:
    subprocess.run(
        [
            sys.executable,
            "-c",
            textwrap.dedent(
                """
                import math

                import termin.bootstrap
                from termin.geombase import Affine3d, GeneralPose3, Pose3, Quat, Vec3
                from termin.scene import TcScene, TransformKind

                def near(a, b, epsilon=1.0e-10):
                    return abs(a - b) <= epsilon

                def vec_near(a, b, epsilon=1.0e-10):
                    return (
                        near(a.x, b.x, epsilon)
                        and near(a.y, b.y, epsilon)
                        and near(a.z, b.z, epsilon)
                    )

                def rotation_z(radians):
                    half = radians * 0.5
                    return Quat(0.0, 0.0, math.sin(half), math.cos(half))

                termin.bootstrap.bootstrap_player()
                scene = TcScene.create("exact-transform-api")
                parent = scene.create_entity("parent")
                child = parent.create_child("child")

                parent.transform.set_local_pose(
                    GeneralPose3(
                        ang=Quat(0.0, 0.0, 0.0, 1.0),
                        lin=Vec3(3.0, 4.0, 5.0),
                        scale=Vec3(2.0, 1.0, 0.5),
                    )
                )
                child.transform.set_local_pose(
                    GeneralPose3(
                        ang=rotation_z(math.pi * 0.5),
                        lin=Vec3(1.0, 2.0, 3.0),
                        scale=Vec3(1.0, 3.0, 1.0),
                    )
                )

                transform = child.transform
                assert transform.kind == TransformKind.Affine
                assert transform.decomposed_global_scale() is None
                assert transform.try_rigid_pose() is None

                expected = (
                    Affine3d.trs(
                        Vec3(3.0, 4.0, 5.0),
                        Quat(0.0, 0.0, 0.0, 1.0),
                        Vec3(2.0, 1.0, 0.5),
                    )
                    @ Affine3d.trs(
                        Vec3(1.0, 2.0, 3.0),
                        rotation_z(math.pi * 0.5),
                        Vec3(1.0, 3.0, 1.0),
                    )
                )
                point = Vec3(2.0, -1.0, 4.0)
                world_point = expected.transform_point(point)
                assert vec_near(transform.transform_point(point), world_point)
                assert vec_near(transform.transform_point_inverse(world_point), point)
                assert vec_near(transform.right(), Vec3(0.0, 1.0, 0.0))

                exact = transform.global_affine()
                assert vec_near(exact.basis.x, expected.basis.x)
                assert vec_near(exact.basis.y, expected.basis.y)
                assert vec_near(exact.basis.z, expected.basis.z)
                assert vec_near(exact.translation, expected.translation)
                lossy_scale = transform.lossy_scale()
                assert vec_near(lossy_scale, transform.basis_axis_lengths())
                lossy_pose = transform.lossy_global_pose()
                assert vec_near(lossy_pose.lin, transform.global_position)
                assert vec_near(lossy_pose.scale, lossy_scale)

                model = child.model_matrix()
                inverse = child.inverse_model_matrix()
                for row in range(4):
                    for col in range(4):
                        value = sum(model[row][k] * inverse[k][col] for k in range(4))
                        assert near(value, 1.0 if row == col else 0.0)

                requested = Vec3(11.0, -7.0, 2.5)
                transform.set_global_position(requested)
                assert vec_near(transform.global_position, requested)
                authored_scale = transform.local_scale()
                requested_pose = Pose3(
                    ang=rotation_z(-0.4),
                    lin=Vec3(-3.0, 8.0, 1.25),
                )
                transform.set_global_pose(requested_pose)
                assert vec_near(transform.global_pose.lin, requested_pose.lin)
                assert vec_near(transform.local_scale(), authored_scale)

                singular = scene.create_entity("singular")
                singular.transform.set_local_scale(Vec3(1.0, 0.0, 1.0))
                try:
                    singular.transform.inverse_world_matrix()
                except RuntimeError:
                    pass
                else:
                    raise AssertionError("singular inverse must fail explicitly")

                scene.destroy()
                termin.bootstrap.shutdown_player()
                """
            ),
        ],
        check=True,
    )
