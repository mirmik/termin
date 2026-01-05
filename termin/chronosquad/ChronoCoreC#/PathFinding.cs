using System;
using System.Collections;
using System.Collections.Generic;
using Unity.AI.Navigation;
#if UNITY_64
using UnityEngine;
#endif

public enum PathFindingTarget
{
    Braced,
    Lean,
    Burrow,
    Standart,
}

public static class PathFinding
{
    public const float SampleDistance = 0.5f;

    public struct Arguments
    {
        public NavMeshLink nav_mesh_link;
        public Vector3 point;
        public ITimeline timeline;
        public UnitPath unit_path;
        public bool use_normal_as_up;
    }

    public static ReferencedPoint GlobalToFramedPosition(
        Vector3 pos,
        ITimeline timeline,
        ObjectId frame
    )
    {
        if (frame.hash == 0)
        {
            return new ReferencedPoint(pos, null);
        }
        var pose = timeline.GetFrame(frame);
        var local_position = pose.InverseTransformPoint(pos);
        return new ReferencedPoint(local_position, frame);
    }

    public static ReferencedPoint VectorToReferencedPoint(Vector3 pos, ITimeline timeline)
    {
        var area_name = NavMeshLinkSupervisor.Instance.PlatformIdForPosition(pos);
        var local_position = GlobalToFramedPosition(pos, timeline, area_name);
        return local_position;
    }

    public static void UnitPathForRawPath_CLIMBING_LINK_AREA(ref Arguments args)
    {
        var area_mask = 1 << args.nav_mesh_link.area;
        var parent = GameCore.FindInParentTree<CommonClimbingBlock>(args.nav_mesh_link.gameObject);
        var braced_coordinates = parent.BracedCoordinates(args.nav_mesh_link);

        var type =
            area_mask == 8192 ? UnitPathPointType.BracedClimbingLink : UnitPathPointType.BracedToUp;

        var p = VectorToReferencedPoint(args.point, args.timeline);
        args.unit_path.AddPassPoint(
            p,
            type,
            null,
            normal: Vector3.up,
            braced_coordinates: braced_coordinates
        );
    }

    public static void UnitPathForRawPath_DOOR_LINK_AREA(ref Arguments args)
    {
        var platform_name = NavMeshLinkSupervisor.Instance.PlatformIdForPosition(args.point);

        var door = GameCore.FindInParentTree<DoorView>(args.nav_mesh_link.gameObject);
        if (door == null)
        {
            Debug.Log("Door not found");
            return;
        }

        var braced_coordinates = door.BracedCoordinates(exit_side: args.point);

        var local_point = GlobalToFramedPosition(args.point, args.timeline, platform_name);

        args.unit_path.AddPassPoint(
            local_point,
            UnitPathPointType.DoorLink,
            null,
            braced_coordinates: braced_coordinates,
            normal: Vector3.up
        );
    }

    public static void UnitPathForRawPath_UNKNOWN_LINK_AREA(ref Arguments args)
    {
        var platform_name = NavMeshLinkSupervisor.Instance.PlatformIdForPosition(args.point);

        var local_point = GlobalToFramedPosition(args.point, args.timeline, platform_name);
        args.unit_path.AddPassPoint(
            local_point,
            UnitPathPointType.StandartMesh,
            null,
            normal: EvaluateNormal(args.point, args.use_normal_as_up, platform_name)
        );

        Debug.Log("Unknown link type: " + NumberOfBitFromMask(args.nav_mesh_link.area));
    }

    public static void UnitPathForRawPath_SEW_LINK_AREA(ref Arguments args)
    {
        Debug.Log("Sew link area");
        // var platform_name =
        // 	NavMeshLinkSupervisor.Instance.PlatformIdForPosition(point);


        // var local_point = GlobalToFramedPosition(point, timeline, platform_name);
        // unit_path.AddPassPoint(local_point,
        // 	UnitPathPointType.StandartMesh,
        // 	null,
        // 	normal: EvaluateNormal(point, use_normal_as_up));

        // Debug.Log("Unknown link type: " + NumberOfBitFromMask(nav_mesh_link.area));
    }

