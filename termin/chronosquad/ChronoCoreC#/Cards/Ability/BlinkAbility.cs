#if UNITY_64
using UnityEngine;
#endif

using System.Collections.Generic;
using System.Linq;
using System;

class BlinkAbility : Ability
{
    // float shoot_distance;
    //IShootDrawer shoot_drawer;
    float BlinkTimeLapse = 0.5f;

    public BlinkAbility() { }

    public BlinkAbility(float BlinkTimeLapse)
    {
        this.BlinkTimeLapse = BlinkTimeLapse;
    }

    public override void UseOnEnvironmentImpl(
        ReferencedPoint target,
        ITimeline tl,
        IAbilityListPanel last_used_stamp,
        PrivateParameters private_parameters = null
    )
    {
        var _actor = last_used_stamp.Actor();
        BlinkCommand command = new BlinkCommand(target, BlinkTimeLapse, _actor.LocalStep() + 1);
        _actor.AddExternalCommand(command);
    }
}
