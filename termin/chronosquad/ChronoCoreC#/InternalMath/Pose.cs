#if UNITY_64
using UnityEngine;
#endif

using System.Collections.Generic;
using System;

public struct Pose : IEquatable<Pose>, ITrentCompatible
{
    public Vector3 position;
    public Quaternion rotation;

    public static Pose Identity = new Pose(Vector3.zero, Quaternion.identity);

    public Pose(Pose other) : this(other.position, other.rotation) { }

    public Pose(Vector3 position, Quaternion rotation)
    {
        this.position = position;
        this.rotation = rotation;
    }

    public Pose(Vector3 position, Vector3 direction)
    {
        this.position = position;
        this.rotation = Quaternion.LookRotation(direction);
    }

    public Vector3 Up()
    {
        return rotation * Vector3.up;
    }

    public Vector3 Forward()
    {
        return rotation * Vector3.forward;
    }

    public void SetUp(Vector3 up)
    {
        rotation = Quaternion.LookRotation(Forward(), up);
    }

    public Pose Prophet(Screw scr, float delta)
    {
        var lin = scr.lin * delta;
        var ang = scr.ang * delta;
        var rot = Quaternion.Euler(ang.x, ang.y, ang.z);
        return new Pose(position + lin, rotation * rot);
    }

    public bool IsLeftHalf(Vector3 pnt)
    {
        var forw = Forward();
        var lpnt = pnt - position;
        var cross = Vector3.Cross(forw, lpnt);
        return cross.y < 0; // < Кажется это неправильно.
        // Надо проверить предшествующие вычисления
        // В месте использования метода
    }

    public void SetUpBiStep(Vector3 up)
    {
        rotation = Quaternion.LookRotation(Forward(), up);
        var curup = Up();

        // quaternion between two vectors
        Quaternion r = Quaternion.FromToRotation(curup, up);
        rotation = r * rotation;
    }

    public Vector3 Right()
    {
        return rotation * Vector3.right;
    }

    public float AngleToDirectionByXZ(Vector3 direction)
    {
        var forw = rotation * Vector3.forward;
        var right = rotation * Vector3.right;
        var up = rotation * Vector3.up;

        var dot_up_dir = Vector3.Dot(up, direction);
        var direction_without_up = direction - dot_up_dir * up;

        direction_without_up.Normalize();
        return Vector3.Angle(forw, direction_without_up);
    }

    public override string ToString()
    {
        return string.Format("Pose({0}, {1})", position, rotation);
    }

    static bool QuaternionEquals(Quaternion a, Quaternion b)
    {
        if (
            a.x == 0.0f
            && a.y == 0.0f
            && a.z == 0.0f
            && a.w == 0.0f
            && b.x == 0.0f
            && b.y == 0.0f
            && b.z == 0.0f
            && b.w == 0.0f
        )
        {
            return true;
        }

        return a == b;
    }

    // equality
    public bool Equals(Pose other)
    {
        return position == other.position && QuaternionEquals(rotation, other.rotation);
    }

    public override bool Equals(object obj)
    {
        if (obj == null || GetType() != obj.GetType())
        {
            return false;
        }
        return Equals((Pose)obj);
    }

    public override int GetHashCode()
    {
        return position.GetHashCode() ^ rotation.GetHashCode();
    }

    // operators
    static public bool operator ==(Pose a, Pose b)
    {
        return a.Equals(b);
    }

    static public bool operator !=(Pose a, Pose b)
    {
        return !a.Equals(b);
    }

    static public Pose operator *(Pose a, Pose b)
    {
        return new Pose(a.position + a.rotation * b.position, (a.rotation * b.rotation));
    }

    public Pose Inverse()
    {
        var inv_rot = Quaternion.Inverse(rotation);
        var npose = new Pose(inv_rot * -position, inv_rot);
        return npose;
    }

    public void Normalize()
    {
        rotation.Normalize();
    }

    public Pose Divide(Pose other)
    {
        return other.Inverse() * this;
    }

    public object ToTrent()
    {
        Dictionary<string, object> dict = new Dictionary<string, object>();
        dict["position"] = SimpleJsonParser.Vector3ToTrent(position);
        dict["rotation"] = SimpleJsonParser.QuaternionToTrent(rotation);
        return dict;
    }

    public void FromTrent(object obj)
    {
        var dict = (Dictionary<string, object>)obj;
        position = SimpleJsonParser.Vector3FromTrent(dict["position"]);
        var rot = SimpleJsonParser.QuaternionFromTrent(dict["rotation"]);
        rotation = new Quaternion(rot[0], rot[1], rot[2], rot[3]);
    }

    public Vector3 XYDirection()
    {
        return MathUtil.QuaternionToXZDirection(rotation);
    }

    public Vector3 TransformPoint(Vector3 point)
    {
        return position + rotation * point;
    }

    public Vector3 TransformDirection(Vector3 point)
    {
        return rotation * point;
    }

    public Vector3 ProjectToHorizon(Vector3 point)
    {
        var point_in_me_frame = InverseTransformPoint(point);
        point_in_me_frame.y = 0;
        return TransformPoint(point_in_me_frame);
    }

    public Vector3 InverseTransformPoint(Vector3 point)
    {
        var ret = Quaternion.Inverse(rotation) * (point - position);
        return ret;
    }

    public Vector3 InverseTransformDirection(Vector3 point)
    {
        return Quaternion.Inverse(rotation) * point;
    }

    public static Pose Lerp(Pose a, Pose b, float t)
    {
        return new Pose(
            Vector3.Lerp(a.position, b.position, t),
            Quaternion.Slerp(a.rotation, b.rotation, t)
        );
    }

    public static Pose BezierLerp(Pose a, Pose b, Pose c, float t)
    {
        var ab = Lerp(a, b, t);
        var bc = Lerp(b, c, t);
        return Lerp(ab, bc, t);
    }
}
