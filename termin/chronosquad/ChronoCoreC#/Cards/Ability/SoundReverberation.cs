#if UNITY_64
using UnityEngine;
#endif

using System.Collections.Generic;
using System.Linq;
using System;

class SoundReverberationAbility : Ability
{
    float radius_of_sound = 10;
    float shoot_distance = 10;
    RestlessnessParameters noise_parameters;

    public SoundReverberationAbility(
        float radius_of_sound,
        float shoot_distance,
        RestlessnessParameters noise_parameters
    )
    {
        this.radius_of_sound = radius_of_sound;
        this.shoot_distance = shoot_distance;
        this.noise_parameters = noise_parameters;
    }

    // public override void UseOnObject(
    // 	ObjectOfTimeline target_actor,
    // 	ITimeline tl,
    // 	IAbilityListPanel last_used_stamp
    // )
    // {
    // 	var _actor = last_used_stamp.Object();
    // 	if (!CanUse(tl, last_used_stamp))
    // 		return;

    // 	SoundReverberationCommand command = new SoundReverberationCommand(
    // 		target_actor,
    // 		radius_of_sound,
    // 		_actor.LocalStep() + 1
    // 	);
    // 	_actor.AddExternalCommand(command);
    // 	last_used_stamp.SetLastUsed(this.GetType(), _actor.LocalStep());
    // }

    public override void UseOnEnvironmentImpl(
        ReferencedPoint target,
        ITimeline tl,
        IAbilityListPanel last_used_stamp,
        PrivateParameters private_parameters = null
    )
    {
        var _actor = last_used_stamp.Object();
        SoundReverberationCommand command = new SoundReverberationCommand(
            target,
            shoot_distance: shoot_distance,
            radius_of_sound: radius_of_sound,
            stamp: _actor.LocalStep() + 1,
            restlessnessParameters: noise_parameters
        );
        _actor.AddExternalCommand(command);
    }
}
