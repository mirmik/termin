using System;
using System.Collections.Generic;

#if UNITY_64
using UnityEngine;
#endif

public class PatrolAiCommander : BasicAiCommander
{
    float AllowedMoveError = Utility.AllowedMovingError;

    PatrolStateStruct state;
    MyList<PatrolPoint> patrolPoints = new MyList<PatrolPoint>();

    public int TargetPointIndex()
    {
        return state.point_no;
    }

    public MyList<PatrolPoint> GetPoints()
    {
        return patrolPoints;
    }

    public override string Info()
    {
        string buf = "PatrolAiCommander: ";
        buf += base.Info();
        buf += "state: " + state.ToString();
        buf += "patrolPoints: " + patrolPoints.Count;
        return buf;
    }

    public override BasicAiCommander Copy()
    {
        PatrolAiCommander buf = new PatrolAiCommander();
        buf.CopyFrom(this);
        return buf;
    }

    public override void CopyFrom(BasicAiCommander other_)
    {
        var other = (PatrolAiCommander)other_;
        base.CopyFrom(other);
        foreach (var point in other.patrolPoints)
        {
            patrolPoints.Add(point);
        }
        state = other.state;
    }

    public MyList<PatrolPoint> PatrolPoints()
    {
        return patrolPoints;
    }

    public void SetPatrolState(PatrolStateStruct state)
    {
        this.state = state;
    }

    public PatrolStateStruct CurrentPatrolState()
    {
        return state;
    }

    public int NextPointIndex()
    {
        return (state.point_no + 1) % patrolPoints.Count;
    }

    public void SetPoints(MyList<PatrolPoint> points)
    {
        foreach (var point in points)
        {
            patrolPoints.Add(point);
        }
    }

    ActorCommand ContinueIdlePhase(ObjectOfTimeline actor, long local_step, ITimeline timeline)
    {
        var current_animatronic = actor.CurrentAnimatronic();
        if (!(current_animatronic is PatrolIdleAnimatronic))
        {
            // Здесь проверка именно на тип PatrolIdleAnimatronic.
            // тип IdleAnimatronic устанавливается в CommandBuffer
            // и объект этого типа может иметь неверные настройки, поэтому
            // мы его перехватываем проверкой на тип наследник
            var animatronic = new PatrolIdleAnimatronic(
                start_step: local_step,
                pose: actor.CurrentReferencedPose(),
                idle_animation: AnimationType.Idle,
                local_camera_pose: new Pose(
                    position: new Vector3(0, actor.CameraLevel, 0),
                    rotation: Quaternion.Euler(0, 0, 0)
                ),
                look_around: new LookAroundSettings(angle: 0.0f, frequency: 1.0f / 4.0f)
            );
            actor.SetNextAnimatronic(animatronic);
        }
        return null;
    }

    PatrolStateStruct NextPointPatrolState(long local_step)
    {
        int nextindex = NextPointIndex();
        var next_point = patrolPoints[nextindex];
        var start_point_state = next_point.StartPhase();
        return new PatrolStateStruct(
            point_no: nextindex,
            phase: start_point_state,
            start_step: local_step
        );
    }

    PatrolStateStruct NextPatrolState(long local_step)
    {
        var curstate = CurrentPatrolState();
        var curpoint = patrolPoints[curstate.point_no];

        bool is_last_point = patrolPoints.Count == 1;
        var next_point_state = curpoint.NextPhase(
            curstate.phase,
            ignore_zero_stand_time: is_last_point
        );
        if (next_point_state.phase == PatrolStatePhase.Finished)
        {
            return NextPointPatrolState(local_step);
        }
        else
        {
            return new PatrolStateStruct(
                point_no: curstate.point_no,
                phase: next_point_state,
                start_step: local_step
            );
        }
    }

    void RestoreMovePatrolPhase(ObjectOfTimeline actor, long local_step)
    {
        var curcommand = actor.CurrentCommand();
        bool has_active_command = curcommand != null;
        if (has_active_command && curcommand is MovingCommand)
        {
            return;
        }

        var current_reference_pose = actor.CurrentReferencedPose();
        var actor_local_position = current_reference_pose.LocalPosition();

        var curstate = CurrentPatrolState();
        var curpoint = patrolPoints[curstate.point_no];
        var point = curpoint.pose;
        var point_local_position = point.LocalPosition();

        var error = Vector3.Distance(actor_local_position, point_local_position);
        if (error < AllowedMoveError)
        {
            InvokeNextPatrolPhaseFromList(local_step);
            return;
        }

        actor.AddInternalCommand(
            new MovingCommand(
                target_position: curpoint.pose.ToPoint(),
                walking_type: WalkingType.Walk,
                stamp: local_step,
                look_around: new LookAroundSettings(angle: 0.0f, frequency: 1.0f / 4.0f)
            )
        );
        return;
    }