    public static void UnitPathForRawPath_UPSTAIRS_LINK_AREA(ref Arguments args)
    {
        var platform_name = NavMeshLinkSupervisor.Instance.PlatformIdForPosition(args.point);

        Debug.Log("Platform: " + platform_name);

        var parent = GameCore.FindInParentTree<Upstairs>(args.nav_mesh_link.gameObject);
        var braced_coordinates = parent.BracedCoordinates();

        var local_point = GlobalToFramedPosition(args.point, args.timeline, platform_name);
        args.unit_path.AddPassPoint(
            local_point,
            UnitPathPointType.StandartMesh,
            braced_coordinates,
            normal: EvaluateNormal(args.point, args.use_normal_as_up, platform_name)
        );
    }

    public static void UnitPathForRawPath_WALL_LINK_AREA(ref Arguments args)
    {
        var platform_name = NavMeshLinkSupervisor.Instance.PlatformIdForPosition(args.point);

        var local_point = GlobalToFramedPosition(args.point, args.timeline, platform_name);
        args.unit_path.AddPassPoint(
            local_point,
            UnitPathPointType.StandartMesh,
            null,
            normal: EvaluateNormal(args.point, args.use_normal_as_up, platform_name)
        );
    }

    public static bool UnitPathForRawPath_BRACED_LINK_AREA(ref Arguments args)
    {
        var platform_name = NavMeshLinkSupervisor.Instance.PlatformIdForPosition(args.point);
        bool target_is_braced = false;

        var up_point = args.nav_mesh_link.transform.TransformPoint(args.nav_mesh_link.startPoint);
        var down_point = args.nav_mesh_link.transform.TransformPoint(args.nav_mesh_link.endPoint);

        var distance_to_up = Vector3.Distance(args.point, up_point);
        var distance_to_down = Vector3.Distance(args.point, down_point);

        bool down_is_target = distance_to_down < distance_to_up;
        var final_point = down_is_target ? down_point : up_point;

        var normal = EvaluateNormal(args.point, args.use_normal_as_up, platform_name);
        var parent = GameCore.FindInParentTree<CommonClimbingBlock>(args.nav_mesh_link.gameObject);
        //var braced_coordinates = parent.BracedCoordinates(args.nav_mesh_link);
        var bcs = args.nav_mesh_link.GetComponent<UpDownBracedCoordinateGenerator>();
        var braced_coordinates = bcs.GenerateBracedCoordinates();
        if (!down_is_target)
        {
            if (braced_coordinates == default)
            {
                Debug.Log("braced_coordinates is null");
                return true;
            }

            //var platform_name_2 = ChronosphereController.
            //	GetPlatformName(GameCore.GetNavmMeshAreaForPosition(point));
            var platform_name_2 = NavMeshLinkSupervisor.Instance.FoundPlatformId(parent.gameObject);

            var local_point_2 = GlobalToFramedPosition(
                bcs.EdgeGlobalPosition(),
                args.timeline,
                platform_name_2
            );

            args.unit_path.AddPassPoint(
                local_point_2,
                UnitPathPointType.DownToBraced,
                null,
                braced_coordinates: braced_coordinates,
                normal: normal
            );

            if (target_is_braced && Vector3.Distance(final_point, args.point) < 1.0f)
            {
                return true;
            }

            args.unit_path.AddPassPoint(
                local_point_2,
                UnitPathPointType.BracedToUp,
                null,
                braced_coordinates: braced_coordinates,
                normal: normal
            );
        }
        else
        {
            var platform_name_3 = NavMeshLinkSupervisor.Instance.PlatformIdForPosition(args.point);
            var local_point_3 = GlobalToFramedPosition(args.point, args.timeline, platform_name_3);

            args.unit_path.AddPassPoint(
                local_point_3,
                UnitPathPointType.JumpDown,
                null,
                braced_coordinates: braced_coordinates,
                normal: normal
            );
        }

        return false;
    }

    // static public void UnitPathForRawPath_CLIMBING_AREA_MASK(
    // 	NavMeshLink nav_mesh_link,
    // 	int area_mask,
    // 	Vector3 point,
    // 	ITimeline timeline,
    // 	UnitPath unit_path,
    // 	NavMeshLinkSupervisor nav_mesh_link_supervisor
    // ) {
    // 	var braced_coordinates = nav_mesh_link_supervisor.
    // 					BracedCoordinatesForClimbingSurface(point);

    // 				var platform_name = ChronosphereController
    // 					.GetPlatformName(GameCore.GetNavmMeshAreaForPosition(point));

