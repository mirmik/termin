#if UNITY_64
using UnityEngine;
#endif

using System;
using System.Collections.Generic;

struct AnimatronicReturn
{
    public Animatronic animatronic;
    public ReferencedPose final_pose;
    public long finish_step;
}

public enum AnimationType
{
    None,
    Walk,
    LowGravityWalk,
    ZeroGravityWalk,
    Idle,
    Punch,
    Death,
    Dragged,
    Shoot,
    Run,
    LowGravityRun,
    CroachWalk,
    ZeroGravityCrawl,
    PulledMove,
    Grabbed,
    Crawl,
    CroachIdle,
    Jump,
    JumpDown,
    JumpDown_TopPhase,
    JumpDown_GroundPhase,
    JumpDown_FleetPhase,
    Climb,
    BracedToCroach,
    IdleToBraced,
    IdleToBraced_FleetPhase,
    IdleToBraced_BracedPhase,
    IdleToBraced_GroundPhase,
    BracedIdle,
    RunToStop,
    Carried,
    BracedHangLeft,
    BracedHangRight,
    CroachToBraced,
    DoorEntrance,
    SkyStrike,
    LeanStandRight,
    LeanStandLeft,
    LeanCroachRight,
    LeanCroachLeft,
    TerminalUsing,

    ClimbingUpWall,
    ClimbingDownWall,

    SkyStrike_TopPhase,
    SkyStrike_FleetPhase,
    SkyStrike_GroundPhase,

    ZeroJumpFleet,
    ZeroJumpStart,
    ZeroJumpGround,
    ZeroJumpToGround,
}

public enum WalkingType
{
    Walk,
    Run,
    Croach,
    BracedHangLeft,
    BracedHangRight,
}

public enum IdleType
{
    Stand,
    Croach
}

public struct SpawnInfo
{
    public string name;
    public long local_step;
    public long timeline_step;

    public SpawnInfo(string name, long local_step, long timeline_step)
    {
        this.name = name;
        this.local_step = local_step;
        this.timeline_step = timeline_step;
    }
}

public class Actor : PhysicalObject
{
    public CroachControlComponent croachControlComponent;

    public SpeedStruct _speed_struct = new SpeedStruct(false);

    public float walk_sync_phase = 0.0f;
    public float run_sync_phase = 0.0f;
    public float croach_sync_phase = 0.0f;
    bool _is_short = false;
    bool _is_armored = false;

    public ObjectId grabbed_actor = default(ObjectId);
    public bool is_drag_grabbed_actor = false;
    ObjectOfTimeline host_actor = null;

    ReferencedPose linked_mark;
    long linked_broken_step;

    public override Dictionary<string, object> ToTrent()
    {
        Dictionary<string, object> dict = base.ToTrent();
        dict["object_type"] = "Actor";
        dict["name"] = _object_id.name;
        dict["is_dead"] = IsDead;
        dict["is_pre_dead"] = IsPreDead;
        dict["is_short"] = _is_short;
        dict["is_armored"] = _is_armored;
        dict["grabbed_actor"] = grabbed_actor;
        dict["host_actor"] = host_actor?.Name();
        dict["parent_guard_name"] = _parent_guard_name?.name;
        dict["primary_child_info"] = _primary_child_info?.name;
        dict["ability_list"] = abilityList.ToTrent();
        return dict;
    }

    public override void FromTrent(Dictionary<string, object> dict)
    {
        base.FromTrent(dict);
        var object_id = (string)dict["name"];
        _object_id = new ObjectId(object_id);
        IsDead = (bool)dict["is_dead"];
        IsPreDead = (bool)dict["is_pre_dead"];
        _is_short = (bool)dict["is_short"];
        _is_armored = (bool)dict["is_armored"];
        _parent_guard_name = new SpawnInfo((string)dict["parent_guard_name"], 0, 0);
        _primary_child_info = new SpawnInfo((string)dict["primary_child_info"], 0, 0);
        abilityList.FromTrent((Dictionary<string, object>)dict["ability_list"]);
    }

    public void SetPromiseMark(ReferencedPose mark, long timeline_step)
    {
        linked_broken_step = _object_time.TimelineToBroken(timeline_step);
        linked_mark = mark;
    }

    public bool HasPromiseMark()
    {
        return linked_mark != default(ReferencedPose);
    }

    public ReferencedPose PromiseMarkPose()
    {
        return linked_mark;
    }

    public long PromiseMarkBrockenStep()
    {
        return linked_broken_step;
    }

    public long PromiseMarkTimelineStep()
    {
        return _object_time.BrokenToTimeline(linked_broken_step);
    }

    public long PromiseMarkTimelineStep2()
    {
        return _object_time.BrokenToTimeline(linked_broken_step);
    }

    public void CancelLinkedSpawning(string copyname)
    {
        //if (_primary_child_info != null && _primary_child_info?.name == copyname)
        //	_primary_child_info = null;
    }

    public void SetPrimaryChild(string copyname)
    {
        var local_step = LocalStep();
        var timeline_step = _timeline.CurrentStep();
        _primary_child_info = new SpawnInfo(
            copyname,
            local_step: local_step,
            timeline_step: timeline_step
        );
    }

    public bool IsBlindCorner(Vector3 point, Vector3 adir, Vector3 bdir)
    {
        Vector3 uadir = adir.normalized;
        Vector3 ubdir = bdir.normalized;

        Vector3 c = (ubdir - uadir).normalized;
        float distanceToNearestCollider = Utility.DistanceToNearestCollider(point, c, 1.0f);
        return distanceToNearestCollider < 1.0f;
    }

    public void SetParentGuardName(string name)
    {
        _parent_guard_name = new SpawnInfo(name, LocalStep(), _timeline.CurrentStep());
    }

    public SpawnInfo? ParentGuardName()
    {
        return _parent_guard_name;
    }

    public bool IsTimePhantom()
    {
        return !IsMeAPrimaryChild();
    }

    Actor ParentGuard()
    {
        return _timeline.GetActor(_parent_guard_name?.name);
    }

