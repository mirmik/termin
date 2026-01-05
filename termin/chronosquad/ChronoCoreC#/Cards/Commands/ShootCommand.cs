using System.Collections;
using System.Collections.Generic;
using System;

#if UNITY_64
using UnityEngine;
#endif

[Serializable]
public class ShootCommand : MovingToObjectCommand
{
    protected float _shoot_distance;

    //Material shootEffectMaterial;
    protected float timeout_before_shoot = 0.5f;
    protected bool ignore_obstacles;
    protected bool can_shoot_from_croach = false;

    // public ShootCommand(
    // 	ObjectId target_actor,
    // 	float shoot_distance,
    // 	Material shootEffectMaterial,
    // 	long stamp,
    // 	bool ignore_obstacles = false,
    // 	bool can_shoot_from_croach = false
    // ) : base(target_actor, WalkingType.Run, stamp)
    // {
    // 	this.shootEffectMaterial = shootEffectMaterial;
    // 	_shoot_distance = shoot_distance;
    // 	this.ignore_obstacles = ignore_obstacles;
    // 	this.can_shoot_from_croach = can_shoot_from_croach;
    // }

    public ShootCommand(
        ObjectId target_actor,
        float shoot_distance,
        long stamp,
        bool ignore_obstacles = false,
        float timeout_before_shoot = 0.5f,
        bool can_shoot_from_croach = false
    ) : base(target_actor, WalkingType.Run, stamp)
    {
        _shoot_distance = shoot_distance;
        this.ignore_obstacles = ignore_obstacles;
        this.timeout_before_shoot = timeout_before_shoot;
        this.can_shoot_from_croach = can_shoot_from_croach;
    }

    void StartShootPhase(ObjectOfTimeline actor, ITimeline timeline)
    {
        var target_actor = TargetObject(timeline);
        var curstep = actor.LocalStep();

        bool croach = (actor as Actor).IsCroachControl() && can_shoot_from_croach;

        ShootAnimatronic punch = new ShootAnimatronic(
            start_step: curstep,
            finish_step: curstep + (long)Utility.GAME_GLOBAL_FREQUENCY * 1,
            pose: actor.CurrentReferencedPose(),
            direction: target_actor.position() - actor.position(),
            croach: croach
        );
        actor.SetNextAnimatronic(punch);
    }

    bool ShootPhase(ObjectOfTimeline actor, ITimeline timeline)
    {
        var target_actor = TargetObject(timeline);
        bool is_shoot_started = actor.CurrentAnimatronic() is ShootAnimatronic;

        if (!is_shoot_started)
        {
            StartShootPhase(actor, timeline);
            return false;
        }
        else
        {
            var start_local_time = actor.CurrentAnimatronic().StartStep;
            var current_local_time = actor.LocalStep();
            if (
                current_local_time - start_local_time
                > Utility.GAME_GLOBAL_FREQUENCY * timeout_before_shoot
            )
            {
                KillTarget(actor, timeline, 0.0f);
                return true;
            }
            else
            {
                return false;
            }
        }
    }

    public virtual void KillTarget(
        ObjectOfTimeline actor,
        ITimeline timeline,
        float absolute_offset
    )
    {
        var target_actor = timeline.GetObject(TargetActorName());
        var global_step = timeline.CurrentStep();
        var curpose = actor.CurrentReferencedPose().GlobalPose(timeline);
        var tgtpose = target_actor.CurrentReferencedPose().GlobalPose(timeline);
        Vector3 gun_position = //actor.GunPosition();
            curpose.position + curpose.rotation * new Vector3(0, 1, 1);
        float blaster_speed = 50.0f;
        float distance = Vector3.Distance(gun_position, target_actor.HeadPositionView());
        float time = distance / blaster_speed;

        timeline.AddEvent(
            new ShootEffectEvent(
                start_step: global_step,
                finish_step: global_step + (long)(time * Utility.GAME_GLOBAL_FREQUENCY),
                position1: gun_position,
                position2: tgtpose.position + tgtpose.rotation * new Vector3(0, 1, 0)
            )
        );

        timeline.AddEvent(
            new DeathEvent(
                step: timeline.CurrentStep()
                    + (long)(
                        absolute_offset * actor.ReverseMultiplier() * Utility.GAME_GLOBAL_FREQUENCY
                    ),
                actor: target_actor,
                who_kill_me: actor.Name(),
                reversed: target_actor.IsReversed()
            )
        );
    }

    bool IsShootPhaseStarted(ObjectOfTimeline actor)
    {
        return actor.CurrentAnimatronic() is ShootAnimatronic;
    }

    bool IsClosestDistance(ObjectOfTimeline actor, ITimeline timeline)
    {
        var target_actor = TargetObject(timeline);
        var target_actor_position = target_actor.GlobalPosition();
        var actor_position = actor.GlobalPosition();
        var distance = Vector3.Distance(target_actor_position, actor_position);
        return distance < _shoot_distance;
    }

    bool InLineOfSight(ObjectOfTimeline actor, ITimeline timeline)
    {
        if (ignore_obstacles)
            return true;

        var target_actor = TargetObject(timeline);

        return GameCore.InLineOfSight(actor, target_actor, _shoot_distance);
    }

    bool IsCanShoot(ObjectOfTimeline actor, ITimeline timeline)
    {
        bool clossest = IsClosestDistance(actor, timeline);
        bool lineofsight = InLineOfSight(actor, timeline);
#if !UNITY_64
        lineofsight = true;
#endif

        return clossest && lineofsight;
    }

    public override bool Execute(ObjectOfTimeline obj, ITimeline timeline)
    {
        var actor = obj;
        bool is_can_shoot = IsCanShoot(actor, timeline);
        bool is_shoot_phase_started = IsShootPhaseStarted(actor);
        if (is_can_shoot || is_shoot_phase_started)
        {
            return ShootPhase(actor, timeline);
        }
        else
        {
            if (actor.IsMovable())
                MovingPhase(actor, timeline);
            return false;
        }
    }

    //BEGIN################################################################
    // This code was generated by FieldScanner

    public override long HashCode()
    {
        long result = 0;
        result = FieldScanner.ModifyHash(result, _shoot_distance);
        result = FieldScanner.ModifyHash(result, timeout_before_shoot);
        result = FieldScanner.ModifyHash(result, ignore_obstacles);
        result = FieldScanner.ModifyHash(result, can_shoot_from_croach);
        result = FieldScanner.ModifyHash(result, target_actor_name);
        result = FieldScanner.ModifyHash(result, can_use_air_strike);
        result = FieldScanner.ModifyHash(result, walktype);
        result = FieldScanner.ModifyHash(result, use_interaction_pose);
        result = FieldScanner.ModifyHash(result, start_step);
        result = FieldScanner.ModifyHash(result, finish_step);
        return result;
    }

    public override bool Equals(object obj)
    {
        if (obj == null)
            return false;
        if (obj.GetType() != GetType())
            return false;
        var other = obj as ShootCommand;
        return _shoot_distance == other._shoot_distance
            && timeout_before_shoot == other.timeout_before_shoot
            && ignore_obstacles == other.ignore_obstacles
            && can_shoot_from_croach == other.can_shoot_from_croach
            && target_actor_name == other.target_actor_name
            && can_use_air_strike == other.can_use_air_strike
            && walktype == other.walktype
            && use_interaction_pose == other.use_interaction_pose
            && start_step == other.start_step
            && finish_step == other.finish_step
            && true;
    }

    public override int GetHashCode()
    {
        return (int)HashCode();
    }
    //END################################################################
}
