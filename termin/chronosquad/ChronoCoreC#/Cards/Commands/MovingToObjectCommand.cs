using System.Collections.Generic;
using System;

#if UNITY_64
using UnityEngine;
#endif

public class MovingToObjectCommand : ActorCommand
{
    protected ObjectId target_actor_name;
    protected bool can_use_air_strike = true;
    protected WalkingType walktype = WalkingType.Run;
    protected bool use_interaction_pose = false;

    public MovingToObjectCommand(
        ObjectId target_actor,
        WalkingType walktype,
        long stamp,
        bool use_interaction_pose = false
    ) : base(stamp)
    {
        this.target_actor_name = target_actor;
        this.walktype = walktype;
        this.use_interaction_pose = use_interaction_pose;
    }

    public void PathPlanning(
        Actor actor,
        ReferencedPoint point,
        WalkingType walktype,
        PathFindingTarget start_type = PathFindingTarget.Standart,
        PathFindingTarget target_type = PathFindingTarget.Standart,
        long local_start_step_offset = 0,
        BracedCoordinates braced_coordinates = default,
        bool use_normal_as_up = false
    )
    {
        //Debug.Log("PathPlanning: " + point);

        var _timeline = actor.GetTimeline();
        if (_timeline.IsPast())
            actor.DropToCurrentState();

        var start_position = actor.CurrentReferencedPosition();
        var finish_position = point;

        //Debug.Log("PathPlanning: Start :" + start_position);

        //PlatformAreaBase platform;
        UnityEngine.AI.NavMeshPath rawpath = PathFinding.MakeRawPathForMoving(
            actor,
            _timeline,
            start_position,
            finish_position,
            start_type,
            target_type,
            braced_coordinates //,
        //out platform
        );

        var unitpath = PathFinding.UnitPathForRawPath(
            ref actor.unit_path_storage,
            rawpath,
            _timeline,
            target_type: PathFindingTarget.Standart,
            current_frame: start_position.Frame,
            use_normal_as_up: use_normal_as_up
        );

        // Debug.Log("UNITPATH");
        // foreach (var p in unitpath)
        // {
        // 	Debug.Log("LL " + p.position);
        // }

        if (can_use_air_strike)
        {
            bool is_air_strike = PathFinding.ReduceForAirStrike(unitpath, _timeline, 4.0f);

            if (is_air_strike)
            {
                var apoint = unitpath[unitpath.Count - 1];
                apoint.type = UnitPathPointType.AirStrike;
                unitpath[unitpath.Count - 1] = apoint;
            }
        }

        var list = actor.PlanPath(unitpath, walktype, local_start_step_offset);
        actor.ApplyAnimatronicsList(list);
    }

    void ReInitPath(ObjectOfTimeline actor, ObjectOfTimeline target, long local_start_step_offset)
    {
        if (use_interaction_pose)
        {
            PathPlanning(
                actor as Actor,
                target.InteractionPosition(),
                walktype,
                local_start_step_offset: local_start_step_offset
            );
        }
        else
        {
            PathPlanning(
                actor as Actor,
                target.CurrentReferencedPosition(),
                walktype,
                local_start_step_offset: local_start_step_offset
            );
        }
    }

    public void MovingPhase(ObjectOfTimeline actor, ITimeline timeline)
    {
        var target_actor = timeline.GetObject(target_actor_name);
        Animatronic animatronic = actor.CurrentAnimatronic();

        if (animatronic == null || animatronic is IdleAnimatronic)
        {
            ReInitPath(actor, target_actor, 0);
            return;
        }

        if (animatronic is MovingAnimatronic)
        {
            ReferencedPose mpose;
            if (actor.Animatronics().Last == null)
            {
                mpose = actor.CurrentReferencedPose();
            }
            else
            {
                mpose = actor.Animatronics().Last.Value.FinalPose(timeline);
            }

            float TOLERANCE = 0.5f;
            bool is_same;
            if (target_actor.MovedWith() == actor.MovedWith())
            {
                var target_manim_position = mpose.LocalPosition();
                var target_actor_position = target_actor.CurrentReferencedPosition().LocalPosition;
                is_same = (target_manim_position - target_actor_position).magnitude < TOLERANCE;
            }
            else
            {
                var target_manim_position = mpose.GlobalPosition(timeline);
                var target_actor_position = target_actor
                    .CurrentReferencedPosition()
                    .GlobalPosition(timeline);
                is_same = (target_manim_position - target_actor_position).magnitude < TOLERANCE;
            }

            if (!is_same)
            {
                ReInitPath(actor, target_actor, 1);
                // Смещение в один шаг нужно потому, что при несовпадении позиций
                // начало аниматроника происходит в текущей позиции и
                // актор застрянет в одной точке. Поэтому один шаг
                // выполняется предыдущий аниматроник
                return;
            }
        }
    }

    // public Actor TargetActor(ITimeline timeline)
    // {
    // 	return TargetObject(timeline) as Actor;
    // }
    public ObjectOfTimeline TargetObject(ITimeline timeline)
    {
        return timeline.GetObject(target_actor_name);
    }

    public ObjectId TargetActorName()
    {
        return target_actor_name;
    }

    public bool IsCloseDistance_minimal(ObjectOfTimeline actor, ITimeline timeline)
    {
        var target_actor = TargetObject(timeline);
        var target_actor_position = target_actor.Position();
        var actor_position = actor.Position();
        var distance = Vector3.Distance(target_actor_position, actor_position);
        return distance < 1.0f;
    }

    public override bool ExecuteFirstTime(ObjectOfTimeline actor, ITimeline timeline)
    {
        var target_actor = timeline.GetObject(target_actor_name);
        ReInitPath(actor, target_actor, 0);
        return false;
    }

    public override bool Execute(ObjectOfTimeline actor, ITimeline timeline)
    {
        var current_animatronic = actor.CurrentAnimatronic();
        if (
            IsCloseDistance_minimal(actor, timeline)
            && current_animatronic.CanBeInterruptedForAction()
        )
        {
            return true;
        }
        else
        {
            MovingPhase(actor, timeline);
            return false;
        }
    }

    //BEGIN################################################################
    // This code was generated by FieldScanner

    public override long HashCode()
    {
        long result = 0;
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
        var other = obj as MovingToObjectCommand;
        return target_actor_name == other.target_actor_name
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
