using System;
using UnityEngine;

public static class HashCodeUtil
{
    public static long HashCode(string str)
    {
        long hash = 5381;
        foreach (char c in str)
        {
            hash = ((hash << 5) + hash) + c;
        }
        return hash;
    }

    public static long HashCode(float f)
    {
        return BitConverter.DoubleToInt64Bits(f);
    }

    public static long HashCode(Vector3 vec)
    {
        long hash = 5381;
        hash = ((hash << 5) + hash) + HashCode(vec.x);
        hash = ((hash << 5) + hash) + HashCode(vec.y);
        hash = ((hash << 5) + hash) + HashCode(vec.z);
        return hash;
    }

    public static long HashCode(Pose pose)
    {
        long hash = 5381;
        hash = ((hash << 5) + hash) + HashCode(pose.position.x);
        hash = ((hash << 5) + hash) + HashCode(pose.position.y);
        hash = ((hash << 5) + hash) + HashCode(pose.position.z);
        hash = ((hash << 5) + hash) + HashCode(pose.rotation.x);
        hash = ((hash << 5) + hash) + HashCode(pose.rotation.y);
        hash = ((hash << 5) + hash) + HashCode(pose.rotation.z);
        hash = ((hash << 5) + hash) + HashCode(pose.rotation.w);
        return hash;
    }
}
