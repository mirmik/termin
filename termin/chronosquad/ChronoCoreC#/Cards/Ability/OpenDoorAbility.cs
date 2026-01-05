#if UNITY_64
using UnityEngine;
#endif

using System.Collections.Generic;
using System.Linq;
using System;

class OpenDoorAbility : Ability
{
    public OpenDoorAbility() { }

    public override void UseSelfImpl(ITimeline tl, IAbilityListPanel last_used_stamp)
    {
        var _actor = last_used_stamp.Actor();
        AutomaticDoorObject door = _actor as AutomaticDoorObject;
        door.ToogleDoor();
    }
}