    // 				var local_point = GlobalToFramedPosition(point, timeline, platform_name);
    // 				unit_path.AddPassPoint(local_point,
    // 					UnitPathPointType.BracedHang, nav_mesh_link,
    // 					braced_coordinates:braced_coordinates,
    // 					normal: Vector3.up);
    //}

    static public Vector3 EvaluateNormal(
        Vector3 point,
        bool use_normal_as_up,
        ObjectId platform_name
    )
    {
        if (use_normal_as_up)
            return GameCore.NormalForSurfacePoint(point);
        else
            return GameCore.UpForWorldPoint(point, platform_name);
    }

    public static void UnitPathForRawPath_STANDART_AREA_MASK(
        Vector3 point,
        ITimeline timeline,
        UnitPath unit_path,
        bool use_normal_as_up,
        ObjectId current_frame = default(ObjectId)
    )
    {
        var platform_name = unit_path.LastFrame();
        var normal = EvaluateNormal(point, use_normal_as_up, platform_name);
        var local_point = GlobalToFramedPosition(point, timeline, platform_name);
        unit_path.AddPassPoint(local_point, UnitPathPointType.StandartMesh, null, normal: normal);
    }

    public static void UnitPathForRawPath_WALLS_FOR_ZERO_GRAVITY_AREA_MASK(
        Vector3 point,
        ITimeline timeline,
        UnitPath unit_path,
        bool use_normal_as_up,
        ObjectId current_frame = default(ObjectId)
    )
    {
        var platform_name = unit_path.LastFrame();
        var normal = EvaluateNormal(point, true, platform_name);
        var local_point = GlobalToFramedPosition(point, timeline, platform_name);
        unit_path.AddPassPoint(local_point, UnitPathPointType.StandartMesh, null, normal: normal);
    }

    public static void UnitPathForRawPath_BRACED_AREA_MASK(
        Vector3 point,
        ITimeline timeline,
        UnitPath unit_path,
        bool use_normal_as_up,
        ObjectId current_frame = default(ObjectId)
    )
    {
        var platform_name = NavMeshLinkSupervisor.Instance.PlatformIdForPosition(point);

#if !(UNITY_64) // For Tests
        platform_name = current_frame;
#endif
        var climbing_block = NavMeshLinkSupervisor.Instance.FoundNearestClimbingBlock(point);

        var braced_coordinates = climbing_block.GetBracedCoordinates(point);

        var normal = EvaluateNormal(point, use_normal_as_up, platform_name);

        var local_point = GlobalToFramedPosition(point, timeline, platform_name);
        unit_path.AddPassPoint(
            local_point,
            UnitPathPointType.BracedHang,
            null,
            normal: normal,
            braced_coordinates: braced_coordinates
        );
    }

    public static void UnitPathForRawPath_UPSTAIRS_AREA_MASK(
        Vector3 point,
        ITimeline timeline,
        UnitPath unit_path,
        bool use_normal_as_up,
        ObjectId current_frame = default(ObjectId)
    )
    {
        var platform_name = NavMeshLinkSupervisor.Instance.PlatformIdForPosition(point);
        var up = EvaluateNormal(point, false, platform_name);
        var forward = EvaluateNormal(point, true, platform_name);

        var braced_coordinates = UpstairsSupervisor.Instance.GetBracedCoordinates(point);
        var local_point = GlobalToFramedPosition(point, timeline, platform_name);
        unit_path.AddPassPoint(
            local_point,
            UnitPathPointType.UpstairsMove,
            braced_coordinates,
            normal: up
        );
    }

    public static void UnitPathForRawPath_TO_BURROW_AREA_ZONE(
        int area_mask,
        Vector3 point,
        ITimeline timeline,
        UnitPath unit_path,
        bool use_normal_as_up,
        NavMeshLinkSupervisor nav_mesh_link_supervisor,
        ObjectId current_frame = default(ObjectId)
    )
    {
        var platform_name = NavMeshLinkSupervisor.Instance.PlatformIdForPosition(point);

#if !(UNITY_64) // For Tests
        platform_name = current_frame;
#endif

        var normal = EvaluateNormal(point, use_normal_as_up, platform_name);

        var local_point = GlobalToFramedPosition(point, timeline, platform_name);
        unit_path.AddPassPoint(local_point, UnitPathPointType.ToBurrowZone, null, normal: normal);
    }

