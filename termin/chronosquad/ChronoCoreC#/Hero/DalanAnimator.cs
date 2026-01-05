using System.Collections;
using System.Collections.Generic;

#if UNITY_64
using UnityEngine;
#endif

public abstract class AbstractDalanAnimation : IAbstractAnimation
{
    public MyList<PoseLinked> _pose_links = new MyList<PoseLinked>();
    public MyList<PoseLinked> _left_arms_links = new MyList<PoseLinked>();
    public MyList<PoseLinked> _right_arms_links = new MyList<PoseLinked>();
    public MyList<PoseLinked> _left_arms_links_second = new MyList<PoseLinked>();
    public MyList<PoseLinked> _right_arms_links_second = new MyList<PoseLinked>();
    DalanAnimator animator;

    MyList<float> _spine_bones_length = new MyList<float>();
    MyList<float> _head_bones_length = new MyList<float>();

    public float BaseSpeed()
    {
        return 0.2f;
    }

    protected MyList<string> _spine_bones = new MyList<string>
    {
        "Armature/Bone.002",
        "Armature/Bone.002/Bone.003",
        "Armature/Bone.002/Bone.003/Bone.004",
        "Armature/Bone.002/Bone.003/Bone.004/Bone.005",
        "Armature/Bone.002/Bone.003/Bone.004/Bone.005/Bone.006",
        "Armature/Bone.002/Bone.003/Bone.004/Bone.005/Bone.006/Bone.007",
        "Armature/Bone.002/Bone.003/Bone.004/Bone.005/Bone.006/Bone.007/Bone.008",
        "Armature/Bone.002/Bone.003/Bone.004/Bone.005/Bone.006/Bone.007/Bone.008/Bone.009",
        "Armature/Bone.002/Bone.003/Bone.004/Bone.005/Bone.006/Bone.007/Bone.008/Bone.009/Bone.010",
        "Armature/Bone.002/Bone.003/Bone.004/Bone.005/Bone.006/Bone.007/Bone.008/Bone.009/Bone.010/Bone.011",
        "Armature/Bone.002/Bone.003/Bone.004/Bone.005/Bone.006/Bone.007/Bone.008/Bone.009/Bone.010/Bone.011/Bone.012",
        "Armature/Bone.002/Bone.003/Bone.004/Bone.005/Bone.006/Bone.007/Bone.008/Bone.009/Bone.010/Bone.011/Bone.012/Bone.013",
        "Armature/Bone.002/Bone.003/Bone.004/Bone.005/Bone.006/Bone.007/Bone.008/Bone.009/Bone.010/Bone.011/Bone.012/Bone.013/Bone.014",
        "Armature/Bone.002/Bone.003/Bone.004/Bone.005/Bone.006/Bone.007/Bone.008/Bone.009/Bone.010/Bone.011/Bone.012/Bone.013/Bone.014/Bone.015",
        "Armature/Bone.002/Bone.003/Bone.004/Bone.005/Bone.006/Bone.007/Bone.008/Bone.009/Bone.010/Bone.011/Bone.012/Bone.013/Bone.014/Bone.015/Bone.016",
    };

    protected MyList<string> _left_arms = new MyList<string>
    {
        "Armature/Bone.002/Bone.L1",
        "Armature/Bone.002/Bone.003/Bone.004/Bone.L2",
        "Armature/Bone.002/Bone.003/Bone.004/Bone.005/Bone.006/Bone.L3",
        "Armature/Bone.002/Bone.003/Bone.004/Bone.005/Bone.006/Bone.007/Bone.008/Bone.L4",
        "Armature/Bone.002/Bone.003/Bone.004/Bone.005/Bone.006/Bone.007/Bone.008/Bone.009/Bone.010/Bone.L5",
        "Armature/Bone.002/Bone.003/Bone.004/Bone.005/Bone.006/Bone.007/Bone.008/Bone.009/Bone.010/Bone.011/Bone.012/Bone.L6",
    };

