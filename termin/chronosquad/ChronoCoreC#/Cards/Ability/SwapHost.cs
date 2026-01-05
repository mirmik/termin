using System.Collections;
using System.Collections.Generic;

#if UNITY_64
using UnityEngine;
#endif

public class SwapHostAbility : Ability
{
    public float jump_radius = 8.0f;
    ParasiteMode parasiteMode = ParasiteMode.Control;

    public SwapHostAbility(ParasiteMode parasiteMode)
    {
        this.parasiteMode = parasiteMode;
        cooldown = 1 * (long)Utility.GAME_GLOBAL_FREQUENCY;
    }

    public override void UseOnObjectImpl(
        ObjectOfTimeline target_actor,
        ITimeline tl,
        IAbilityListPanel last_used_stamp
    )
    {
        var _actor = last_used_stamp.Actor();
        // ConnectToHostCommand command = new ConnectToHostCommand(
        // 	target_actor.ObjectId(),
        // 	shoot_distance: jump_radius,
        // 	stamp: _actor.LocalStep() + 1
        // );

        ParasiteCommand command = new ParasiteCommand(
            target_actor.ObjectId(),
            WalkingType.Walk,
            jump_radius,
            _actor.LocalStep() + 1,
            parasiteMode: parasiteMode
        );

        _actor.AddExternalCommand(command);
    }
}