    public static void UnitPathForRawPath_FROM_BURROW_AREA_ZONE(
        int area_mask,
        Vector3 point,
        ITimeline timeline,
        UnitPath unit_path,
        NavMeshLinkSupervisor nav_mesh_link_supervisor,
        bool use_normal_as_up,
        ObjectId current_frame = default(ObjectId)
    )
    {
        var platform_name = NavMeshLinkSupervisor.Instance.PlatformIdForPosition(point);

#if !(UNITY_64) // For Tests
        platform_name = current_frame;
#endif

        var normal = EvaluateNormal(point, use_normal_as_up, platform_name);

        var local_point = GlobalToFramedPosition(point, timeline, platform_name);
        unit_path.AddPassPoint(local_point, UnitPathPointType.FromBurrowZone, null, normal: normal);
    }

    public static void UnitPathForRawPath_DOWN_MOVE_LINK_AREA(
        LinkData nav_mesh_link,
        int area_mask,
        Vector3 point,
        ITimeline timeline,
        UnitPath unit_path,
        bool use_normal_as_up,
        NavMeshLinkSupervisor nav_mesh_link_supervisor,
        ObjectId current_frame = default(ObjectId)
    )
    {
        var platform_name = NavMeshLinkSupervisor.Instance.PlatformIdForPosition(point);

#if !(UNITY_64)
        platform_name = current_frame;
#endif

        var local_point = GlobalToFramedPosition(
            point,
            timeline,
            platform_name == default(ObjectId) ? current_frame : platform_name
        );
        unit_path.AddPassPoint(
            local_point,
            UnitPathPointType.StandartMesh,
            nav_mesh_link,
            normal: EvaluateNormal(point, use_normal_as_up, platform_name)
        );
    }

    public static int NumberOfBitFromMask(int n)
    {
        if (n == 0)
            return 0;

        int mask = 1;
        for (int i = 0; i < 32; i++, mask <<= 1)
            if ((n & mask) != 0)
                return i;

        return 32;
    }

    static UnityEngine.AI.NavMeshPath path_storage = new UnityEngine.AI.NavMeshPath();

    public static UnityEngine.AI.NavMeshPath RawPathFinding(
        Vector3 start_position,
        Vector3 finish_position,
        int areas,
        //out PlatformAreaBase platform,
        bool navmesh_precast = true
    )
    {
        PlatformAreaBase platform = null;
        if (navmesh_precast)
            finish_position = NavMeshPoint_Global(
                finish_position,
                layer_mask: areas,
                sample_distance: SampleDistance
            );

        //start_position = NavMeshPoint_Global(start_position);

        if (NavMeshLinkSupervisor.Instance != null)
        {
            PlatformAreaBase start_platform = NavMeshLinkSupervisor.Instance.PlatformForPosition(
                start_position
            );
            PlatformAreaBase finish_platform = NavMeshLinkSupervisor.Instance.PlatformForPosition(
                finish_position
            );

            if (start_platform == null || finish_platform == null)
            {
                //Debug.Log("Platform not found " + start_position + " " + finish_position);
                platform = null;
                return new UnityEngine.AI.NavMeshPath();
            }

            if (
                (start_platform != null)
                && (finish_platform != null)
                && (start_platform == finish_platform)
            )
            {
                platform = start_platform;
                start_position = platform.NavigatePosition(start_position);
                finish_position = platform.NavigatePosition(finish_position);
                //Debug.Log("Platform found " + start_position + " " + finish_position);
            }
        }

        UnityEngine.AI.NavMeshPath path = path_storage;
        UnityEngine.AI.NavMesh.CalculatePath(start_position, finish_position, areas, path);

        if (platform != null)
        {
            for (int i = 0; i < path.corners.Length; i++)
            {
                path.corners[i] = platform.InvertNavigatePosition(path.corners[i]);
            }
        }

        if (path.status != UnityEngine.AI.NavMeshPathStatus.PathComplete)
        {
            //Debug.Log("Pathfinding: Path not found");
            //return new UnityEngine.AI.NavMeshPath();
        }

        return path;
    }

#if UNITY_64
    public const int AllAreas = UnityEngine.AI.NavMesh.AllAreas;
#else
    public const int AllAreas = -1;
#endif