    protected MyList<string> _right_arms = new MyList<string>
    {
        "Armature/Bone.002/Bone.R1",
        "Armature/Bone.002/Bone.003/Bone.004/Bone.R2",
        "Armature/Bone.002/Bone.003/Bone.004/Bone.005/Bone.006/Bone.R3",
        "Armature/Bone.002/Bone.003/Bone.004/Bone.005/Bone.006/Bone.007/Bone.008/Bone.R4",
        "Armature/Bone.002/Bone.003/Bone.004/Bone.005/Bone.006/Bone.007/Bone.008/Bone.009/Bone.010/Bone.R5",
        "Armature/Bone.002/Bone.003/Bone.004/Bone.005/Bone.006/Bone.007/Bone.008/Bone.009/Bone.010/Bone.011/Bone.012/Bone.R6",
    };

    protected MyList<string> _left_arms_second = new MyList<string>
    {
        "Armature/Bone.002/Bone.L1/Bone.LL1",
        "Armature/Bone.002/Bone.003/Bone.004/Bone.L2/Bone.LL2",
        "Armature/Bone.002/Bone.003/Bone.004/Bone.005/Bone.006/Bone.L3/Bone.LL3",
        "Armature/Bone.002/Bone.003/Bone.004/Bone.005/Bone.006/Bone.007/Bone.008/Bone.L4/Bone.LL4",
        "Armature/Bone.002/Bone.003/Bone.004/Bone.005/Bone.006/Bone.007/Bone.008/Bone.009/Bone.010/Bone.L5/Bone.LL5",
        "Armature/Bone.002/Bone.003/Bone.004/Bone.005/Bone.006/Bone.007/Bone.008/Bone.009/Bone.010/Bone.011/Bone.012/Bone.L6/Bone.LL6",
    };

    protected MyList<string> _right_arms_second = new MyList<string>
    {
        "Armature/Bone.002/Bone.R1/Bone.RR1",
        "Armature/Bone.002/Bone.003/Bone.004/Bone.R2/Bone.RR2",
        "Armature/Bone.002/Bone.003/Bone.004/Bone.005/Bone.006/Bone.R3/Bone.RR3",
        "Armature/Bone.002/Bone.003/Bone.004/Bone.005/Bone.006/Bone.007/Bone.008/Bone.R4/Bone.RR4",
        "Armature/Bone.002/Bone.003/Bone.004/Bone.005/Bone.006/Bone.007/Bone.008/Bone.009/Bone.010/Bone.R5/Bone.RR5",
        "Armature/Bone.002/Bone.003/Bone.004/Bone.005/Bone.006/Bone.007/Bone.008/Bone.009/Bone.010/Bone.011/Bone.012/Bone.R6/Bone.RR6",
    };

    protected MyList<string> _head_bones = new MyList<string>
    {
        "Armature/Bone",
        "Armature/Bone/Bone.001",
    };

    public abstract AnimationValues ValuesArray(
        float time,
        bool loop,
        Animatronic animatronic,
        float animation_booster
    );

    void MakeSpineLinkedPose()
    {
        PoseLinked prev_link = null;
        float lengt_accum = 0;
        for (int i = 0; i < _spine_bones.Count; i++)
        {
            Pose pose = new Pose();
            pose.position = new Vector3(0, lengt_accum, 0);
            pose.rotation = Quaternion.Euler(0, 0, 0);
            PoseLinked link = new PoseLinked(pose, prev_link);
            _pose_links.Add(link);
            prev_link = link;
            _spine_bones_length.Add(0.1f);
            lengt_accum += 0.1f;
        }
    }

    void MakeArmLinkedPose()
    {
        for (int i = 0; i < 6; i++)
        {
            Pose pose = new Pose();
            pose.position = new Vector3(0, 0, 0);
            pose.rotation = Quaternion.Euler(0, 0, 0);
            PoseLinked left_link = new PoseLinked(pose, _pose_links[i * 2]);
            _left_arms_links.Add(left_link);
            PoseLinked right_link = new PoseLinked(pose, _pose_links[i * 2]);
            _right_arms_links.Add(right_link);

            PoseLinked left_link_second = new PoseLinked(pose, _left_arms_links[i]);
            _left_arms_links_second.Add(left_link_second);
            PoseLinked right_link_second = new PoseLinked(pose, _right_arms_links[i]);
            _right_arms_links_second.Add(right_link_second);
        }
    }

