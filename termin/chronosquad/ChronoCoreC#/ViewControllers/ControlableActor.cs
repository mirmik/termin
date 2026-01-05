using System;
using System.Collections;
using System.Collections.Generic;
#if UNITY_64
using UnityEngine;
using UnityEngine.UI;
using UnityEngine.AI;
using UnityEngine.Experimental.AI;
using Unity.AI.Navigation;
#endif

public class ControlableActor : MonoBehaviour
{
    GuardView _guard_view;
    AvatarView _avatar_view;
    UserInterfaceCanvas _user_interface_canvas;
    ChronosphereController _chronosphere_controller;
    ObjectController _object_controller;

    NavMeshLinkSupervisor _nav_mesh_link_supervisor;

    // public void DeleteVariant()
    // {
    // 	var obj = GetObject();
    // 	var current_timeline_step = obj.LocalStep();
    // 	var object_start_timeline_step = obj.ObjectStartTimelineStep();

    // 	var timeline = obj.GetTimeline() as Timeline;
    // 	timeline.RemoveObject(obj);

    // 	Debug.Log("Пересчитываю вариант");
    // 	timeline.Promote(object_start_timeline_step);
    // 	timeline.Promote(current_timeline_step);
    // }

    public GameAction _used_action
    {
        get { return UsedActionBuffer.Instance.UsedAction; }
    }

    //NavMeshAgent _nav_mesh_agent;

    //GameObject _collider;

    //NavMeshAgent _nav_mes_tester;

    public int ActorNavArea()
    {
        return GetObject().NavArea();
    }

    // bool IsAreaApprochability(int area)
    // {
    // 	var approached = ActorNavArea();
    // 	if ( approached == PathFinding.AllAreas)
    // 		return true;

    // 	return (approached & (1 << area)) != 0;
    // }

    public Actor guard()
    {
        return _guard_view.guard() as Actor;
    }

    public ObjectOfTimeline Object()
    {
        return _object_controller.GetObject();
    }

    public ObjectOfTimeline GetObject()
    {
        return _object_controller.GetObject();
    }

    enum DefaultInteractionType
    {
        None,
        SwapHost,
        AirAtack,
    }

    DefaultInteractionType EvaluateDefaultInteraction(GameObject obj, int layer)
    {
        SwapHostAction swap_host = GetComponent<SwapHostAction>();

        if (swap_host != null)
        {
            if (swap_host.CanUseOnObject(obj))
            {
                return DefaultInteractionType.SwapHost;
            }
        }

        return DefaultInteractionType.None;
    }

    public void on_hover_another_while_selected(GameObject obj, int layer)
    {
        if (_used_action != null)
        {
            bool can_use_on = _used_action.CanUseOnObject(obj);
            if (can_use_on)
            {
                PathViewer.Instance.UpdatePathView(obj.transform.position, obj, Object().NavArea());
                //CursorController.Instance.SetCursor(CursorType.Hack);
            }
            else
            {
                CursorController.Instance.SetCursor(CursorType.Default);
            }
        }
        else
        {
            var default_interaction = EvaluateDefaultInteraction(obj, layer);

            switch (default_interaction)
            {
                case DefaultInteractionType.None:
                    CursorController.Instance.SetCursor(CursorType.Default);
                    break;
                case DefaultInteractionType.SwapHost:
                    CursorController.Instance.SetCursor(CursorType.SwapHost);
                    break;
                default:
                    CursorController.Instance.SetCursor(CursorType.Default);
                    break;
            }
        }
    }

    void Awake()
    {
        _avatar_view = this.GetComponent<AvatarView>();
        _object_controller = this.GetComponent<ObjectController>();
        _guard_view = this.GetComponent<GuardView>();
        _chronosphere_controller = GameObject
            .Find("Timelines")
            .GetComponent<ChronosphereController>();
        _user_interface_canvas = GameObject
            .Find("ChronoSphereInterface")
            .GetComponent<UserInterfaceCanvas>();
        //_collider = this.transform.Find("Collider").gameObject;
        _nav_mesh_link_supervisor = GameObject
            .Find("NavMeshLinkSupervisor")
            .GetComponent<NavMeshLinkSupervisor>();
    }