    public bool IsMeAPrimaryChild()
    {
        if (_parent_guard_name == null)
            return true;

        var parent = ParentGuard();
        var primary = parent.PrimaryChild();

        return primary == this;
    }

    public void SetIsArmored(bool value)
    {
        _is_armored = value;
    }

    public void ImmediateBlinkTo(ReferencedPose target)
    {
        var local_step = LocalStep();
        var state = new BlinkedMovingState(
            initial_pose: CurrentReferencedPose(),
            target_pose: target,
            start_step: local_step,
            finish_step: local_step + 1,
            is_croaching: IsCroach()
        );
        SetNextAnimatronic(state);
    }

    public void ImmediateBlinkTo(ReferencedPoint tgtpnt)
    {
        var glbpose = GlobalPose();
        var target = ReferencedPose.FromGlobalPose(
            new Pose(tgtpnt.GlobalPosition(_timeline), glbpose.rotation),
            tgtpnt.Frame,
            _timeline
        );
        var local_step = LocalStep();
        var state = new BlinkedMovingState(
            initial_pose: CurrentReferencedPose(),
            target_pose: target,
            start_step: local_step,
            finish_step: local_step + 1,
            is_croaching: IsCroach()
        );
        SetNextAnimatronic(state);
    }

    public void ImmediateBlinkTo(Vector3 position, Vector3 direction)
    {
        var local_step = LocalStep();
        var state = new BlinkedMovingState(
            initial_pose: CurrentReferencedPose(),
            target_pose: new ReferencedPose(new Pose(position, direction), null),
            start_step: local_step,
            finish_step: local_step + 1,
            is_croaching: IsCroach()
        );
        SetNextAnimatronic(state);
    }

    public void SetHostActor(ObjectOfTimeline actor)
    {
        host_actor = actor;
    }

    public Actor HostActor()
    {
        return host_actor as Actor;
    }

    public ObjectId GrabbedActor()
    {
        return grabbed_actor;
    }

    public void CroachSwitch()
    {
        if (IsShort())
            return;

        if (IsCroach())
            FromCroachToStand();
        else
            FromStandToCroach();
    }

    void FromCroachToStand()
    {
        croachControlComponent.IsCroachControl = false;
        var stop_command = new StopCommand(AnimationType.Idle, LocalStep());
        AddExternalCommand(stop_command);
    }

    void FromStandToCroach()
    {
        croachControlComponent.IsCroachControl = true;
        var stop_command = new StopCommand(AnimationType.CroachIdle, LocalStep());
        AddExternalCommand(stop_command);
    }

    public Actor()
    {
        croachControlComponent = GetComponent<CroachControlComponent>();
        //_speed_struct = new SpeedStruct(false);
    }

    public bool IsCroach()
    {
        return croachControlComponent.IsCroach;
    }

    public bool IsBraced()
    {
        return croachControlComponent.IsBraced;
    }

    public bool IsCroachControl()
    {
        return croachControlComponent.IsCroachControl;
    }

    public Actor(string name) : this()
    {
        _object_id = new ObjectId(name);
    }

    public override bool IsDifficultToObserve()
    {
        return _is_short || IsCroach() || IsDead;
    }

    public Animatronic current_state()
    {
        return _animatronic_states.Current();
    }

    float WalkSpeedImpl(AnimationType animtype)
    {
        switch (animtype)
        {
            case AnimationType.Walk:
                return _speed_struct.walk_speed;
            case AnimationType.LowGravityWalk:
                return _speed_struct.low_gravity_walk_speed;
            case AnimationType.ZeroGravityWalk:
                return _speed_struct.zero_gravity_walk_speed;
            case AnimationType.Run:
                return _speed_struct.run_speed;
            case AnimationType.LowGravityRun:
                return _speed_struct.low_gravity_run_speed;
            case AnimationType.CroachWalk:
                return _speed_struct.crouch_speed;
            case AnimationType.BracedHangLeft:
                return 0.5f;
            case AnimationType.BracedHangRight:
                return 0.5f;
        }
        return 1.0f;
    }

    float WalkSpeed(AnimationType animtype)
    {
        float spd = WalkSpeedImpl(animtype);
        if (spd <= 0.0f)
            throw new Exception($"WalkSpeed for {animtype} is {spd}");
        return spd;
    }

    AnimationType ChooseWalkingAnimation()
    {
        var global_pose = GlobalPose();
        var gravity = GameCore.GetGravityInGlobalPoint(global_pose.position, MovedWith());
        var gravity_magnitude = gravity.magnitude;
        if (gravity_magnitude < 1.5f)
            return AnimationType.ZeroGravityWalk;
        else if (gravity_magnitude < 5.0f)
            return AnimationType.LowGravityWalk;
        else
            return AnimationType.Walk;
    }

    private AnimatronicReturn move_to(
        ReferencedPoint target,
        long local_start_step,
        ReferencedPose spos,
        WalkingType walktype,
        MyList<Animatronic> accumulator,
        Vector3 normal,
        LookAroundSettings look_around = default(LookAroundSettings)
    )
    {
        if (target.Frame != spos.Frame)
        {
            Debug.Log(
                $"target.Frame != spos.Frame. target.Frame: {target.Frame} spos.Frame: {spos.Frame}"
            );
        }

        var local_point = target.LocalPosition;
        return move_to(
            local_point,
            local_start_step,
            spos,
            walktype,
            accumulator,
            normal: normal,
            frame: target.Frame,
            look_around: look_around
        );
    }

    AnimationType ChooseRunningAnimation()
    {
        var global_pose = GlobalPose();
        var gravity = GameCore.GetGravityInGlobalPoint(global_pose.position, MovedWith());
        var gravity_magnitude = gravity.magnitude;
        if (gravity_magnitude < 5.0f)
            return AnimationType.LowGravityRun;
        else
            return AnimationType.Run;
    }