    void MakeHeadLinkedPose()
    {
        PoseLinked prev_link = null;
        float lengt_accum = 0;
        for (int i = 0; i < _head_bones.Count; i++)
        {
            Pose pose = new Pose();
            pose.position = new Vector3(0, lengt_accum, 0);
            pose.rotation = Quaternion.Euler(0, 0, 0);
            PoseLinked link = new PoseLinked(pose, prev_link);
            _pose_links.Add(link);
            prev_link = link;
            _head_bones_length.Add(0.1f);
            lengt_accum += 0.1f;
        }
    }

    public AbstractDalanAnimation(DalanAnimator animator)
    {
        MakeSpineLinkedPose();
        MakeHeadLinkedPose();
        MakeArmLinkedPose();

        this.animator = animator;
        foreach (var bone in _spine_bones)
        {
            _spine_bones_length.Add(0.1f);
        }
    }
}

public class PoseLinked
{
    Pose _local_pose;
    Pose _global_pose;
    PoseLinked _parent;

    public PoseLinked(Pose pose, PoseLinked parent)
    {
        _local_pose = pose;
        _parent = parent;
        UpdateGlobalPoseByLocal();
    }

    public void UpdateGlobalPoseByLocal()
    {
        if (_parent != null)
        {
            _global_pose = _parent.GlobalPose() * _local_pose;
        }
        else
        {
            _global_pose = _local_pose;
        }
    }

    public void UpdateLocalByGlobal()
    {
        if (_parent != null)
        {
            _local_pose = _parent.GlobalPose().Inverse() * _global_pose;
        }
        else
        {
            _local_pose = _global_pose;
        }
    }

    public void SetGlobalPose(Pose pose)
    {
        _global_pose = pose;
        UpdateLocalByGlobal();
    }

    public void SetLocalPose(Pose pose)
    {
        _local_pose = pose;
        UpdateGlobalPoseByLocal();
    }

    public Pose GlobalPose()
    {
        return _global_pose;
    }

    public Pose LocalPose()
    {
        return _local_pose;
    }

    public PoseLinked Parent
    {
        get { return _parent; }
    }
}

public class DalanIdleAnimation : AbstractDalanAnimation
{
    public DalanIdleAnimation(DalanAnimator animator) : base(animator) { }

    public override AnimationValues ValuesArray(
        float time,
        bool loop,
        Animatronic animatronic,
        float animation_booster
    )
    {
        Dictionary<string, AnimationChannelData> animationData =
            new Dictionary<string, AnimationChannelData>();
        return new AnimationValues(animationData);
    }
}

public class DalanWalkAnimation : AbstractDalanAnimation
{
    float _scale = 100.0f;

    float walk_speed = 0.2f;

    public DalanWalkAnimation(DalanAnimator animator, float speed) : base(animator)
    {
        walk_speed = speed;
    }

