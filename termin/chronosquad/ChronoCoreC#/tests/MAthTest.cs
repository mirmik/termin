#if !UNITY_64
public static class MathTestClass
{
    public static void AngleTest(Checker checker)
    {
        checker.Equal(Vector3.Angle(new Vector3(1, 0, 0), new Vector3(0, 1, 0)), 90.0f, 0.001f);
    }

    public static void PoseTest(Checker checker)
    {
        Pose pose = Pose.Identity;
        checker.Equal(pose.position, new Vector3(0, 0, 0));
        checker.Equal(Quaternion.identity, Quaternion.identity);
        checker.Equal(pose.rotation, Quaternion.identity);
        checker.Equal(pose.XYDirection(), MathUtil.QuaternionDefaultDirection);
    }

    public static void MulRotationTest(Checker checker)
    {
        Pose a = new Pose(
            position: new Vector3(),
            rotation: MathUtil.XZDirectionToQuaternion(new Vector3(1, 0, 0))
        );
        Pose b = new Pose(
            position: new Vector3(),
            rotation: MathUtil.XZDirectionToQuaternion(new Vector3(0, 0, 1))
        );

        checker.Equal(
            MathUtil.XZDirectionToQuaternion(new Vector3(0, 0, 1)),
            new Quaternion(0, 0, 0, 1)
        );
        checker.Equal(
            MathUtil.XZDirectionToQuaternion(new Vector3(1, 0, 0)),
            new Quaternion(0, 0.70710677f, 0, 0.70710677f)
        );

        checker.Equal(
            MathUtil.QuaternionToXZDirection(new Quaternion(0, 0.70710677f, 0, 0.70710677f)),
            new Vector3(1, 0, 0),
            1e-5f
        );

        checker.Equal(MathUtil.QuaternionToXZDirection(Quaternion.identity), new Vector3(0, 0, 1));
        checker.Equal(Quaternion.identity, MathUtil.XZDirectionToQuaternion(new Vector3(0, 0, 1)));

        checker.Equal(
            MathUtil.QuaternionToXZDirection(
                MathUtil.XZDirectionToQuaternion(new Vector3(0, 0, 1))
            ),
            new Vector3(0, 0, 1),
            1e-5f
        );

        checker.Equal(
            MathUtil.QuaternionToXZDirection(
                MathUtil.XZDirectionToQuaternion(new Vector3(1, 0, 0))
            ),
            new Vector3(1, 0, 0),
            1e-5f
        );

        checker.Equal(
            MathUtil.XZDirectionToQuaternion(MathUtil.QuaternionToXZDirection(Quaternion.identity)),
            Quaternion.identity
        );

        checker.Equal(MathUtil.QuaternionToXZDirection(a.rotation), new Vector3(1, 0, 0), 1e-5f);
        checker.Equal(MathUtil.QuaternionToXZDirection(b.rotation), new Vector3(0, 0, 1), 1e-5f);

        Pose c = a * b;
        checker.Equal(MathUtil.QuaternionToXZDirection(c.rotation), new Vector3(1, 0, 0), 1e-5f);

        Pose d = a * a;
        checker.Equal(MathUtil.QuaternionToXZDirection(d.rotation), new Vector3(0, 0, -1), 1e-5f);
    }

    public static void SlerpTest(Checker checker)
    {
        Quaternion quaternion1 = new Quaternion(0, 1, 0, 0);
        Quaternion quaternion2 = new Quaternion(0, 0, 0, 1);
        Vector3 direction = new Vector3(1, 0, 0);
        Vector3 direction2 = new Vector3(0, 0, 1);

        Quaternion slerp = Quaternion.Slerp(quaternion1, quaternion2, 0.5f);
        checker.Equal(slerp, new Quaternion(0, 0.7071068f, 0, 0.7071068f), 1e-5f);

        checker.Equal(quaternion1 * direction, new Vector3(-1, 0, 0), 1e-5f);
        checker.Equal(quaternion2 * direction, new Vector3(1, 0, 0), 1e-5f);
        checker.Equal(quaternion1 * direction2, new Vector3(0, 0, -1), 1e-5f);
        checker.Equal(quaternion2 * direction2, new Vector3(0, 0, 1), 1e-5f);
    }

