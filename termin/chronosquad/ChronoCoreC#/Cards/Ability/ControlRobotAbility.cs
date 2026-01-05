#if UNITY_64
using UnityEngine;
#endif

using System.Collections.Generic;
using System.Linq;
using System;

class ControlRobotAbility : Ability
{
    public ControlRobotAbility() { }

    public override void UseSelfImpl(ITimeline tl, IAbilityListPanel last_used_stamp)
    {
        var controlled = last_used_stamp.Object().DirrectControlled;
        bool control = controlled == default(ObjectId);

        Debug.Log("ControlRobotAbility.UseSelf");
        var command = new ControlRobotCommand(last_used_stamp.Object().LocalStep() + 1, control);
        last_used_stamp.Object().AddExternalCommand(command);
    }
}
