// parallel raycasts using job system

using Unity.Collections;
using Unity.Jobs;
using UnityEngine;
using System;
using System.Collections;
using System.Collections.Generic;

struct Pair
{
    public ObjectOfTimeline actor;
    public ObjectOfTimeline target;

    public Pair(ObjectOfTimeline actor, ObjectOfTimeline target)
    {
        this.actor = actor;
        this.target = target;
    }
}

public class Raycaster
{
    public struct Indexes
    {
        public int i;
        public int j;

        public Indexes(int i, int j)
        {
            this.i = i;
            this.j = j;
        }
    }

    // static NativeArray<RaycastCommand> commands;
    // static NativeArray<RaycastHit> results;
    // static NativeArray<Indexes> indexes;
    static MyList<Pair> pairs;
    static int last_count = 0;

    static bool NeedRegenerateArrays(int newcount)
    {
        return pairs == null || last_count < newcount;
    }

    static void RegenerateArrays(int newcount)
    {
        pairs = new MyList<Pair>(newcount);
        last_count = newcount;
    }

    static void TestSightGPU(
        CanSee[,] matrix,
        MyList<ObjectOfTimeline> actors,
        MyList<ObjectOfTimeline> targets,
        Timeline timeline,
        bool allow_near_distance_sight,
        bool ignore_heights_rule = false
    )
    {
        var count = actors.Count * targets.Count;
        if (NeedRegenerateArrays(count))
        {
            RegenerateArrays(count);
        }

        NativeArray<RaycastCommand> commands = new NativeArray<RaycastCommand>(
            count,
            Allocator.TempJob
        );
        NativeArray<RaycastHit> results = new NativeArray<RaycastHit>(count, Allocator.TempJob);
        NativeArray<Indexes> indexes = new NativeArray<Indexes>(count, Allocator.TempJob);

        var layerMask =
            1 << (int)Layers.GROUND_LAYER
            | 1 << (int)Layers.OBSTACLES_LAYER
            | 1 << (int)Layers.DEFAULT_LAYER
            | 1 << (int)Layers.ACTOR_NON_TRANSPARENT_LAYER;

        int k = 0;
        float near_distance = 2.0f;
        for (int i = 0; i < actors.Count; i++)
        {
            var actor = actors[i];
            float fovangle = actor.SightAngle();
            float maxdistance = actor.SightDistance();
            var camera_pose = actor.CameraPose();
            for (int j = 0; j < targets.Count; j++)
            {
                var target = targets[j];
                if (target is Avatar)
                    continue;

                if (target.IsHide() || target.IsDisguise() || target.IsBurrowed())
                {
                    continue;
                }

                var target_position = target.TorsoPosition();

                var target_in_camera_frame = camera_pose.InverseTransformPoint(target_position);
                var diff = target_position - camera_pose.position;

                float vertical_distance = target_in_camera_frame.y; // < Здесь должна быть местная вертикаль
                bool difficult_to_observe = target.IsDifficultToObserve();

                if (!ignore_heights_rule && difficult_to_observe && vertical_distance > 0.1f)
                {
                    continue;
                }

                float distance = target_in_camera_frame.magnitude;
                if (distance > maxdistance)
                {
                    continue;
                }

                //var angle = camera_pose.AngleToDirectionByXZ(diff);
                var angle =
                    Mathf.Atan2(target_in_camera_frame.x, target_in_camera_frame.z) * Mathf.Rad2Deg;
                angle = Mathf.Abs(angle);
                if (
                    (angle > fovangle / 2)
                    && !(allow_near_distance_sight && distance < near_distance)
                )
                {
                    continue;
                }

                indexes[k] = new Indexes(actor._timeline_index, target._timeline_index);

                commands[k] = new RaycastCommand(
                    camera_pose.position,
                    diff / distance,
                    queryParameters: new QueryParameters(layerMask: layerMask),
                    distance: distance
                );
                pairs[k] = new Pair(actor, target);
                k++;
            }
        }

        NativeArray<RaycastCommand> commands_view = commands.GetSubArray(0, k);
        NativeArray<RaycastHit> results_view = results.GetSubArray(0, k);

        JobHandle handle = RaycastCommand.ScheduleBatch(commands_view, results_view, 1);
        handle.Complete();

        for (int l = 0; l < k; ++l)
        {
            var hit = results_view[l];
            int i = indexes[l].i;
            int j = indexes[l].j;
            var pair = pairs[l];
            bool can = hit.collider == null;
            var actor = pair.actor;
            var target = pair.target;

            if (can)
            {
                if (target.IsDifficultToObserve())
                {
                    matrix[i, j] = SecondPhaseView(actor, target);
                }
                else
                {
                    matrix[i, j] = CanSee.See;
                }
            }
            else
            {
                matrix[i, j] = CanSee.None;
            }
        }

        commands.Dispose();
        results.Dispose();
        indexes.Dispose();
    }

    static public void FillMatrix(Timeline tl, CanSee sts)
    {
        var matrix = tl.present.CanSeeMatrix();
        for (int i = 0; i < matrix.GetLength(0); i++)
        {
            for (int j = 0; j < matrix.GetLength(1); j++)
            {
                matrix[i, j] = sts;
            }
        }
    }

    static CanSee SecondPhaseView(ObjectOfTimeline actor, ObjectOfTimeline target)
    {
        var camera_pose = actor.CameraPose();
        var vertical_distance = target.TorsoPosition().y - camera_pose.position.y;
        var diff = (target.TorsoPosition() - camera_pose.position).normalized;
        RaycastHit hit;
        var distance = Vector3.Distance(target.TorsoPosition(), camera_pose.position);

        if (vertical_distance > 1.0f)
        {
            return CanSee.None;
        }

        if (
            Physics.Raycast(
                camera_pose.position,
                diff,
                out hit,
                distance,
                1 << (int)Layers.HALF_OBSTACLES_LAYER
            )
        )
        {
            return CanSee.None;
        }

        return CanSee.See;
    }

