#if UNITY_64
using UnityEngine;
#endif

using System;

class ExplosionOnDeathAbility : Ability
{
    float radius;
    float loud_radius = 6.0f;
    RestlessnessParameters restlessness;

    public ExplosionOnDeathAbility(float radius, RestlessnessParameters restlessness)
    {
        this.radius = radius;
        this.restlessness = restlessness;
    }

    public override void HookInstall(ObjectOfTimeline actor)
    {
        actor.SetDeadHook(Hook);
    }

    public bool Hook(string who_kill_me, ITimeline tl, IAbilityListPanel last_used_stamp)
    {
        var obj = last_used_stamp.Actor();
        var target = obj.CurrentReferencedPoint();

        tl.AddEvent(
            new LoudSoundEvent(
                step: tl.CurrentStep(),
                center: target,
                radius: loud_radius,
                noise_parameters: restlessness
            )
        );

        tl.AddEvent(
            new LoudSoundVisualEffect(
                start_step: tl.CurrentStep(),
                finish_step: tl.CurrentStep() + (long)(Utility.GAME_GLOBAL_FREQUENCY * 0.5f),
                position: target,
                maxRadius: loud_radius
            )
        );

        tl.AddEvent(
            new ExplosionEffectEvent(
                start_step: tl.CurrentStep() + 1,
                position: target.GlobalPosition(tl)
            )
        );

        tl.AddEvent(
            new AudioEffect(
                start_step: tl.CurrentStep() + 1,
                position: target.GlobalPosition(tl),
                "Explosion",
                1.0f
            )
        );

        tl.AddEvent(new ExplosionEvent(step: tl.CurrentStep() + 1, center: target, radius: radius));

        tl.AddEvent(
            new AnigilationEvent(tl.CurrentStep() + 1, obj.ObjectId().name, reversed: false)
        );

        return false;
    }
}