    AnimationType ChooseCroachAnimation()
    {
        var global_pose = GlobalPose();
        var gravity = GameCore.GetGravityInGlobalPoint(global_pose.position, MovedWith());
        var gravity_magnitude = gravity.magnitude;
        if (gravity_magnitude < 1.5f)
            return AnimationType.ZeroGravityCrawl;
        else
            return AnimationType.CroachWalk;
    }

    public void SetSpeedStruct(SpeedStruct ss)
    {
        _speed_struct = ss;
    }

    AnimationType WalkTypeToAnimationType(WalkingType walktype, bool is_dragging)
    {
        if (is_dragging)
        {
            return AnimationType.PulledMove;
        }

        switch (walktype)
        {
            case WalkingType.Walk:
                return ChooseWalkingAnimation();
            case WalkingType.Run:
                return ChooseRunningAnimation();
            case WalkingType.Croach:
                return ChooseCroachAnimation();
            case WalkingType.BracedHangLeft:
                return AnimationType.BracedHangLeft;
            case WalkingType.BracedHangRight:
                return AnimationType.BracedHangRight;
        }
        return AnimationType.Walk;
    }

    private AnimatronicReturn move_to(
        Vector3 pos,
        long local_start_step,
        ReferencedPose spos,
        WalkingType walktype,
        MyList<Animatronic> accumulator,
        Vector3 normal,
        ObjectId frame = default(ObjectId),
        LookAroundSettings look_around = default(LookAroundSettings)
    )
    {
        var last_animatronic_state = _animatronic_states.Last;

        bool is_dragging = is_drag_grabbed_actor && IsGrab();
        float dist = Vector3.Distance(spos.LocalPosition(), pos);
        var animtype = WalkTypeToAnimationType(walktype, is_dragging);
        float animdur = AnimationDuration(animtype);
        float speed = WalkSpeed(animtype);
        Debug.Assert(speed > 0.0f);

        long start_step = local_start_step;
        long finish_step = local_start_step + (Int64)(dist / speed * Utility.GAME_GLOBAL_FREQUENCY);

        var final_pose = new ReferencedPose(pos, pos - spos.LocalPosition(), frame);

        var global_final_pose = final_pose.GlobalPose(_timeline);
        global_final_pose.SetUpBiStep(normal);
        final_pose = ReferencedPose.FromGlobalPose(global_final_pose, frame, _timeline);

        if (finish_step == start_step)
            finish_step += 1;

        if (!Steering)
        {
            var state = new MovingAnimatronic(
                animtype,
                start_pose: spos,
                finish_pose: final_pose,
                start_step: start_step,
                finish_step: finish_step,
                animation_duration: animdur,
                is_dragging: is_dragging,
                look_around: look_around
            );

            if (last_animatronic_state != null && last_animatronic_state.Value is MovingAnimatronic)
            {
                MovingAnimatronic last = (MovingAnimatronic)last_animatronic_state.Value;
                var moving_phase = last.MovingPhaseForStep(local_start_step);
                float initial_animation_time = state.InitialWalkingTimeForPhase(moving_phase);
                state.SetInitialAnimationTime(initial_animation_time);
            }
            accumulator.Add(state);
            return new AnimatronicReturn
            {
                animatronic = state,
                final_pose = state.FinalPose(),
                finish_step = finish_step
            };
        }
        else
        {
            var state = new CubicMoveAnimatronic(
                pose_a: spos,
                pose_b: final_pose,
                start_step: start_step,
                finish_step: finish_step
            );
            accumulator.Add(state);
            return new AnimatronicReturn
            {
                animatronic = state,
                final_pose = state.FinalPose(_timeline),
                finish_step = finish_step
            };
        }
    }

    private AnimatronicReturn upstairs_move_to(
        ReferencedPoint pos,
        long local_start_step,
        ReferencedPose spos,
        MyList<Animatronic> accumulator,
        Vector3 normal,
        BracedCoordinates braced_coordinates,
        ObjectId frame = default(ObjectId)
    )
    {
        if (frame == default(ObjectId))
            frame = MovedWith();

        var slocal = spos.LocalPosition();
        var flocal = pos.LocalPosition;
        var up_of_spose = spos.LocalPose().Up();
        var proj_to_normal_slocal = Vector3.Dot(slocal, up_of_spose);
        var proj_to_normal_flocal = Vector3.Dot(flocal, up_of_spose);

        bool isup = proj_to_normal_flocal > proj_to_normal_slocal;

        var last_animatronic_state = _animatronic_states.Last;

        float dist = Vector3.Distance(spos.LocalPosition(), pos.LocalPosition);
        var animtype = isup ? AnimationType.ClimbingUpWall : AnimationType.ClimbingDownWall;
        var rotation = braced_coordinates.Rotation;

        long start_step = local_start_step;
        long finish_step = local_start_step + (Int64)(dist / 1.0f * Utility.GAME_GLOBAL_FREQUENCY);

        if (finish_step == start_step)
            finish_step += 1;
        var state = new BracedMovingAnimatronic(
            pose_a: new ReferencedPose(spos.LocalPosition(), rotation, frame),
            pose_b: new ReferencedPose(pos.LocalPosition, rotation, frame),
            start_step: start_step,
            finish_step: finish_step,
            animation_type: animtype,
            is_loop: true
        );

        accumulator.Add(state);

        return new AnimatronicReturn
        {
            animatronic = state,
            final_pose = new ReferencedPose(pos.LocalPosition, rotation, frame),
            finish_step = finish_step
        };
    }

    public void ImmediateDeath()
    {
        var ev = new DeathEvent(
            step: LocalStep() + 1,
            actor: this,
            who_kill_me: null,
            reversed: IsReversed()
        );

        _timeline.AddEvent(ev);
    }

    public bool IsQuestionState()
    {
        if (_ai_controller == null)
            return false;

        return _ai_controller.IsQuestionState();
    }

    public bool IsShort()
    {
        return _is_short;
    }

    public void SetShort(bool value)
    {
        _is_short = value;
    }