    static public UnityEngine.AI.NavMeshPath RawPathFinding(
        ReferencedPoint start_position,
        ReferencedPoint pos,
        ITimeline timeline,
        int areas,
        //out PlatformAreaBase platform,
        bool navmesh_precast = false
    )
    {
        var sp = start_position.GlobalPosition(timeline);
        var tp = pos.GlobalPosition(timeline);

        return RawPathFinding(
            sp,
            tp,
            areas,
            //out platform,
            navmesh_precast: navmesh_precast
        );
    }

    public static UnityEngine.AI.NavMeshPath MakeRawPathForMoving(
        ObjectOfTimeline actor,
        ITimeline timeline,
        ReferencedPoint start_position,
        ReferencedPoint finish_position,
        PathFindingTarget _start_type,
        PathFindingTarget _target_type,
        BracedCoordinates _braced_coordinates,
        //out PlatformAreaBase platform,
        bool navmesh_precast = false
    )
    {
        if (_start_type == PathFindingTarget.Braced && _target_type == PathFindingTarget.Braced)
        {
            var rawpath = PathFinding.RawPathfindingToBraced(
                start_position.GlobalPosition(timeline),
                _braced_coordinates,
                timeline,
                //out platform,
                areas: 8192
            );

            if (rawpath.corners.Length != 0)
            {
                //platform = null;
                return rawpath;
            }
        }

        if (_target_type == PathFindingTarget.Braced || _target_type == PathFindingTarget.Lean)
        {
            return PathFinding.RawPathfindingToBraced(
                start_position.GlobalPosition(timeline),
                _braced_coordinates,
                timeline,
                //out platform,
                actor.NavArea()
            );
        }
        else
        {
            return PathFinding.RawPathFinding(
                start_position,
                finish_position,
                timeline,
                actor.NavArea(),
                //out platform,
                navmesh_precast: navmesh_precast
            );
        }
    }

    public static UnitPath MakeUnitPathForMoving(
        ObjectOfTimeline actor,
        ITimeline timeline,
        ReferencedPoint start_position,
        ReferencedPoint finish_position,
        PathFindingTarget _start_type,
        PathFindingTarget _target_type,
        BracedCoordinates _braced_coordinates,
        bool navmesh_precast,
        bool use_normal_as_up
    )
    {
        UnityEngine.AI.NavMeshPath rawpath = MakeRawPathForMoving(
            actor,
            timeline,
            start_position,
            finish_position,
            _start_type,
            _target_type,
            _braced_coordinates,
            //out static_brother,
            navmesh_precast: navmesh_precast
        );

        if (
            rawpath.corners.Length == 0
            || rawpath.status != UnityEngine.AI.NavMeshPathStatus.PathComplete
        )
        {
            //Debug.Log("Path not found");
            return new UnitPath();
        }

        var unitpath = PathFinding.UnitPathForRawPath(
            ref actor.unit_path_storage,
            rawpath,
            timeline,
            target_type: _target_type,
            current_frame: actor.CurrentReferencedPosition().Frame,
            use_normal_as_up: use_normal_as_up //,
        //static_brother: static_brother
        );

        if (_target_type == PathFindingTarget.Lean)
        {
            unitpath.AddPassPoint(finish_position, UnitPathPointType.Lean, _braced_coordinates);
        }

        return unitpath;
    }

    public static UnityEngine.AI.NavMeshPath RawPathfindingToBraced(
        Vector3 start_position,
        BracedCoordinates braced_coordinates,
        ITimeline timeline,
        //out PlatformAreaBase platform,
        int areas = AllAreas
    )
    {
        UnityEngine.AI.NavMeshHit hit;
        UnityEngine.AI.NavMesh.SamplePosition(
            braced_coordinates.TopPosition,
            out hit,
            SampleDistance,
            areas
        );

        if (!hit.hit)
        {
            //platform = null;
            return new UnityEngine.AI.NavMeshPath();
        }

        if (hit.mask == 8192)
        {
            var path = RawPathFinding(
                start_position,
                braced_coordinates.TopPosition,
                8192 //,
            //out platform
            );

            if (path.corners.Length != 0)
            {
                return path;
            }
        }

        return RawPathFinding(
            start_position,
            braced_coordinates.TopPosition,
            areas //,
        //out platform
        );
    }

