#if UNITY_64
using UnityEngine;
#endif

using System.Collections.Generic;
using System.Linq;
using System;

class ShootAbility : Ability
{
    float shoot_distance;
    bool can_shoot_from_croach;

    public ShootAbility(float shoot_distance, bool can_shoot_from_croach = true)
    {
        this.shoot_distance = shoot_distance;
        this.can_shoot_from_croach = can_shoot_from_croach;
    }

    public override void UseOnObjectImpl(
        ObjectOfTimeline target_actor,
        ITimeline tl,
        IAbilityListPanel last_used_stamp
    )
    {
        var _actor = last_used_stamp.Object();
        ShootCommand command = new ShootCommand(
            target_actor.ObjectId(),
            shoot_distance,
            stamp: _actor.LocalStep() + 1,
            ignore_obstacles: false,
            can_shoot_from_croach: can_shoot_from_croach
        );
        _actor.AddExternalCommand(command);
    }
}

class ShootAbilityOverWalls : Ability
{
    float shoot_distance;
    bool can_shoot_from_croach;

    public ShootAbilityOverWalls(float shoot_distance, bool can_shoot_from_croach)
    {
        this.shoot_distance = shoot_distance;
        this.can_shoot_from_croach = can_shoot_from_croach;
    }

    public override void UseOnObjectImpl(
        ObjectOfTimeline target_actor,
        ITimeline tl,
        IAbilityListPanel last_used_stamp
    )
    {
        var _actor = last_used_stamp.Actor();
        if (!CanUse(tl, last_used_stamp))
            return;

        ShootCommand command = new ShootCommand(
            target_actor.ObjectId(),
            shoot_distance,
            stamp: _actor.LocalStep() + 1,
            ignore_obstacles: true,
            can_shoot_from_croach: can_shoot_from_croach
        );
        _actor.AddExternalCommand(command);
    }
}
