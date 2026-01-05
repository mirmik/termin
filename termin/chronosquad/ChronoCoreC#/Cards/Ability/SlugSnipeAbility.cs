#if UNITY_64
using UnityEngine;
#endif

using System.Collections.Generic;
using System.Linq;
using System;

public class SlugSnipeAbility : Ability
{
    float _shoot_distance = 1.0f;
    string _slug_name;

    public SlugSnipeAbility(float shoot_distance, string slug_name)
    {
        _shoot_distance = shoot_distance;
        _slug_name = slug_name;
    }

    public override bool CanUseAbility(ObjectOfTimeline target_actor)
    {
        var netpoint = target_actor.GetComponent<NetPoint>();
        if (netpoint == null)
            return false;
        return true;
    }

    public override void UseOnObjectImpl(
        ObjectOfTimeline target,
        ITimeline tl,
        IAbilityListPanel last_used_stamp
    )
    {
        var _actor = last_used_stamp.Actor();
        SlugSnipeKillaCommand command = new SlugSnipeKillaCommand(
            target.ObjectId(),
            shoot_distance: _shoot_distance,
            stamp: _actor.LocalStep(),
            slug_name: _slug_name
        );
        _actor.AddExternalCommand(command);
    }

    public override void UseOnEnvironmentImpl(
        ReferencedPoint target,
        ITimeline tl,
        IAbilityListPanel last_used_stamp,
        PrivateParameters private_parameters = null
    )
    {
        var _actor = last_used_stamp.Object();
        SlugSnipeCommand command = new SlugSnipeCommand(
            target,
            shoot_distance: _shoot_distance,
            radius_of_sound: 3.0f,
            stamp: _actor.LocalStep() + 1,
            restlessnessParameters: default,
            slug_name: _slug_name
        );
        _actor.AddExternalCommand(command);
    }
}