    public static void EasingTest(Checker checker)
    {
        Easing.TimeCurve curve = new Easing.TimeCurve(Easing.Linear, 0, 1);
        EaseFrame frame = new EaseFrame(Pose.Identity, Pose.Identity, curve);
        checker.Equal(frame.Evaluate(0), Pose.Identity);
        checker.Equal(frame.Evaluate(1), Pose.Identity);
        checker.Equal(frame.Evaluate(0.5f), Pose.Identity);
    }

    public static void EaseFrameTest(Checker checker)
    {
        Easing.TimeCurve curve = new Easing.TimeCurve(Easing.Linear, 0, 1);
        EaseFrame frame = new EaseFrame(Pose.Identity, Pose.Identity, curve);
        ComplexEaseFrame complex = new ComplexEaseFrame();
        complex.AddFrame(frame);
        checker.Equal(complex.Evaluate(0), Pose.Identity);
        checker.Equal(complex.Evaluate(1), Pose.Identity);
        checker.Equal(complex.Evaluate(0.5f), Pose.Identity);
    }

    public static void EaseFrameTest2(Checker checker)
    {
        Easing.TimeCurve curve = new Easing.TimeCurve(Easing.Linear, 0, 1);
        EaseFrame frame = new EaseFrame(
            Pose.Identity,
            new Pose(new Vector3(0, 10, 10), Quaternion.identity),
            curve
        );
        ComplexEaseFrame complex = new ComplexEaseFrame();
        complex.AddFrame(frame);
        checker.Equal(complex.Evaluate(0), Pose.Identity);
        checker.Equal(complex.Evaluate(1), new Pose(new Vector3(0, 10, 10), Quaternion.identity));
        checker.Equal(complex.Evaluate(0.5f), new Pose(new Vector3(0, 5, 5), Quaternion.identity));
    }

    public static void EaseFrameTest3(Checker checker)
    {
        EaseFrame aframe = new EaseFrame(
            Pose.Identity,
            new Pose(new Vector3(0, 0, 10), Quaternion.identity),
            new Easing.TimeCurve(Easing.Linear, 0, 1)
        );
        EaseFrame bframe = new EaseFrame(
            Pose.Identity,
            new Pose(new Vector3(0, 10, 0), Quaternion.identity),
            new Easing.TimeCurve(Easing.OutQuad, 0, 1)
        );
        ComplexEaseFrame complex = new ComplexEaseFrame();
        complex.AddFrame(aframe);
        complex.AddFrame(bframe);
        checker.Equal(complex.Evaluate(0), Pose.Identity);
        checker.Equal(complex.Evaluate(1), new Pose(new Vector3(0, 10, 10), Quaternion.identity));
        checker.Equal(
            complex.Evaluate(0.5f),
            new Pose(new Vector3(0, 7.5f, 5), Quaternion.identity)
        );
    }

    public static void EaseFrameTest4_Rotation(Checker checker)
    {
        EaseFrame aframe = new EaseFrame(
            Pose.Identity,
            new Pose(Vector3.zero, Quaternion.Euler(0, 0, 90)),
            new Easing.TimeCurve(Easing.Linear, 0, 1)
        );

        ComplexEaseFrame complex = new ComplexEaseFrame();
        complex.AddFrame(aframe);

        checker.Equal(
            Quaternion.Slerp(Quaternion.identity, Quaternion.Euler(0, 0, 90), 0.1f),
            Quaternion.Euler(0, 0, 9)
        );
        checker.Equal(
            Quaternion.Slerp(Quaternion.identity, Quaternion.Euler(0, 0, 90), 0.5f),
            Quaternion.Euler(0, 0, 45)
        );

        checker.Equal(complex.Evaluate(0), Pose.Identity);
        checker.Equal(
            complex.Evaluate(1),
            new Pose(Vector3.zero, Quaternion.Euler(0, 0, 90)),
            0.1f
        );
        checker.Equal(
            complex.Evaluate(0.25f),
            new Pose(Vector3.zero, Quaternion.Euler(0, 0, 22.5f)),
            0.1f
        );
        checker.Equal(
            complex.Evaluate(0.75f),
            new Pose(Vector3.zero, Quaternion.Euler(0, 0, 67.5f)),
            0.1f
        );
        checker.Equal(complex.Evaluate(0.5f), new Pose(Vector3.zero, Quaternion.Euler(0, 0, 45)));
    }
}
#endif
