using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class LoudWave : MonoBehaviour
{
    float maxRadius = 1.5f;
    float minRadius = 0.5f;

    public void SetMinRadius(float r)
    {
        minRadius = r;
    }

    public void SetMaxRadius(float r)
    {
        maxRadius = r;
    }

    public void SetPhase(float phase)
    {
        var cur = Mathf.Lerp(minRadius, maxRadius, phase);
        transform.localScale = new Vector3(cur, cur, cur);
    }
}