    public void JumpImpl(ReferencedPoint position)
    {
        var target_position = GameCore.FindNearestPointOnNavMesh(
            position.GlobalPosition(_timeline)
        );
        var xyz = position.GlobalPosition(_timeline) - GlobalPosition();
        var xz = new Vector3(xyz.x, 0, xyz.z).normalized;
        var finish_pose = ReferencedPose.FromGlobalPose(
            new Pose(target_position, xz),
            position.Frame,
            _timeline
        );
        var jump_animatronic = new JumpAnimatronic(
            start_step: LocalStep() + 1,
            finish_step: LocalStep() + (long)(1.5f * Utility.GAME_GLOBAL_FREQUENCY),
            start_pose: CurrentReferencedPose(),
            finish_pose: finish_pose
        );
        SetNextAnimatronic(jump_animatronic);
    }

    public void hast(long start_step_by_timeline)
    {
        var start_step = ObjectTime().ToBroken(start_step_by_timeline);
        _object_time.AddModifier(
            new TimeHast(
                start_step: start_step,
                finish_step: start_step + 3 * (int)Utility.GAME_GLOBAL_FREQUENCY
            )
        );
    }

    public void freeze(long start_step_by_timeline)
    {
        var start_step = ObjectTime().ToBroken(start_step_by_timeline);
        _object_time.AddModifier(
            new TimeFreeze(
                start_step: start_step,
                finish_step: start_step + 10 * (int)Utility.GAME_GLOBAL_FREQUENCY
            )
        );
    }

    public void reverse(long start_step_by_timeline)
    {
        var start_step = ObjectTime().ToBroken(start_step_by_timeline);
        _object_time.AddModifier(
            new TimeReverse(
                start_step: start_step,
                finish_step: start_step + 10 * (int)Utility.GAME_GLOBAL_FREQUENCY
            )
        );
    }

    MyList<Animatronic> return_animatronics = new MyList<Animatronic>();

    public MyList<Animatronic> PlanPath(
        UnitPath path,
        WalkingType walktype = WalkingType.Walk,
        long local_start_step_offset = 0,
        LookAroundSettings look_around = default
    )
    {
        long start_step = _timeline.CurrentStep();
        long local_start_step = _object_time.TimelineToLocal(start_step) + local_start_step_offset;
        Vector3 spos = CurrentReferencedPose().LocalPosition();
        Vector3 sdir = MathUtil.QuaternionToXZDirection(CurrentReferencedPose().LocalRotation());
        ReferencedPose pose = CurrentReferencedPose();

        return_animatronics.Clear();
        MyList<Animatronic> animatronics = return_animatronics;

        foreach (var p in path)
        {
            var pos = p.position.GlobalPosition(_timeline);
            var moving_type = p.type;
            var local_p = GlobalPositionToLocal(pos);
            var normal = p.normal;

            AnimatronicReturn ar = new AnimatronicReturn();
            if (
                moving_type == UnitPathPointType.StandartMesh
                || moving_type == UnitPathPointType.Unknown
            )
            {
                ar = move_to(
                    p.position,
                    local_start_step,
                    pose,
                    walktype,
                    animatronics,
                    normal: normal,
                    look_around: look_around
                );
            }
            else if (moving_type == UnitPathPointType.UpstairsMove)
            {
                ar = upstairs_move_to(
                    p.position,
                    local_start_step,
                    pose,
                    accumulator: animatronics,
                    normal: normal,
                    braced_coordinates: p.braced_coordinates
                );
            }
            else if (moving_type == UnitPathPointType.DownToBraced)
            {
                ar = down_to_braced(
                    p.position,
                    _timeline,
                    local_start_step,
                    pose,
                    animatronics,
                    bracedCoordinates: p.braced_coordinates
                );
            }
            else if (moving_type == UnitPathPointType.BracedToUp)
            {
                ar = braced_to_top(
                    p.position,
                    _timeline,
                    local_start_step,
                    pose,
                    animatronics,
                    bracedCoordinates: p.braced_coordinates
                );
            }
            else if (moving_type == UnitPathPointType.BracedClimbingLink)
            {
                ar = top_to_braced(
                    p.position,
                    _timeline,
                    local_start_step,
                    pose,
                    animatronics,
                    bracedCoordinates: p.braced_coordinates
                );
            }
            else if (moving_type == UnitPathPointType.BracedHang)
            {
                ar = braced_hang(
                    p.position,
                    local_start_step,
                    pose,
                    animatronics,
                    bracedCoordinates: p.braced_coordinates
                );
            }
            else if (moving_type == UnitPathPointType.JumpDown)
            {
                ar = jump_down_to(
                    p.position,
                    _timeline,
                    local_start_step,
                    pose,
                    bracedCoordinates: p.braced_coordinates,
                    accumulator: animatronics
                );
            }
            else if (moving_type == UnitPathPointType.AirStrike)
            {
                ar = jump_down_to(
                    p.position,
                    _timeline,
                    local_start_step,
                    pose,
                    bracedCoordinates: p.braced_coordinates,
                    accumulator: animatronics,
                    air_strike_animation: true
                );
            }
            else if (moving_type == UnitPathPointType.DoorLink)
            {
                ar = door_entrance(
                    p.position,
                    _timeline,
                    local_start_step,
                    pose,
                    animatronics,
                    bracedCoordinates: p.braced_coordinates
                );
            }
            else if (moving_type == UnitPathPointType.Lean)
            {
                ar = lean_corner(
                    p.position,
                    _timeline,
                    local_start_step,
                    pose,
                    animatronics,
                    bracedCoordinates: p.braced_coordinates
                );
            }
            else if (moving_type == UnitPathPointType.ToBurrowZone)
            {
                ar = to_burrow_zone(p.position, _timeline, local_start_step, pose, animatronics);
            }
            else if (moving_type == UnitPathPointType.FromBurrowZone)
            {
                ar = from_burrow_zone(p.position, _timeline, local_start_step, pose, animatronics);
            }
            else
            {
                Debug.Log($"Unknown moving type: {moving_type}");
                ar = move_to(
                    p.position,
                    local_start_step,
                    pose,
                    walktype,
                    animatronics,
                    normal: normal
                );
            }

            local_start_step = ar.finish_step;
            pose = ar.final_pose;
        }
        return animatronics;
    }