    void Start()
    {
        if (IsSelected())
        {
            _user_interface_canvas.set_activity_list_to_panel(Activities());
        }
    }

    public bool IsControlableByUser()
    {
        return _object_controller.IsControlableByUser();
    }

    void Update()
    {
        if (IsSelected())
        {
            var activities = Activities();
            _user_interface_canvas.SetActivities(activities);

            var obj = GetObject();
            if (obj.DirrectControlled != default(ObjectId))
            {
                var current_timeline_controller = GameCore.CurrentTimelineController();

                var object_controller_for_controlled =
                    current_timeline_controller.GetObjectController(obj.DirrectControlled.name);

                var controlled_activities = object_controller_for_controlled.Activities();

                _user_interface_canvas.SetAdditionalActivities(controlled_activities);
            }
            else
            {
                _user_interface_canvas.SetAdditionalActivities(null);
            }
        }
    }

    public MyList<Activity> Activities()
    {
        return _object_controller.Activities();
    }

    public bool IsSelected()
    {
        return _object_controller.IsSelected();
    }

    public void OnSelect()
    {
        // _user_interface_canvas.set_activity_list_to_panel(Activities());

        // var obj = GetObject();
        // if (obj.Controlled != null)
        // {
        // 	var current_timeline_controller =
        // 		GameCore.CurrentTimelineController();

        // 	var object_controller_for_controlled =
        // 		current_timeline_controller.GetObjectController(
        // 			obj.Controlled);

        // 	var controlled_activities =
        // 		object_controller_for_controlled.Activities();

        // 	_user_interface_canvas.
        // 		set_additional_activity_list_to_panel(controlled_activities);
        // }
    }

    public void unselect()
    {
        if (GameCore.SelectedActor() == this)
        {
            GameCore.DropSelectedActor();
        }
    }

    public string Info()
    {
        return guard().Info();
    }

    public void Stop()
    {
        guard().Stop(GameCore.Chronosphere().current_timeline());
    }

    bool IsPassiveTimePassForThisActor()
    {
        return GetObject().IsPassiveTimePass();
    }

    string Name()
    {
        return guard().Name();
    }

    bool IsPast()
    {
        return GameCore.Chronosphere().current_timeline().IsPast();
    }

    public ObjectId MovedWithFrame()
    {
        return guard().MovedWith();
    }

    ObjectId PlatformName(GameObject hit)
    {
        if (hit == null)
            return new ObjectId();
        var platform = hit.GetComponent<PlatformView>();
        if (platform == null)
        {
            var parent = hit.transform.parent;
            if (parent == null)
                return new ObjectId();
            platform = parent.GetComponent<PlatformView>();
            if (platform == null)
                return new ObjectId();
        }
        return new ObjectId(platform.name);
    }

    public void on_right_enviroment_clicked_while_selected(
        Vector3 pos,
        bool double_click,
        GameObject hit
    )
    {
        var chronosphere = GameCore.Chronosphere();
        if (GetObject() is Actor)
        {
            if (_used_action != null)
            {
                _used_action.Cancel();
            }
            return;
        }
    }

    public void on_air_click(
        Vector3 pos,
        bool double_click,
        GameObject hit,
        bool only_rotate = false
    )
    {
        var drone = GetComponent<DroneController>();
        var selected_object = GetObject();
        var stamp = selected_object.LocalStep();

        var frame = NavMeshLinkSupervisor.Instance.PlatformIdForPosition(pos);
        if (only_rotate)
        {
            var command2 = new SightToCommand(
                ReferencedPoint.FromGlobalPosition(pos, frame, selected_object.GetTimeline()),
                AnimationType.Idle,
                stamp
            );
            selected_object.CommandBuffer().AddExternalCommand(command2);
            return;
        }

        var command = new AirMovingCommand(
            ReferencedPoint.FromGlobalPosition(
                pos + new Vector3(0, drone.AirLevel, 0),
                default,
                selected_object.GetTimeline()
            ),
            WalkingType.Run,
            stamp
        );
        if (selected_object.CommandBuffer() != null)
        {
            selected_object.CommandBuffer().AddExternalCommand(command);
        }
    }

