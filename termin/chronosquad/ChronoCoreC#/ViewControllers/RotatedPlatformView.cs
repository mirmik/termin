using System.Collections;
using System.Collections.Generic;

#if UNITY_64
using UnityEngine;
using Unity.AI.Navigation;
#endif

public interface IGravitySolver
{
    Vector3 GetGravity(Vector3 position);
}

public class RotatedPlatformView : ObjectController, IGravitySolver
{
    public float angular_speed_deg = 16;

    public string FrameName()
    {
        return gameObject.name;
    }

    public override void ManualAwake()
    {
        base.ManualAwake();
        HideInTimeSpiritMode = true;
    }

    public override void InitObjectController(ITimeline tl)
    {
        Platform obj = CreateObject<Platform>(gameObject.name, tl);
        obj.AddComponent(new RingPseudoGravityEvaluator(obj));
        obj.SetPose(transform.position, Quaternion.identity);
        obj.DisableBehaviour();
        obj.SetNextAnimatronic(new InfiniteRotationAnimatronic(angular_speed: angular_speed_deg));
        base.InitVariables(obj);
        obj.PreEvaluate();
    }

    public Vector3 GetGravity(Vector3 position)
    {
        var radius = new Vector2(position.x, position.y).magnitude;
        var angular_speed_rad = angular_speed_deg * Mathf.Deg2Rad;
        var a = angular_speed_rad * angular_speed_rad * radius;
        var direction = new Vector3(position.x, position.y, 0).normalized;
        return a * direction;
    }
}
