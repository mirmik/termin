#if UNITY_64
using UnityEngine;
#endif

using System.Collections.Generic;
using System.Linq;
using System;

public class GoldSkullAbility : Ability
{
    float radius = 10;
    string name = "GoldSkull";

    public GoldSkullAbility() { }

    public GoldSkullAbility(float radius, string name)
    {
        this.radius = radius;
        this.name = name;
    }

    public override void UseOnEnvironmentImpl(
        ReferencedPoint target,
        ITimeline tl,
        IAbilityListPanel last_used_stamp,
        PrivateParameters private_parameters = null
    )
    {
        var command = new GoldSkullCommand(
            target_position: target,
            radius: radius,
            stamp: tl.CurrentStep(),
            name: name
        );
        last_used_stamp.Actor().AddExternalCommand(command);
    }
}
