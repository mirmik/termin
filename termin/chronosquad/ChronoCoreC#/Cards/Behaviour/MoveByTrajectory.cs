using System.Collections;
using System.Collections.Generic;
using System;

#if UNITY_64
using UnityEngine;
#endif

[RequireComponent(typeof(PatrolPointCollection))]
public class MoveByTrajectory : MonoBehaviour
{
    //public MyList<GameObject> patrol_points = new MyList<GameObject>();
    ObjectController object_view;
    ObjectOfTimeline obj;
    PatrolPointCollection patrolPointCollection;

    MyList<Pose> poses = new MyList<Pose>();

    Pose start_pose;

    public float Speed = 3.0f;

    public bool Loop = false;

    bool inited = false;

    void Go(MyList<Pose> poses, bool looped)
    {
        int start_index = 0;
        if (looped)
        {
            start_index = -1;
        }
        long current_step = obj.LocalStep();
        for (int i = start_index; i < poses.Count - 1; i++)
        {
            Pose pose;
            if (i == -1)
                pose = poses[poses.Count - 1];
            else
                pose = poses[i];
            var next_pose = poses[i + 1];
            float distance = Vector3.Distance(pose.position, next_pose.position);
            float time = distance / Speed;
            long steps = (long)(time * Utility.GAME_GLOBAL_FREQUENCY);

            ReferencedPose ref_pose = ReferencedPose.FromGlobalPose(
                pose,
                default(ObjectId),
                obj.GetTimeline()
            );
            ReferencedPose ref_next_pose = ReferencedPose.FromGlobalPose(
                next_pose,
                default(ObjectId),
                obj.GetTimeline()
            );

            obj.AddPoseLerp(ref_pose, ref_next_pose, current_step, current_step + steps);
            current_step += steps;
        }
    }

    void Start()
    {
        patrolPointCollection = this.GetComponent<PatrolPointCollection>();
        object_view = this.GetComponent<ObjectController>();
        obj = object_view.GetObject();

        var patrol_points = patrolPointCollection.patrol_points;

        if (inited == false)
        {
            start_pose = obj.GlobalPose();
            Pose curpos = start_pose;
            poses.Add(curpos);
            foreach (var point in patrol_points)
            {
                if (point == null)
                    continue;

                var pose = new Pose(point.transform.position, point.transform.rotation);
                poses.Add(pose);
            }

            DoIt(false);
        }
    }

    void DoIt(bool looped)
    {
        Debug.Log("poses.Count = " + poses.Count);
        Go(poses, looped);
    }

    void Update()
    {
        if (Loop)
        {
            if (
                obj.CurrentAnimatronic() == null
                || obj.CurrentAnimatronic() is IdleAnimatronic
                || obj.LocalStep() > obj.CurrentAnimatronic().FinishStep
            )
            {
                DoIt(true);
            }
        }
    }
}
