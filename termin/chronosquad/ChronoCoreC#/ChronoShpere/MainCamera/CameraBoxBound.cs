using UnityEngine;

public class CameraBoxBound : CameraBounds
{
    public Vector3 Center;
    public Vector3 Size;

    private Vector3 Min;
    private Vector3 Max;

    void Awake()
    {
        Min = Center - Size / 2;
        Max = Center + Size / 2;
    }

    public override bool IsValid(Vector3 pos)
    {
        return pos.x >= Min.x
            && pos.x <= Max.x
            && pos.y >= Min.y
            && pos.y <= Max.y
            && pos.z >= Min.z
            && pos.z <= Max.z;
    }
}