    // Если последние движения - прыжок вниз и перемещение на небольшую дистанцию,
    // заменить их на прыжок вниз в последнюю точке
    static public bool ReduceForAirStrike(
        UnitPath unit_path,
        ITimeline timeline,
        float max_distance
    )
    {
        if (unit_path.Count < 2)
            return false;

        var last_point = unit_path[unit_path.Count - 1];
        var penultimate_point = unit_path[unit_path.Count - 2];

        if (
            last_point.type != UnitPathPointType.StandartMesh
            || penultimate_point.type != UnitPathPointType.JumpDown
        )
        {
            return false;
        }

        var last_point_position = last_point.position;
        var penultimate_point_position = penultimate_point.position;
        var distance = last_point_position.DistanceTo(penultimate_point_position, timeline);
        if (distance > max_distance)
        {
            return false;
        }

        unit_path.RemoveLast();
        penultimate_point.position = last_point_position;
        unit_path[unit_path.Count - 1] = penultimate_point;
        return true;
    }

    public static Vector3 NavMeshPoint_Global(
        Vector3 pos,
        int layer_mask = AllAreas,
        float sample_distance = SampleDistance
    )
    {
        PlatformAreaBase platform = null;
        if (NavMeshLinkSupervisor.Instance != null)
        {
            var platform_data = NavMeshLinkSupervisor.Instance.PlatformDataForPosition(pos);

            if (platform_data == null)
            {
                Debug.Log("Platform not found");
            }
            else
            {
                var platform_id = platform_data.frame_id;
                platform = platform_data.go.GetComponent<PlatformAreaBase>();
                pos = platform.NavigatePosition(pos);
            }
        }

        UnityEngine.AI.NavMeshHit hit;
        UnityEngine.AI.NavMesh.SamplePosition(pos, out hit, sample_distance, layer_mask);

        if (hit.hit)
        {
            if (platform != null)
                return platform.InvertNavigatePosition(hit.position);
            else
                return hit.position;
        }
        else
        {
            return Vector3.zero;
        }
    }

    public static Vector3 NavMeshPoint_Global_EditorMode(
        Vector3 pos,
        int layer_mask = AllAreas,
        float sample_distance = SampleDistance
    )
    {
        UnityEngine.AI.NavMeshHit hit;
        UnityEngine.AI.NavMesh.SamplePosition(pos, out hit, sample_distance, layer_mask);
        return hit.position;
    }

    public static ReferencedPoint NavMeshPoint(
        Vector3 pos,
        ITimeline timeline,
        ObjectId current_frame = default(ObjectId),
        bool weak_position_cast = false
    )
    {
        bool finded;
        return NavMeshPoint(pos, timeline, out finded, current_frame, weak_position_cast);
    }

    public static ReferencedPoint NavMeshPoint(
        Vector3 pos,
        ITimeline timeline,
        out bool finded,
        ObjectId override_frame = default(ObjectId),
        bool weak_position_cast = false
    )
    {
        Vector3 navigate_pos = pos;
        PlatformAreaBase platform = null;
        ObjectId platform_id = default(ObjectId);

        if (NavMeshLinkSupervisor.Instance != null)
        {
            var platform_data = NavMeshLinkSupervisor.Instance.PlatformDataForPosition(pos);
            if (platform_data == null)
            {
                finded = false;
                return new ReferencedPoint(Vector3.zero, null);
            }
            platform_id = platform_data.frame_id;
            platform = platform_data.go.GetComponent<PlatformAreaBase>();
            navigate_pos = platform.NavigatePosition(pos);
        }

        float sample_distance = weak_position_cast ? 100 : SampleDistance;
        UnityEngine.AI.NavMeshHit hit;
        UnityEngine.AI.NavMesh.SamplePosition(
            navigate_pos,
            out hit,
            sample_distance,
            UnityEngine.AI.NavMesh.AllAreas
        );

        if (hit.hit)
        {
            finded = true;
        }
        else
        {
            finded = false;
            return new ReferencedPoint(Vector3.zero, null);
        }

        //var area_name = NavMeshLinkSupervisor.Instance.PlatformIdForPosition(hit.position);

#if !(UNITY_64)
        //area_name = override_frame;
#endif
        var renavigated_pos = platform.InvertNavigatePosition(hit.position);

        var local_position = PathFinding.GlobalToFramedPosition(
            renavigated_pos,
            timeline,
            platform_id
        );
        return local_position;
    }