    private AnimatronicReturn to_burrow_zone(
        ReferencedPoint pos,
        ITimeline timeline,
        long local_start_step,
        ReferencedPose spose,
        MyList<Animatronic> accumulator
    )
    {
        var time1 = 0.1f;
        //var time2 = time1 + 0.3f;

        spose = new ReferencedPose(spose.LocalPosition(), Quaternion.identity, spose.Frame);

        ReferencedPose middle_pose = new ReferencedPose(
            pos.LocalPosition,
            Quaternion.identity,
            pos.Frame
        );

        var state0 = new ToBurrowAnimatronic(
            start_step: local_start_step,
            finish_step: (long)(local_start_step + Utility.GAME_GLOBAL_FREQUENCY * time1),
            pose_a: spose,
            pose_b: middle_pose,
            animation_type: AnimationType.DoorEntrance,
            is_loop: false
        );
        accumulator.Add(state0);

        return new AnimatronicReturn
        {
            animatronic = state0,
            final_pose = middle_pose,
            finish_step = state0.FinishStep
        };
    }

    private AnimatronicReturn from_burrow_zone(
        ReferencedPoint pos,
        ITimeline timeline,
        long local_start_step,
        ReferencedPose spose,
        MyList<Animatronic> accumulator
    )
    {
        var time1 = 0.1f;
        //var time2 = time1 + 0.3f;

        spose = new ReferencedPose(spose.LocalPosition(), Quaternion.identity, spose.Frame);

        ReferencedPose middle_pose = new ReferencedPose(
            pos.LocalPosition,
            Quaternion.identity,
            pos.Frame
        );

        var state0 = new FromBurrowAnimatronic(
            start_step: local_start_step,
            finish_step: (long)(local_start_step + Utility.GAME_GLOBAL_FREQUENCY * time1),
            pose_a: spose,
            pose_b: middle_pose,
            animation_type: AnimationType.DoorEntrance,
            is_loop: false
        );
        accumulator.Add(state0);

        return new AnimatronicReturn
        {
            animatronic = state0,
            final_pose = middle_pose,
            finish_step = state0.FinishStep
        };
    }

    private AnimatronicReturn down_to_braced(
        ReferencedPoint final_point,
        ITimeline timeline,
        long local_start_step,
        ReferencedPose spose,
        MyList<Animatronic> accumulator,
        BracedCoordinates bracedCoordinates
    )
    {
        var time1 = AnimationDuration(AnimationType.IdleToBraced_GroundPhase);
        var time2 = time1 + 1.5f * AnimationDuration(AnimationType.IdleToBraced_FleetPhase);
        var time3 = time2 + AnimationDuration(AnimationType.IdleToBraced_BracedPhase);

        var state0 = new UniversalJumpAnimatronic(
            start_step: local_start_step,
            finish_step: (long)(local_start_step + Utility.GAME_GLOBAL_FREQUENCY * time1),
            start_pose: bracedCoordinates.EPose,
            finish_pose: bracedCoordinates.EPose,
            animation_type: AnimationType.IdleToBraced_GroundPhase,
            overlap_time: 0.5f
        );
        accumulator.Add(state0);

        var state1 = new UniversalJumpAnimatronic(
            start_step: (long)(local_start_step + Utility.GAME_GLOBAL_FREQUENCY * time1),
            finish_step: (long)(local_start_step + Utility.GAME_GLOBAL_FREQUENCY * time2),
            start_pose: bracedCoordinates.EPose,
            finish_pose: bracedCoordinates.CPose,
            animation_type: AnimationType.IdleToBraced_FleetPhase,
            parabolic_jump: false
        );
        accumulator.Add(state1);

        var state2 = new UniversalJumpAnimatronic(
            start_step: (long)(local_start_step + Utility.GAME_GLOBAL_FREQUENCY * time2),
            finish_step: (long)(local_start_step + Utility.GAME_GLOBAL_FREQUENCY * time3),
            start_pose: bracedCoordinates.CPose,
            finish_pose: bracedCoordinates.CPose,
            animation_type: AnimationType.IdleToBraced_BracedPhase
        );
        accumulator.Add(state2);

        return new AnimatronicReturn
        {
            animatronic = state2,
            final_pose = bracedCoordinates.CPose,
            finish_step = state2.FinishStep
        };
    }

    private AnimatronicReturn braced_to_top(
        ReferencedPoint pos,
        ITimeline timeline,
        long local_start_step,
        ReferencedPose spose,
        MyList<Animatronic> accumulator,
        BracedCoordinates bracedCoordinates
    )
    {
        var xzdir = spose.LocalDirection();
        xzdir.y = 0;
        xzdir.Normalize();

        var time1 = AnimationDuration(AnimationType.BracedToCroach);
        var time2 = time1 + 0.3f;

        ReferencedPose middle_pose = new ReferencedPose(
            spose.LocalPosition(),
            bracedCoordinates.Rotation,
            pos.Frame
        );
        ReferencedPose final_pose = new ReferencedPose(
            pos.LocalPosition,
            bracedCoordinates.Rotation,
            pos.Frame
        );

        var state0 = new BracedMovingAnimatronic(
            start_step: local_start_step,
            finish_step: (long)(local_start_step + Utility.GAME_GLOBAL_FREQUENCY * time1),
            pose_a: spose,
            pose_b: middle_pose,
            animation_type: AnimationType.BracedToCroach,
            is_loop: false
        );
        accumulator.Add(state0);

        return new AnimatronicReturn
        {
            animatronic = state0,
            final_pose = final_pose,
            finish_step = state0.FinishStep
        };
    }