    bool RestoreMoveToObjectPatrolPhase(ObjectOfTimeline actor, long local_step)
    {
        bool has_active_command = actor.CurrentCommand() != null;
        if (has_active_command)
            return false;

        var timeline = actor.GetTimeline();

        var current_reference_pose = actor.CurrentReferencedPose();
        var actor_global_position = current_reference_pose.GlobalPosition(timeline);

        var curstate = CurrentPatrolState();
        var curpoint = patrolPoints[curstate.point_no];
        var point = curpoint.pose.ToPoint();
        var point_local_position = point.LocalPosition;

        var target_object = actor.GetTimeline().GetObject(curpoint.interaction_object_name);
        var target_global_position = target_object.InteractionPose().GlobalPosition(timeline);

        var dist = Vector3.Distance(actor_global_position, target_global_position);
        if (dist < AllowedMoveError)
        {
            InvokeNextPatrolPhaseFromList(local_step);
            return true;
        }

        actor.AddInternalCommand(
            new HackCommand(
                target_actor: target_object,
                punch_distance: 0.5f,
                hack_type: HackCommandType.FormatNetwork,
                walktype: WalkingType.Walk,
                avatar_name: null,
                stamp: local_step
            )
        );
        return false;
    }

    bool PoseIsEqual(ReferencedPose a, ReferencedPose b)
    {
        if (a.Frame != b.Frame)
            return false;

        var apose = a.pose;
        var bpose = b.pose;

        bool pe = Vector3.Distance(apose.position, bpose.position) < AllowedMoveError;
        bool re = Quaternion.Angle(apose.rotation, bpose.rotation) < 1.0f;
        return pe && re;
    }

    float PositionDifference(Pose apose, Pose bpose)
    {
        return Vector3.Distance(apose.position, bpose.position);
    }

    float RotationDifference(ReferencedPose apose, ReferencedPose bpose)
    {
        Debug.Assert(apose.Frame == bpose.Frame);
        return Quaternion.Angle(apose.LocalRotation(), bpose.LocalRotation());
    }

    void RotateAfterMovePhase(ObjectOfTimeline actor, long local_step)
    {
        var curpoint_pose = patrolPoints[state.point_no].pose;
        var curent_pose = actor.CurrentReferencedPose();

        if (curpoint_pose.Frame != curent_pose.Frame)
        {
            Debug.Log(
                "Frames are not equal: point:"
                    + curpoint_pose.Frame
                    + " current:"
                    + curent_pose.Frame
            );
            RestoreMovePatrolPhase(actor, local_step);
            return;
        }

        var point_global_pose = curpoint_pose.GlobalPose(actor.GetTimeline());
        var current_global_pose = curent_pose.GlobalPose(actor.GetTimeline());

        var posdiff = PositionDifference(point_global_pose, current_global_pose);
        var rotdiff = RotationDifference(curpoint_pose, curent_pose);

        if (posdiff > AllowedMoveError)
        {
            RestoreMovePatrolPhase(actor, local_step);
            return;
        }

        if (rotdiff < 1.0f)
        {
            InvokeNextPatrolPhaseFromList(local_step);
            return;
        }

        var current_command = actor.CurrentCommand();
        if (current_command != null && current_command is RotateCommand)
        {
            return;
        }

        var rpose = new ReferencedPose(
            new Pose(curent_pose.LocalPose().position, curpoint_pose.LocalPose().rotation),
            curpoint_pose.Frame
        );

        // var point_local_pose = curpoint_pose.LocalPose();
        // Debug.Log("PointLocalPose: " + point_local_pose);
        // var timeline = actor.GetTimeline();
        // Vector3 lpoint =
        // 	point_local_pose.Forward() * 100.0f +
        // 	point_local_pose.position;
        // ReferencedPoint rpoint = new ReferencedPoint(
        // 	lpoint,
        // 	curpoint_pose.Frame
        // );

        actor.AddInternalCommand(
            new RotateCommand(target_pose: rpose, stamp: local_step, anim: AnimationType.Idle)
        );
    }

