using System;
using System.Collections.Generic;

#if UNITY_64
using UnityEngine;
#endif

public class BasicAiCommanderSlot
{
    public BasicAiCommander commander;
    public string name;
    public int priority;

    public BasicAiCommanderSlot(BasicAiCommander commander, string name, int priority)
    {
        this.commander = commander;
        this.name = name;
        this.priority = priority;
    }

    public bool IsEqual(BasicAiCommanderSlot other)
    {
        return commander == other.commander && name == other.name && priority == other.priority;
    }
}