    private AnimatronicReturn top_to_braced(
        ReferencedPoint pos,
        ITimeline timeline,
        long local_start_step,
        ReferencedPose spose,
        MyList<Animatronic> accumulator,
        BracedCoordinates bracedCoordinates
    )
    {
        var time1 = AnimationDuration(AnimationType.BracedToCroach);
        var time2 = time1 + 0.3f;

        spose = new ReferencedPose(spose.LocalPosition(), bracedCoordinates.Rotation, spose.Frame);

        ReferencedPose middle_pose = new ReferencedPose(
            bracedCoordinates.TopPosition,
            bracedCoordinates.Rotation,
            pos.Frame
        );
        ReferencedPose final_pose = new ReferencedPose(
            bracedCoordinates.TopPosition,
            bracedCoordinates.Rotation,
            pos.Frame
        );

        var state0 = new BracedMovingAnimatronic(
            start_step: local_start_step,
            finish_step: (long)(local_start_step + Utility.GAME_GLOBAL_FREQUENCY * time1),
            pose_a: spose,
            pose_b: middle_pose,
            animation_type: AnimationType.CroachToBraced,
            is_loop: false
        );
        accumulator.Add(state0);

        return new AnimatronicReturn
        {
            animatronic = state0,
            final_pose = final_pose,
            finish_step = state0.FinishStep
        };
    }

    private AnimatronicReturn lean_corner(
        ReferencedPoint pos,
        ITimeline timeline,
        long local_start_step,
        ReferencedPose spose,
        MyList<Animatronic> accumulator,
        BracedCoordinates bracedCoordinates
    )
    {
        var xzdir = spose.LocalDirection();
        xzdir.y = 0;
        xzdir.Normalize();

        var time1 = AnimationDuration(AnimationType.LeanStandRight);
        var time2 = time1 + 0.3f;

        ReferencedPose final_pose = new ReferencedPose(
            ReferencedPoint
                .FromGlobalPosition(bracedCoordinates.TopPosition, pos.Frame, timeline)
                .LocalPosition,
            bracedCoordinates.Rotation,
            pos.Frame
        );

        Vector3 camera_shift =
            bracedCoordinates.CornerLean == CornerLeanZoneType.Right ? Vector3.left : Vector3.right;
        Quaternion camera_rotation =
            bracedCoordinates.CornerLean == CornerLeanZoneType.Right
                ? Quaternion.Euler(0, -120, 0)
                : Quaternion.Euler(0, 120, 0);

        AnimationType lean_animation =
            bracedCoordinates.CornerLean == CornerLeanZoneType.Right
                ? AnimationType.LeanStandRight
                : AnimationType.LeanStandLeft;

        var state0 = new IdleAnimatronic(
            start_step: local_start_step,
            pose: final_pose,
            idle_animation: lean_animation,
            local_camera_pose: new Pose(
                camera_shift + Utility.HEAD_LEVEL * Vector3.up,
                camera_rotation
            )
        );
        accumulator.Add(state0);

        return new AnimatronicReturn
        {
            animatronic = state0,
            final_pose = final_pose,
            finish_step = state0.FinishStep
        };
    }

    private AnimatronicReturn door_entrance(
        ReferencedPoint pos,
        ITimeline timeline,
        long local_start_step,
        ReferencedPose spose,
        MyList<Animatronic> accumulator,
        BracedCoordinates bracedCoordinates
    )
    {
        var time1 = AnimationDuration(AnimationType.DoorEntrance);
        var time2 = time1 + 0.3f;

        spose = new ReferencedPose(spose.LocalPosition(), bracedCoordinates.Rotation, spose.Frame);

        ReferencedPose middle_pose = new ReferencedPose(
            bracedCoordinates.BotPosition.Value,
            bracedCoordinates.Rotation,
            pos.Frame
        );

        var state0 = new BracedMovingAnimatronic(
            start_step: local_start_step,
            finish_step: (long)(local_start_step + Utility.GAME_GLOBAL_FREQUENCY * time1),
            pose_a: spose,
            pose_b: middle_pose,
            animation_type: AnimationType.DoorEntrance,
            is_loop: false
        );
        accumulator.Add(state0);

        return new AnimatronicReturn
        {
            animatronic = state0,
            final_pose = middle_pose,
            finish_step = state0.FinishStep
        };
    }

    private AnimatronicReturn braced_hang(
        ReferencedPoint pos,
        long local_start_step,
        ReferencedPose spos,
        MyList<Animatronic> accumulator,
        BracedCoordinates bracedCoordinates,
        ObjectId frame = default(ObjectId)
    )
    {
        if (frame == default(ObjectId))
            frame = MovedWith();

        var last_animatronic_state = _animatronic_states.Last;
        //sdir.y = 0;

        var gpose = spos.GlobalPose(_timeline);
        var gstart = gpose.position;
        var gend = pos.GlobalPosition(_timeline);

        float dist = Vector3.Distance(gstart, gend);
        var rotation = bracedCoordinates.Rotation;

        bool is_left_half = gpose.IsLeftHalf(gend);

        var animtype = is_left_half ? AnimationType.BracedHangLeft : AnimationType.BracedHangRight;
        float speed = WalkSpeed(animtype);

        var epose = ReferencedPose.FromGlobalPose(new Pose(gend, rotation), frame, GetTimeline());

        long start_step = local_start_step;
        long finish_step = local_start_step + (Int64)(dist / speed * Utility.GAME_GLOBAL_FREQUENCY);

        if (finish_step == start_step)
            finish_step += 1;
        var state = new BracedMovingAnimatronic(
            pose_a: spos,
            pose_b: epose,
            start_step: start_step,
            finish_step: finish_step,
            animation_type: animtype,
            is_loop: true
        );

        accumulator.Add(state);

        return new AnimatronicReturn
        {
            animatronic = state,
            final_pose = epose,
            finish_step = finish_step
        };
    }

    public float AnimationDuration(AnimationType animation_name)
    {
        return GameCore.AnimationDuration(ProtoId(), animation_name);
    }

    public long AnimationDurationSteps(AnimationType animation_name)
    {
        return (long)(Utility.GAME_GLOBAL_FREQUENCY * AnimationDuration(animation_name));
    }