    public static MyList<Animatronic> PulledPathFrom(
        MyList<Animatronic> referenced_animatronics,
        ReferencedPose initial_pose,
        ITimeline timeline
    )
    {
        var pulled_path = new MyList<Animatronic>();
        var pose_of_pulled = initial_pose;
        foreach (var animatronic in referenced_animatronics)
        {
            if (animatronic is MovingAnimatronic)
            {
                var moving_animatronic = animatronic as MovingAnimatronic;
                var pulled = new PulledByAnimatronic(
                    moving_animatronic.StartStep,
                    moving_animatronic.FinishStep,
                    moving_animatronic,
                    pose_of_pulled
                );
                pulled_path.Add(pulled);
                pose_of_pulled = pulled.FinalPose(timeline);
            }
            else
            {
                //pulled_path.Add(animatronic);
            }
        }
        return pulled_path;
    }

    public static int NavMeshSampleMask(Vector3 point)
    {
        if (NavMeshLinkSupervisor.Instance != null)
        {
            var platform_data = NavMeshLinkSupervisor.Instance.PlatformDataForPosition(point);
            var platform_id = platform_data.frame_id;
            PlatformAreaBase platform = platform_data.go.GetComponent<PlatformAreaBase>();
            point = platform.NavigatePosition(point);
        }

        var hit = new UnityEngine.AI.NavMeshHit();
        if (
            !UnityEngine.AI.NavMesh.SamplePosition(
                point,
                out hit,
                SampleDistance,
                UnityEngine.AI.NavMesh.AllAreas
            )
        )
        {
            return -1;
        }
        return hit.mask;
    }

