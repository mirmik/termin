using System.Collections;
using System.Collections.Generic;

#if UNITY_64
using UnityEngine;
#endif

public class ZeroJumpAbility : Ability
{
    public float jump_radius = 8.0f;
    public float fleet_speed = 5.0f;

    public ZeroJumpAbility(float maxdistance, float speed)
    {
        cooldown = 1 * (long)Utility.GAME_GLOBAL_FREQUENCY;
        jump_radius = maxdistance;
        fleet_speed = speed;
    }

    public override void UseOnEnvironmentImpl(
        ReferencedPoint target_position,
        ITimeline tl,
        IAbilityListPanel last_used_stamp,
        PrivateParameters private_parameters = null
    )
    {
        var _actor = last_used_stamp.Actor();
        ZeroJumpCommand command = new ZeroJumpCommand(
            target: target_position,
            stamp: _actor.LocalStep() + 1,
            jump_radius: jump_radius,
            fleet_speed: fleet_speed
        );
        _actor.AddExternalCommand(command);
    }

    public override void UseOnObjectImpl(
        ObjectOfTimeline target_actor,
        ITimeline tl,
        IAbilityListPanel last_used_stamp
    )
    {
        var _actor = last_used_stamp.Actor();
        JumpKillCommand command = new JumpKillCommand(
            target_actor.ObjectId(),
            shoot_distance: jump_radius,
            stamp: _actor.LocalStep() + 1
        );
        _actor.AddExternalCommand(command);
    }
}