    private AnimatronicReturn jump_down_to(
        ReferencedPoint pos,
        ITimeline timeline,
        long local_start_step,
        ReferencedPose spose,
        BracedCoordinates bracedCoordinates,
        MyList<Animatronic> accumulator,
        bool air_strike_animation = false
    )
    {
        var apose = bracedCoordinates.APose;
        var bpose = bracedCoordinates.BPose;
        spose = apose;

        var start_global_pos = apose.GlobalPosition(timeline);
        var end_global_pos = bpose.GlobalPosition(timeline);

        var top_phase_animation = air_strike_animation
            ? AnimationType.JumpDown_TopPhase
            : AnimationType.JumpDown_TopPhase;
        var fleet_phase_animation = air_strike_animation
            ? AnimationType.SkyStrike_FleetPhase
            : AnimationType.JumpDown_FleetPhase;
        var ground_phase_animation = air_strike_animation
            ? AnimationType.SkyStrike_GroundPhase
            : AnimationType.JumpDown_GroundPhase;

        var time1 = AnimationDuration(top_phase_animation);
        var time2 = time1 + AnimationDuration(fleet_phase_animation);
        var time3 = time2 + AnimationDuration(ground_phase_animation);

        // ReferencedPose final_pose = ReferencedPose.FromGlobalPose(
        // 	new Pose(end_global_pos, spose.LocalRotation()), pos.Frame, timeline
        // );
        ReferencedPose final_pose = bpose;

        spose = new ReferencedPose(spose.LocalPosition(), spose.LocalRotation(), spose.Frame.name);

        var state0 = new UniversalJumpAnimatronic(
            start_step: local_start_step,
            finish_step: (long)(local_start_step + Utility.GAME_GLOBAL_FREQUENCY * time1),
            start_pose: spose,
            finish_pose: spose,
            animation_type: top_phase_animation,
            overlap_time: 0.25f
        );
        accumulator.Add(state0);

        var state1 = new UniversalJumpAnimatronic(
            start_step: (long)(local_start_step + Utility.GAME_GLOBAL_FREQUENCY * time1),
            finish_step: (long)(local_start_step + Utility.GAME_GLOBAL_FREQUENCY * time2),
            start_pose: spose,
            finish_pose: final_pose,
            animation_type: fleet_phase_animation,
            parabolic_jump: true,
            overlap_time: 0.25f
        );
        accumulator.Add(state1);

        var state2 = new UniversalJumpAnimatronic(
            start_step: (long)(local_start_step + Utility.GAME_GLOBAL_FREQUENCY * time2),
            finish_step: (long)(local_start_step + Utility.GAME_GLOBAL_FREQUENCY * time3),
            start_pose: final_pose,
            finish_pose: final_pose,
            animation_type: ground_phase_animation,
            overlap_time: 0.25f
        );
        accumulator.Add(state2);

        return new AnimatronicReturn
        {
            animatronic = state2,
            final_pose = final_pose,
            finish_step = state2.FinishStep
        };
    }

    public void SetCroachControl(bool value)
    {
        croachControlComponent.IsCroachControl = value;
    }

    public bool IsGrab()
    {
        return grabbed_actor != default(ObjectId);
    }

    // public void Grab(ObjectOfTimeline obj, bool is_dragging)
    // {
    // 	Actor actor = (Actor)obj;
    // 	AddExternalCommand(new GrabCommand(
    // 		actor.ObjectId(),
    // 		LocalStep(),
    // 		is_dragging: is_dragging));
    // }

    // public void UnGrab(ReferencedPoint pos)
    // {
    // 	AddExternalCommand(new UnGrabCommand(pos, LocalStep()));
    // }

    public void GrabImpl(ObjectOfTimeline target_actor, bool is_dragging)
    {
        SetGrabbedAddCard(target_actor.ObjectId(), is_dragged: is_dragging);
    }

    public void UnGrabImpl()
    {
        SetGrabbedAddCard(default(ObjectId), false);
    }

    public void GrabbedImpl(ObjectOfTimeline actor, bool is_dragging)
    {
        if (is_dragging == false)
        {
            SetMovedWithAddCard(actor.ObjectId());

            var stun_event = new StunEvent(
                step: LocalStep() + 1,
                length: (long)(6.0f * Utility.GAME_GLOBAL_FREQUENCY)
            );
            AddCard(stun_event);
        }
        else
        {
            // AnimationType animationType = is_dragging ?
            // 	AnimationType.Dragged :
            // 	AnimationType.Carried;

            // var anim = new DeathAnimatronic(
            // 	LocalStep(),
            // 	long.MaxValue,
            // 	new ReferencedPose(Pose.Identity, actor.Name()),
            // 	animation_type: animationType
            // );
            // SetNextAnimatronic(anim);
        }
    }

    public long LastAnimatronicStepInStartList()
    {
        return _animatronic_states.LastStepInStartList();
    }

    public void UnGrabbedImpl(bool is_dragging, ReferencedPose host_pose)
    {
        if (is_dragging)
        {
            var anim = new IdleAnimatronic(
                LocalStep(),
                CurrentReferencedPose(),
                AnimationType.Dragged,
                new Pose(new Vector3(0, CameraLevel, 0), Quaternion.identity)
            );
            SetNextAnimatronic(anim);
        }
        else
        {
            Animatronic anim;

            if (IsDead || IsPreDead)
            {
                anim = new DeathAnimatronic(
                    LocalStep(),
                    long.MaxValue,
                    host_pose,
                    AnimationType.Dragged
                );
            }
            else
            {
                anim = new IdleAnimatronic(
                    LocalStep(),
                    host_pose,
                    AnimationType.Idle,
                    local_camera_pose: new Pose(new Vector3(0, CameraLevel, 0), Quaternion.identity)
                );
            }
            SetNextAnimatronic(anim);
        }
    }

    public void SetMovedWithAddCard(ObjectId obj)
    {
        // var card = new SetMovedWithCard(
        // 	LocalStep(),
        // 	prev: MovedWith(),
        // 	next: obj);
        // AddCard(card);

        // if (obj != ObjectId())

        var parasite_anim = new ParasiteParasiteAnimatronic(LocalStep(), long.MaxValue, obj);
        SetNextAnimatronic(parasite_anim);
    }