    public override AnimationValues ValuesArray(
        float time,
        bool loop,
        Animatronic priv_animatronic,
        float animation_booster
    )
    {
        MovingAnimatronic movingAnimatronic = (MovingAnimatronic)priv_animatronic;
        Dictionary<string, AnimationChannelData> animationData =
            new Dictionary<string, AnimationChannelData>();

        AnimationChannelData channelData2 = new AnimationChannelData();
        channelData2.position = new Vector3(0, 0, 0);
        channelData2.rotation = Quaternion.Euler(-90, 180, 0);
        animationData["Armature"] = channelData2;

        float lengt_accum = 0;
        float freq = walk_speed * Mathf.PI * 2;
        float start_phase = Mathf.PI / 2;
        float amplitude = 0.6f;
        //float wave_factor = 0.3f;
        float lengt_accum_inc = 0.7f;
        for (int i = 0; i < _spine_bones.Count; ++i)
        {
            AnimationChannelData channelData = new AnimationChannelData();
            float phase = lengt_accum - time * freq + start_phase;
            var off = Mathf.Sin(phase) * amplitude / _scale;
            float angle = Mathf.Atan(Mathf.Cos(phase)) / Mathf.PI * 180.0f;

            var position = new Vector3(off, -lengt_accum / _scale, 0);
            var rotation = Quaternion.Euler(0, 0, 0);
            //if (lengt_accum == 0)
            //{
            rotation = Quaternion.Euler(0, 0, angle) * Quaternion.Euler(0, 0, 180);
            //}
            _pose_links[i].SetGlobalPose(new Pose(position, rotation));
            var local_pose = _pose_links[i].LocalPose();

            channelData.position = local_pose.position;
            channelData.rotation = local_pose.rotation;

            animationData[_spine_bones[i]] = channelData;
            lengt_accum += lengt_accum_inc;
        }

        float head_lengt_accum = 0;
        for (int i = 0; i < _head_bones.Count; ++i)
        {
            AnimationChannelData channelData = new AnimationChannelData();
            var off = Mathf.Sin(lengt_accum - time * freq + start_phase) * amplitude / _scale;

            var position = new Vector3(-off, head_lengt_accum / _scale, 0.5f / _scale);
            var rotation = Quaternion.Euler(0, 0, 0);
            rotation = Quaternion.Euler(0, 0, 0);
            _pose_links[i].SetGlobalPose(new Pose(position, rotation));
            var local_pose = _pose_links[i].LocalPose();

            channelData.position = local_pose.position;
            channelData.rotation = local_pose.rotation;

            animationData[_head_bones[i]] = channelData;
            head_lengt_accum += 1.0f;
        }

        float lengt_accum_2 = 0;
        float start_phase2 = (-Mathf.PI / 3 - Mathf.PI / 4) / 2;
        float start_phase3 = (-Mathf.PI / 3 - Mathf.PI / 4) / 2 / 3;
        for (int i = 0; i < _left_arms_links.Count; ++i)
        {
            float phase_p = lengt_accum_2 - time * freq + start_phase + start_phase2;
            float phase_pp = lengt_accum_2 - 2.0f * time * freq + start_phase + start_phase2;
            float angle_p = -Mathf.Atan(Mathf.Cos(phase_p)) / Mathf.PI * 180.0f;
            float angle_pp = 0.0f * -Mathf.Atan(Mathf.Cos(phase_pp)) / Mathf.PI * 180.0f;
            float phase = lengt_accum_2 - time * freq + start_phase + start_phase3;
            float angle = -Mathf.Atan(Mathf.Cos(phase)) / Mathf.PI * 180.0f;
            AnimationChannelData channelData_l = new AnimationChannelData();
            AnimationChannelData channelData_r = new AnimationChannelData();

            var f = angle_p * 0.6f;
            var f1 = f > 0 ? f : 0;
            var f2 = f < 0 ? f : 0;

            var AN = 80.0f;
            var rotation_l =
                Quaternion.Euler(0, 0, AN + angle_p + angle_pp) * Quaternion.Euler(-f2, 0, 0);
            var rotation_r =
                Quaternion.Euler(0, 0, -AN + angle_p + angle_pp) * Quaternion.Euler(f1, 0, 0);
            var position = new Vector3(0, 0.00754f, 0);

            if (i == 0)
            {
                rotation_l = Quaternion.Euler(35.0f, 0, 60.0f + angle);
                rotation_r = Quaternion.Euler(35.0f, 0, -60.0f + angle);
                position = new Vector3(0, 0.00354f, 0);
            }

            channelData_l.position = position;
            channelData_l.rotation = rotation_l;
            channelData_r.position = position;
            channelData_r.rotation = rotation_r;

            animationData[_left_arms[i]] = channelData_l;
            animationData[_right_arms[i]] = channelData_r;
            lengt_accum_2 += lengt_accum_inc * 2;
        }

        return new AnimationValues(animationData);
    }
}

public class DalanAnimator : AnimateController
{
    public DalanWalkAnimation _DalanWalkAnimation;
    public DalanWalkAnimation _DalanRunAnimation;
    public DalanIdleAnimation _DalanIdleAnimation;

    void Awake()
    {
        var gutard_view = GetComponent<GuardView>();
        _DalanWalkAnimation = new DalanWalkAnimation(this, gutard_view.WalkSpeed);
        _DalanRunAnimation = new DalanWalkAnimation(this, gutard_view.RunSpeed);
        _DalanIdleAnimation = new DalanIdleAnimation(this);
    }

    public override IAbstractAnimation GetAnimation(AnimationType type)
    {
        if (AnimationType.Walk == type)
        {
            return _DalanWalkAnimation;
        }
        else if (AnimationType.Run == type)
        {
            return _DalanRunAnimation;
        }
        else if (AnimationType.Idle == type)
        {
            return _DalanIdleAnimation;
        }

        return base.GetAnimation(type);
    }
}
