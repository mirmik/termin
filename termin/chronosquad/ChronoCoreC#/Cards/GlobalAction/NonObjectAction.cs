#if UNITY_64
using UnityEngine;
#endif

using System;
using System.Collections.Generic;

public abstract class NonObjectAction : GameAction
{
    public Activity _activity;

    //public void Init()
    void Awake()
    {
        ManualAwake();
        _activity = new Activity(icon, clicked_action: this, hotkey: KeyCode.K);
    }

    public Activity GetActivity()
    {
        return _activity;
    }
}