    public void on_promise_clicked_while_selected(Vector3 pos, bool double_click, GameObject hit)
    {
        Debug.Log("on_promise_clicked_while_selected");
        var promise = hit.GetComponent<PromiseMark>();
        var promise_id = promise.GetObjectController();

        var rpos = PathFinding.NavMeshPoint(pos, GameCore.CurrentTimeline());
        var command = new RestoreReverseMarkCommand(rpos, promise_id, Object().LocalStep());
        Object().CommandBuffer().AddExternalCommand(command);
    }

    public void on_enviroment_clicked_while_selected(
        Vector3 pos,
        ClickInformation click,
        bool only_rotate = false
    )
    {
        var hit = click.environment_hit.collider.gameObject;
        ObjectId platform_name = PlatformName(hit);

        if (GameCore.Chronosphere().current_timeline() != Object().GetTimeline())
        {
            Debug.Log(
                "Prevent: GameCore.Chronosphere().current_timeline() != guard().GetTimeline()"
            );
            return;
        }

        var chronosphere = GameCore.Chronosphere();
        var selected_object = GetObject();

        if (_avatar_view != null)
        {
            var controlled = selected_object.DirrectControlled;
            if (controlled != default(ObjectId))
            {
                var controlled_controller = GameCore
                    .CurrentTimelineController()
                    .GetObjectController(controlled.name);
                selected_object = controlled_controller.GetObject();
            }
        }

        var selected_actor = selected_object as Actor;

        if (
            selected_object is Actor
            && ((selected_object as Actor).IsDead || (selected_object as Actor).IsPreDead)
        )
        {
            if (_used_action != null)
                _used_action.Cancel();
            return;
        }

        if (IsPassiveTimePassForThisActor())
        {
            return;
        }

        var drone = GetComponent<DroneController>();
        if (drone != null)
        {
            //var point = AirEnvironmentHit(Input.mousePosition);
            on_air_click(pos, click.double_click, hit, only_rotate);
            return;
        }

        if (Input.GetKey(KeyCode.LeftControl) && selected_actor.IsGrab())
        {
            UngrabMove(pos, selected_actor, click, platform_name);
            return;
        }

        if (!selected_object.IsMovable())
            return;

        MoveOrRotateTo(pos, only_rotate, selected_actor, click);
    }

    void UngrabMove(
        Vector3 pos,
        Actor selected_actor,
        ClickInformation click,
        ObjectId platform_name
    )
    {
        UnityEngine.AI.NavMeshHit hit3;
        UnityEngine.AI.NavMesh.SamplePosition(
            pos,
            out hit3,
            PathFinding.SampleDistance,
            UnityEngine.AI.NavMesh.AllAreas
        );
        pos = hit3.position;

        // selected_actor.UnGrab(
        // 	ReferencedPoint.FromGlobalPosition(pos, platform_name, selected_object.GetTimeline())
        // );

        selected_actor.AddExternalCommand(
            new UnGrabCommand(
                ReferencedPoint.FromGlobalPosition(
                    pos,
                    platform_name,
                    selected_actor.GetTimeline()
                ),
                selected_actor.LocalStep(),
                walktype: ToWalkingType(click.double_click, selected_actor.IsCroachControl())
            )
        );
    }