    public void SetGrabbedAddCard(ObjectId obj, bool is_dragged)
    {
        var card = new SetGrabbedCard(
            LocalStep(),
            prev: grabbed_actor,
            next: obj,
            is_dragging_prev: is_drag_grabbed_actor,
            is_dragging_next: is_dragged
        );
        AddCard(card);
    }

    public void Stop(ITimeline timeline)
    {
        var animation_type = IsCroach() ? AnimationType.CroachIdle : AnimationType.Idle;

        var stop_command = new StopCommand(animation_type, LocalStep());
        AddExternalCommand(stop_command);
    }

    public WalkingType CurrentCalmWalkingType()
    {
        if (IsCroachControl())
            return WalkingType.Croach;
        return WalkingType.Walk;
    }

    public void DropAnimatronicAfterCurrent()
    {
        while (_animatronic_states.NextNode() != null)
        {
            _animatronic_states.RemoveLast();
        }
    }

    public void MoveToCommand(Vector3 point, bool is_run = false)
    {
        WalkingType walktype = is_run ? WalkingType.Run : CurrentCalmWalkingType();
        MoveToCommand(point, walktype);
    }

    public void MoveToCommand(Vector3 point, WalkingType walktype)
    {
        point = GameCore.NavSamplePosition(point);
        var cmd = new MovingCommand(
            target_position: new ReferencedPoint(point, null),
            walking_type: walktype,
            LocalStep() + 1
        );
        AddExternalCommand(cmd);
    }

    public void SightToCommand(ReferencedPoint target_position, long stamp)
    {
        var command = new SightToCommand(
            target_position: target_position,
            anim: AnimationType.Idle,
            stamp: stamp
        );
        AddExternalCommand(command);
    }

    public void MoveToCommand(ReferencedPoint rpoint, WalkingType walktype)
    {
        var cmd = new MovingCommand(
            target_position: rpoint,
            walking_type: walktype,
            stamp: LocalStep()
        );
        AddExternalCommand(cmd);
    }

    public ChronoSphere Chronosphere()
    {
        return _timeline.GetChronosphere();
    }

    public void ControlDecorator(Action<Actor> action)
    {
        bool is_past = _timeline.IsPast();
        var actor = this;

        if (is_past)
        {
            if (Chronosphere().IsDropTimeOnEdit())
            {
                (_timeline as Timeline).DropTimelineToCurrentState();
            }
            else
            {
                var ntl = (_timeline as Timeline).Copy();
                ntl.SetCurrentTimeline();
                ntl.DropTimelineToCurrentState();
                actor = ntl.GetActor(_object_id);
            }
        }

        action(actor);
    }

    public void set_idle_animation()
    {
        current_animation_type = AnimationType.Idle;
    }

    public MovingAnimatronic MovingState()
    {
        return CurrentAnimatronic() as MovingAnimatronic;
    }

    public override void PromoteExtended(long local_step) { }

    public bool IsMoving(long local_step)
    {
        if (!(_animatronic_states.Current() is MovingAnimatronic))
            return false;

        var manim = (MovingAnimatronic)_animatronic_states.Current();
        if (manim.FinishStep < local_step)
            return false;

        return true;
    }

    public override void ExecuteExtended(long timeline_step, long local_step) { }

    public void NormilizeCoeffs(MyList<float> coeffs)
    {
        float sum = 0;
        foreach (var c in coeffs)
            sum += c;
        for (int i = 0; i < coeffs.Count; i++)
            coeffs[i] /= sum;
    }

    public override void CopyFrom(ObjectOfTimeline other_, ITimeline newtimeline)
    {
        var other = other_ as Actor;
        base.CopyFrom(other, newtimeline);
        //_is_croach = other._is_croach;
        //_is_croach_control = other._is_croach_control;
        IsDead = other.IsDead;
        IsPreDead = other.IsPreDead;
        _is_short = other._is_short;
        _is_armored = other._is_armored;

        _speed_struct = other._speed_struct;
        walk_sync_phase = other.walk_sync_phase;
        run_sync_phase = other.run_sync_phase;
        croach_sync_phase = other.croach_sync_phase;

        _parent_guard_name = other._parent_guard_name;
        _primary_child_info = other._primary_child_info;

        grabbed_actor = other.grabbed_actor;
        is_drag_grabbed_actor = other.is_drag_grabbed_actor;

        linked_mark = other.linked_mark;
        linked_broken_step = other.linked_broken_step;

        croachControlComponent = GetComponent<CroachControlComponent>();
    }

    public void InitActorLinks()
    {
        // if (LinkedInTimeWithName() != null)
        // {
        //     var actor = _timeline.GetActor(LinkedInTimeWithName());
        //     // var gv = GuardView();
        //     // var agv = actor.GuardView();

        //     // if (gv != null && agv != null)
        //     //     gv.SetLinkedInTimeWith(agv);
        // }
    }

    public override ObjectOfTimeline Copy(ITimeline newtimeline)
    {
        Actor obj = new Actor();
        obj.CopyFrom(this, newtimeline);
        return obj;
    }

    //public void SynchronizeLocalTime() { }

    protected override bool IsStateEqualImpl(ObjectOfTimeline aobj)
    {
        var obj = aobj as Actor;

        if (obj == null)
            return false;

        if (base.IsStateEqualImpl(obj) == false)
            return false;

        return true;
    }
}

// public class SetMovedWithCard : EventCard<ObjectOfTimeline>
// {
// 	ObjectId prev; ObjectId next;
// 	public SetMovedWithCard(long step, ObjectId prev, ObjectId next)
// 		: base(step)
// 	{
// 		this.prev = prev;
// 		this.next = next;
// 	}

// 	public override void on_forward_enter(global::System.Int64 current_step, ObjectOfTimeline obj)
// 	{
// 		(obj as Actor).SetMovedWith(next);
// 	}

// 	public override void on_backward_leave(global::System.Int64 current_step, ObjectOfTimeline obj)
// 	{
// 		(obj as Actor).SetMovedWith(prev);
// 	}
// }
