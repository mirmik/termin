using System.Collections.Generic;

#if UNITY_64
using UnityEngine;
#endif

public class Platform : PhysicalObject
{
    public Platform()
    {
        DisableBehaviour();
    }

    public override ObjectOfTimeline Copy(ITimeline newtimeline)
    {
        Platform obj = new Platform();
        obj.CopyFrom(this, newtimeline);
        return obj;
    }

    public void StartSinusAnimatronic(Pose start, Pose end, float period)
    {
        _animatronic_states.Add(new SinusMoveAnimatronic(start, end, period));
    }
}