    public static UnitPath UnitPathForRawPath(
        ref UnitPath unit_path,
        UnityEngine.AI.NavMeshPath rawpath,
        ITimeline timeline,
        PathFindingTarget target_type,
        bool use_normal_as_up,
        ObjectId current_frame = default(ObjectId),
        PlatformAreaBase static_brother = null
    )
    {
        var path_points = rawpath.corners;
        NavMeshLinkSupervisor nav_mesh_link_supervisor = NavMeshLinkSupervisor.Instance;

        unit_path.Clear();

        if (path_points.Length == 0)
        {
            return unit_path;
        }

        var position_iterator = path_points[0];
        var finish_pos = path_points[path_points.Length - 1];

        // var start_hit = new UnityEngine.AI.NavMeshHit();
        // if (!UnityEngine.AI.NavMesh.SamplePosition(
        // 	path_points[0], out start_hit, SampleDistance, UnityEngine.AI.NavMesh.AllAreas))
        // {
        // 	return unit_path;
        // }
        // var start_area_mask = start_hit.mask;

        // Оптимизировать. Сейчас sample берётся дважды
        var start_position = PathFinding.NavMeshPoint(position_iterator, timeline, current_frame);
        //int previous_area_mask = start_area_mask;

        unit_path.InitFrame(current_frame);

        Arguments args = new Arguments();

        for (int i = 1; i < path_points.Length; i++)
        {
            var point = path_points[i];
            // var hit = new UnityEngine.AI.NavMeshHit();
            // if (!UnityEngine.AI.NavMesh.SamplePosition(point, out hit, SampleDistance, UnityEngine.AI.NavMesh.AllAreas))
            // {
            // 	return unit_path;
            // }
            var area_mask = NavMeshSampleMask(point);

            var nav_mesh_link =
                nav_mesh_link_supervisor != null
                    ? nav_mesh_link_supervisor.GetLinkByStartFinal2(position_iterator, point)
                    : null;

            args.nav_mesh_link = nav_mesh_link;
            args.point = point;
            args.timeline = timeline;
            args.unit_path = unit_path;
            args.use_normal_as_up = use_normal_as_up;

            if (nav_mesh_link != null)
            {
                switch (nav_mesh_link.area)
                {
                    case (int)Areas.DOOR_LINK_AREA:
                        UnitPathForRawPath_DOOR_LINK_AREA(ref args);
                        break;
                    case (int)Areas.UPSTAIRS_AREA:
                        UnitPathForRawPath_UPSTAIRS_LINK_AREA(ref args);
                        break;
                    case (int)Areas.WALLS_AREA:
                        UnitPathForRawPath_WALL_LINK_AREA(ref args);
                        break;
                    case (int)Areas.CLIMBING_LINK_AREA: // ClimbingLink
                        UnitPathForRawPath_CLIMBING_LINK_AREA(ref args);
                        break;
                    case (int)Areas.BRACED_UPDOWN_LINK_AREA: // ClimbingLink
                        UnitPathForRawPath_BRACED_LINK_AREA(ref args);
                        break;
                    case (int)Areas.SEW_LINK_AREA: // ClimbingLink
                        UnitPathForRawPath_SEW_LINK_AREA(ref args);
                        break;
                    default:
                        UnitPathForRawPath_UNKNOWN_LINK_AREA(ref args);
                        break;
                }
            }
            else
            {
                int area = NumberOfBitFromMask(area_mask);

                // if (
                // 	area_mask == Utility.ToMask(Areas.BURROW_ZONE_AREA)
                // 	&& previous_area_mask != Utility.ToMask(Areas.BURROW_ZONE_AREA)
                // )
                // {
                // 	UnitPathForRawPath_TO_BURROW_AREA_ZONE(
                // 		area_mask,
                // 		point,
                // 		timeline,
                // 		unit_path,
                // 		use_normal_as_up : use_normal_as_up,
                // 		nav_mesh_link_supervisor: nav_mesh_link_supervisor,
                // 		current_frame : current_frame);
                // }
                // else if (area_mask != Utility.ToMask(Areas.BURROW_ZONE_AREA)
                // 	&& previous_area_mask == Utility.ToMask(Areas.BURROW_ZONE_AREA)
                // )
                // {
                // 	UnitPathForRawPath_FROM_BURROW_AREA_ZONE(
                // 		area_mask,
                // 		point,
                // 		timeline,
                // 		unit_path,
                // 		use_normal_as_up: use_normal_as_up,
                // 		nav_mesh_link_supervisor: nav_mesh_link_supervisor,
                // 		current_frame: current_frame);
                // }

                // else if (area_mask == Utility.CLIMBING_AREA_MASK) // climbing
                // 	UnitPathForRawPath_CLIMBING_AREA_MASK(
                // 		nav_mesh_link, area_mask, point, timeline, unit_path, nav_mesh_link_supervisor);

                //else
                if (area == (int)Areas.STANDART_AREA) // standart
                    UnitPathForRawPath_STANDART_AREA_MASK(
                        point,
                        timeline,
                        unit_path,
                        use_normal_as_up: use_normal_as_up,
                        current_frame: current_frame
                    );
                else if (area == (int)Areas.WALKABLE_SHORT_AREA)
                    UnitPathForRawPath_STANDART_AREA_MASK(
                        point,
                        timeline,
                        unit_path,
                        use_normal_as_up: use_normal_as_up,
                        current_frame: current_frame
                    );
                else if (area == (int)Areas.WALLS_AREA)
                    UnitPathForRawPath_STANDART_AREA_MASK(
                        point,
                        timeline,
                        unit_path,
                        use_normal_as_up: use_normal_as_up,
                        current_frame: current_frame
                    );
                else if (area == (int)Areas.WALLS_FOR_ZERO_GRAVITY_AREA)
                    UnitPathForRawPath_WALLS_FOR_ZERO_GRAVITY_AREA_MASK(
                        point,
                        timeline,
                        unit_path,
                        use_normal_as_up: use_normal_as_up,
                        current_frame: current_frame
                    );
                else if (area == (int)Areas.BRACED_SURFACE_AREA)
                    UnitPathForRawPath_BRACED_AREA_MASK(
                        point,
                        timeline,
                        unit_path,
                        use_normal_as_up: use_normal_as_up,
                        current_frame: current_frame
                    );
                else if (area == (int)Areas.UPSTAIRS_AREA)
                    UnitPathForRawPath_UPSTAIRS_AREA_MASK(
                        point,
                        timeline,
                        unit_path,
                        use_normal_as_up: use_normal_as_up,
                        current_frame: current_frame
                    );
                else
                {
#if UNITY_64
                    Debug.Log("Unknown area mask: " + NumberOfBitFromMask(area_mask));
#endif
                    UnitPathForRawPath_STANDART_AREA_MASK(
                        point,
                        timeline,
                        unit_path,
                        use_normal_as_up: use_normal_as_up,
                        current_frame: current_frame
                    );
                }
            }
            position_iterator = point;
            //previous_area_mask = area_mask;
        }

        unit_path.SetStartPosition(start_position);

        return unit_path;
    }
}
