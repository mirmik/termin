using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class DroneController : GuardView
{
    float _air_level = 4.0f;
    float _air_level_target = 4.0f;

    public float AirLevel
    {
        get { return _air_level; }
    }

    public float AirLevelTarget
    {
        get { return _air_level_target; }
        set { _air_level_target = value; }
    }

    void Update()
    {
        _air_level = (_air_level_target - _air_level) * 5.0f * Time.deltaTime + _air_level;
    }
}