    void RestoreStandPatrolPhase(ObjectOfTimeline actor, long local_step)
    {
        var current_animatronic = actor.CurrentAnimatronic();
        var curstate = CurrentPatrolState();
        var curpoint = patrolPoints[curstate.point_no];
        var stand_time = curpoint.stand_time;
        if (patrolPoints.Count == 1)
        {
            stand_time = 10000.0f; // Бесконечно стоим на месте
        }

        var stand_steps = (long)(stand_time * Utility.GAME_GLOBAL_FREQUENCY);
        var start_stand_step = curstate.start_step;
        var finish_stand_step = start_stand_step + stand_steps;

        bool pose_is_equal = PoseIsEqual(curpoint.pose, actor.CurrentReferencedPose());
        if (!pose_is_equal)
        {
            ReturnToMovePhase(local_step);
            return;
        }

        if (!(current_animatronic is PatrolIdleAnimatronic))
        {
            // Здесь проверка именно на тип PatrolIdleAnimatronic.
            // тип IdleAnimatronic устанавливается в CommandBuffer
            // и объект этого типа может иметь неверные настройки, поэтому
            // мы его перехватываем проверкой на тип наследник
            var animatronic = new PatrolIdleAnimatronic(
                start_step: local_step,
                pose: curpoint.pose,
                idle_animation: AnimationType.Idle,
                local_camera_pose: new Pose(
                    position: new Vector3(0, actor.CameraLevel, 0),
                    rotation: Quaternion.Euler(0, 0, 0)
                ),
                look_around: new LookAroundSettings(angle: 30.0f, frequency: 1.0f / 4.0f)
            );
            actor.SetNextAnimatronic(animatronic);
        }

        if (local_step > finish_stand_step)
        {
            InvokeNextPatrolPhaseFromList(local_step);
            return;
        }

        return;
    }

    string myname;

    void RestoreCurrentPatrolPhase(ObjectOfTimeline actor, long local_step)
    {
        myname = actor.Name();

        var curstate = CurrentPatrolState();
        PatrolStatePhase phase = curstate.phase.phase;
        switch (phase)
        {
            case PatrolStatePhase.Move:
                RestoreMovePatrolPhase(actor, local_step);
                break;
            case PatrolStatePhase.RotateAfterMove:
                RotateAfterMovePhase(actor, local_step);
                break;
            case PatrolStatePhase.MoveToObject:
                RestoreMoveToObjectPatrolPhase(actor, local_step);
                break;
            case PatrolStatePhase.Stand:
                RestoreStandPatrolPhase(actor, local_step);
                break;
        }
        return;
    }

    void InvokeNextPatrolPhaseFromList(long local_step)
    {
        var current_patrol_state = CurrentPatrolState();
        var next_patrol_state = NextPatrolState(local_step);
        AddCard(
            new ChangePatrolStateEvent(
                step: local_step,
                prevstate: current_patrol_state,
                nextstate: next_patrol_state
            )
        );
    }

    void ReturnToMovePhase(long local_step)
    {
        var curstate = CurrentPatrolState();
        var next_patrol_state = new PatrolStateStruct(
            point_no: curstate.point_no,
            phase: new PatrolPointStateStruct(PatrolStatePhase.Move),
            start_step: local_step
        );
        AddCard(
            new ChangePatrolStateEvent(
                step: local_step,
                prevstate: curstate,
                nextstate: next_patrol_state
            )
        );
    }

    void ContinuePatrolPhase(ObjectOfTimeline actor, long local_step, ITimeline timeline)
    {
        if (patrolPoints == null || patrolPoints.Count == 0)
        {
            ContinueIdlePhase(actor, local_step, timeline);
            return;
        }

        RestoreCurrentPatrolPhase(actor, local_step);
        //bool is_current_patrol_phase_completed =
        // if (is_current_patrol_phase_completed)
        // {
        // 	InvokeNextPatrolPhase(local_step);
        // }
        return;
    }

    public override bool WhatIShouldDo(
        BasicAiController aicontroller,
        long timeline_step,
        long local_step
    )
    {
        var actor = aicontroller.GetObject();
        ContinuePatrolPhase(actor, local_step, actor.GetTimeline());
        return true; // Патрульный модуль всегда берёт управление, если его спрашивают
    }
}
