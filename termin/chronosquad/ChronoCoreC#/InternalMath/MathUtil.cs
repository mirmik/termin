#if UNITY_64
using UnityEngine;
#endif

public class MathUtil
{
    public static Vector3 QuaternionDefaultDirection => Vector3.forward;

    static public Vector3 QuaternionToXZDirection(Quaternion quat)
    {
        return quat * QuaternionDefaultDirection;
    }

    static public Quaternion XZDirectionToQuaternion(Vector3 dir)
    {
        dir.y = 0;
        dir = dir.normalized;
        return Quaternion.LookRotation(dir, Vector3.up);
    }

    static public Quaternion UpperiseLookRotation(Vector3 forward, Vector3 up)
    {
        // As look rotation but up vetor is fixed
        Quaternion look = Quaternion.LookRotation(forward, up);
        var look_up = look * Vector3.up;

        // rotate look vector to up vector
        var axis = Vector3.Cross(look_up, up);
        var angle = Vector3.Angle(look_up, up);
        return Quaternion.AngleAxis(angle, axis) * look;
    }
}