    static void RaycastCommand_ScheduleBatch_cpu(
        NativeArray<RaycastCommand> commands,
        NativeArray<RaycastHit> results,
        int numCommands
    )
    {
        for (int i = 0; i < numCommands; i++)
        {
            var command = commands[i];
            RaycastHit hit;
            if (
                Physics.Raycast(
                    command.from,
                    command.direction,
                    out hit,
                    command.distance,
                    command.queryParameters.layerMask
                )
            )
            {
                results[i] = hit;
            }
        }
    }

    static public void TestSightPhase(Timeline tl)
    {
        var can_see_matrix = tl.present.CanSeeMatrix();
        var actors = tl.Heroes();
        var enemies = tl.Enemies();
        var all_objects = tl.ObjectList();

        bool SafetySpace = false;
        if (!(ChronosphereController.instance is null))
            SafetySpace = ChronosphereController.instance.SafetySpace;

        NullifyMatrix(can_see_matrix);

        TestSightGPU(
            can_see_matrix,
            actors,
            enemies,
            tl,
            allow_near_distance_sight: true,
            ignore_heights_rule: true
        );

        if (!SafetySpace)
            TestSightGPU(can_see_matrix, enemies, actors, tl, allow_near_distance_sight: false);

        TestSightGPU(can_see_matrix, enemies, enemies, tl, allow_near_distance_sight: false);
    }

    static void NullifyMatrix(CanSee[,] matrix)
    {
        for (int i = 0; i < matrix.GetLength(0); i++)
        {
            for (int j = 0; j < matrix.GetLength(1); j++)
            {
                matrix[i, j] = CanSee.None;
            }
        }
    }

    static void TestSightCPU(
        CanSee[,] matrix,
        MyList<ObjectOfTimeline> actors,
        MyList<ObjectOfTimeline> targets,
        Timeline timeline,
        bool allow_near_distance_sight,
        bool ignore_heights_rule = false
    )
    {
        float absolute_distance = 2.0f;
        for (int i = 0; i < actors.Count; i++)
        {
            var actor = actors[i];
            var camera_pose = actor.CameraPose();
            float fovangle = actor.SightAngle();
            float maxdistance = actor.SightDistance();
            for (int j = 0; j < targets.Count; j++)
            {
                var target = targets[j];
                var target_position = target.TorsoPosition();
                var diff = target_position - camera_pose.position;

                float distance = diff.magnitude;
                if (distance > maxdistance)
                {
                    continue;
                }

                var angle = camera_pose.AngleToDirectionByXZ(diff);
                if (angle > fovangle / 2 && !(distance < absolute_distance))
                {
                    continue;
                }

                var can = IsCanSee1(actor, targets[j]);

                matrix[actor._timeline_index, targets[j]._timeline_index] = can
                    ? CanSee.See
                    : CanSee.None;
            }
        }
    }

    static public bool IsCanSee1(
        ObjectOfTimeline actor,
        ObjectOfTimeline target,
        float absolute_distance = 0.0f
    )
    {
#if UNITY_EDITOR
        var chronosphere_controller = ChronosphereController.instance;
        if (
            chronosphere_controller != null
            && chronosphere_controller.SafetySpace
            && target.IsHero()
        )
            return false;
#endif
        if (target.IsDisguise())
        {
            return false;
        }

        if (target.IsBurrowed())
        {
            return false;
        }

        return IsCanSee2(
            actor,
            target.TorsoPosition(),
            target.IsDifficultToObserve(),
            absolute_distance
        );
    }

    static public bool IsCanSee2(
        ObjectOfTimeline actor,
        Vector3 target_position,
        bool difficult_to_observe = false,
        float absolute_distance = 0.0f
    )
    {
        return IsCanSee3(
            actor.CameraPose(),
            target_position,
            actor.SightAngle(),
            actor.SightDistance(),
            difficult_to_observe,
            absolute_distance
        );
    }

    static bool IsCanSee3(
        Pose camera_pose,
        Vector3 target_position,
        float fovangle,
        float maxdistance,
        bool difficult_to_observe = false,
        float absolute_distance = 0.0f
    )
    {
        float vertical_distance = target_position.y - camera_pose.position.y;
        var diff = target_position - camera_pose.position;
        var diffSqr = diff.sqrMagnitude;
        if (diffSqr > maxdistance * maxdistance)
        {
            return false;
        }

        if (vertical_distance > 7.0f)
        {
            return false;
        }

        float distance = Mathf.Sqrt(diffSqr);

        var angle = camera_pose.AngleToDirectionByXZ(diff);
        if (angle > fovangle / 2 && !(distance < absolute_distance))
        {
            return false;
        }

        var layerMask =
            1 << (int)Layers.GROUND_LAYER
            | 1 << (int)Layers.OBSTACLES_LAYER
            | 1 << (int)Layers.DEFAULT_LAYER
            | 1 << (int)Layers.ACTOR_NON_TRANSPARENT_LAYER;

        RaycastHit hit;
        if (Physics.Raycast(camera_pose.position, diff, out hit, distance, layerMask))
        {
#if !UNITY_64
            return true;
#else
            return false;
#endif
        }

        if (difficult_to_observe)
        {
            if (vertical_distance > 1.0f)
            {
                return false;
            }

            if (
                Physics.Raycast(
                    camera_pose.position,
                    diff,
                    out hit,
                    distance,
                    1 << (int)Layers.HALF_OBSTACLES_LAYER
                )
            )
            {
                return false;
            }
        }

        return true;
    }
}
