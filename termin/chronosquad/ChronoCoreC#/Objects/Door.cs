using System.Collections.Generic;

#if UNITY_64
using UnityEngine;
#endif

public class DoorObject : PhysicalObject
{
    public DoorObject()
    {
        DisableBehaviour();
    }

    public override ObjectOfTimeline Copy(ITimeline newtimeline)
    {
        DoorObject obj = new DoorObject();
        obj.CopyFrom(this, newtimeline);
        return obj;
    }
}