    void MoveOrRotateTo(Vector3 pos, bool only_rotate, Actor selected_actor, ClickInformation click)
    {
        var is_run = click.double_click && !selected_actor.IsGrab();
        var is_croach = selected_actor.IsCroachControl();
        var stamp = selected_actor.LocalStep();
        var walking_type =
            is_run ? WalkingType.Run
            : is_croach ? WalkingType.Croach
            : WalkingType.Walk;

        pos = PathFinding.NavMeshPoint_Global(pos, ActorNavArea());
        var area_name = NavMeshLinkSupervisor.Instance.PlatformIdForPosition(pos);

        if (only_rotate)
        {
            var frame = NavMeshLinkSupervisor.Instance.PlatformIdForPosition(pos);
            var command2 = new SightToCommand(
                ReferencedPoint.FromGlobalPosition(pos, frame, selected_actor.GetTimeline()),
                is_croach ? AnimationType.CroachIdle : AnimationType.Idle,
                stamp
            );
            selected_actor.CommandBuffer().AddExternalCommand(command2);
            return;
        }

        var command = new MovingCommand(
            ReferencedPoint.FromGlobalPosition(pos, area_name, selected_actor.GetTimeline()),
            walking_type,
            stamp
        );
        if (selected_actor.CommandBuffer() != null)
        {
            selected_actor.CommandBuffer().AddExternalCommand(command);
        }
    }

    public void on_lean_clicked_while_selected(
        Vector3 top_position,
        bool double_click,
        GameObject navmeshlink,
        BracedCoordinates braced_coordinates,
        ClickInformation click
    )
    {
        if (_used_action != null)
        {
            _used_action.OnEnvironmentClick(click);
            return;
        }

        var is_run = double_click && !guard().IsGrab();
        var is_croach = guard().IsCroachControl();
        var stamp = Object().LocalStep();
        var walking_type =
            is_run ? WalkingType.Run
            : is_croach ? WalkingType.Croach
            : WalkingType.Walk;

        var frame = GameCore.FrameNameForPosition(top_position);
        var pos = GameCore.NavSamplePosition(top_position);
        var current_position = Object()
            .CurrentReferencedPose()
            .GlobalPosition(Object().GetTimeline());
        var current_position_mask = GameCore.NavSampleAreaMask(current_position);

        var command = new MovingCommand(
            ReferencedPoint.FromGlobalPosition(pos, frame, Object().GetTimeline()),
            walking_type,
            stamp,
            target_type: PathFindingTarget.Lean,
            braced_coordinates: braced_coordinates
        );
        guard().CommandBuffer().AddExternalCommand(command);
    }

    public void on_braced_clicked_while_selected(
        Vector3 top_position,
        bool double_click,
        GameObject navmeshlink,
        BracedCoordinates braced_coordinates,
        ClickInformation click
    )
    {
        if (_used_action != null)
        {
            _used_action.OnEnvironmentClick(click);
            return;
        }

        var is_run = double_click && !guard().IsGrab();
        var is_croach = guard().IsCroachControl();
        var stamp = Object().LocalStep();
        var walking_type =
            is_run ? WalkingType.Run
            : is_croach ? WalkingType.Croach
            : WalkingType.Walk;

        var frame = GameCore.FrameNameForPosition(top_position);
        var pos = GameCore.NavSamplePosition(top_position);
        var current_position = Object()
            .CurrentReferencedPose()
            .GlobalPosition(Object().GetTimeline());
        var current_position_mask = GameCore.NavSampleAreaMask(current_position);

        var command = new MovingCommand(
            ReferencedPoint.FromGlobalPosition(pos, frame, Object().GetTimeline()),
            walking_type,
            stamp,
            target_type: PathFindingTarget.Braced,
            start_type: current_position_mask == 8192
                ? PathFindingTarget.Braced
                : PathFindingTarget.Standart,
            braced_coordinates: braced_coordinates
        );
        guard().CommandBuffer().AddExternalCommand(command);
    }

    public void on_right_button_clicked_while_selected(Vector3 pos)
    {
        if (_used_action != null)
        {
            _used_action.Cancel();
            return;
        }
    }

    public void double_clicked_by_interface()
    {
        var position = Object().GlobalPose().position;
        var camera_obj = GameObject.Find("Main Camera");
        var camera = camera_obj.GetComponent<AbstractCameraController>();

        var platform_id = Object().MovedWith();
        var curtlctr = ChronosphereController.Instance.CurrentTimelineController();
        var objctr = curtlctr.GetObjectController(platform_id.name);

        var gravity = GameCore.GetGravityInGlobalPoint(position, platform_id);
        camera.TeleportToNewCenterWithNewReference(position, objctr.transform, -gravity);
    }

