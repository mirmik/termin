#if UNITY_64
using UnityEngine;
#endif

using System;
using System.Collections.Generic;

public abstract class MonoBehaviourAction : GameAction
{
    protected ObjectController _actor;

    protected override void ManualAwake()
    {
        _actor = this.GetComponent<ObjectController>();
        base.ManualAwake();
    }

    protected ObjectOfTimeline GetObject()
    {
        return this.GetComponent<ObjectController>().GetObject();
    }
}
