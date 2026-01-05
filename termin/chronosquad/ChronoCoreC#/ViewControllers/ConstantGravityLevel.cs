using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using Unity.AI.Navigation;

public class ConstantGravityLevel : MonoBehaviour, IGravitySolver
{
    public float g = 9.81f;

    public Vector3 GetGravity(Vector3 position)
    {
        return new Vector3(0, -g, 0);
    }
}