    WalkingType ToWalkingType(bool double_click, bool is_croach_control)
    {
        if (double_click)
            return WalkingType.Run;

        if (is_croach_control)
            return WalkingType.Croach;
        else
            return WalkingType.Walk;
    }

    public bool left_click_on_another_actor(
        GameObject another_actor,
        ClickInformation clickInformation
    )
    {
        var pos = clickInformation.actor_hit.point;
        var envhit = clickInformation.environment_hit.point;

        if (_used_action != null)
        {
            _used_action.OnActorClick(another_actor, clickInformation);
            return true;
        }

        if (_avatar_view != null)
        {
            var controlled = _object_controller.GetObject().DirrectControlled;
            if (controlled == default(ObjectId))
                return _avatar_view.LeftClickOnAnotherActor(another_actor, pos);
        }

        if (GameCore.Chronosphere().current_timeline() != Object().GetTimeline())
        {
            Debug.Log(
                "Prevent: GameCore.Chronosphere().current_timeline() != guard().GetTimeline()"
            );
            return false;
        }

        if (Input.GetKey(KeyCode.LeftControl))
        {
            if (guard().IsGrab())
            {
                return true;
            }

            var other = another_actor.GetComponent<GuardView>().guard();

            if (other == guard())
            {
                return true;
            }

            if (other == GetObject() || (!other.IsDead && !other.IsPreDead))
            {
                if (guard()._can_grab_alived)
                {
                    bool is_croach =
                        guard().IsCroachControl() || guard().CanGrabCorpseStayed() == false;

                    // guard().Grab(
                    // 	other,
                    // 	is_dragging: guard().IsShort());
                    WalkingType walktype = ToWalkingType(clickInformation.double_click, is_croach);
                    guard()
                        .AddExternalCommand(
                            new GrabCommand(
                                other.ObjectId(),
                                guard().LocalStep(),
                                walktype: walktype,
                                is_dragging: guard().IsShort()
                            )
                        );
                }

                return true;
            }

            if (guard().CanGrabCorpse())
            {
                bool is_croach =
                    guard().IsCroachControl() || guard().CanGrabCorpseStayed() == false;

                // guard().Grab(
                // 	other,
                // 	is_dragging: guard().IsShort());
                WalkingType walktype = ToWalkingType(clickInformation.double_click, is_croach);
                guard()
                    .AddExternalCommand(
                        new GrabCommand(
                            other.ObjectId(),
                            guard().LocalStep(),
                            walktype: walktype,
                            is_dragging: guard().IsShort()
                        )
                    );
            }

            return true;
        }

        var clicked_object = another_actor.GetComponent<ObjectController>().GetObject();
        var interaction = clicked_object.GetInteraction();
        if (interaction != null)
        {
            Object().MoveToInteraction(clicked_object);
            return true;
        }

        on_enviroment_clicked_while_selected(pos, clickInformation);
        return false;
    }

    public void AddCommand(ActorCommand command)
    {
        var command_buffer_behaviour = guard().CommandBuffer();
        if (command_buffer_behaviour == null)
        {
            Debug.Log("Command buffer is null");
            return;
        }

        command_buffer_behaviour.AddExternalCommand(command);
    }

    // public MyList<Animatronic> GetAnimatronicsList()
    // {
    // 	var list = Object().GetAnimatronicsList();
    // 	return list;
    // }

    public void CroachSwitch()
    {
        if (_avatar_view != null)
        {
            var controlled = _object_controller.GetObject().DirrectControlled;
            if (controlled != default(ObjectId))
            {
                var ctrobj = Object().GetTimeline().GetObject(controlled);
                (ctrobj as Actor).CroachSwitch();
            }
            return;
        }

        guard().CroachSwitch();
    }
}
