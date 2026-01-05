using System.Collections;
using System.Collections.Generic;
using System;

#if UNITY_64
using UnityEngine;
#endif

public struct AnimationValues
{
    public MyList<AnimationChannelData> array_values;
    public Dictionary<string, AnimationChannelData> dict_values;

    public AnimationValues(MyList<AnimationChannelData> values)
    {
        array_values = values;
        dict_values = null;
    }

    public AnimationValues(Dictionary<string, AnimationChannelData> values)
    {
        dict_values = values;
        array_values = null;
    }

    public bool IsNull()
    {
        if (array_values == null && dict_values == null)
            return true;

        if (array_values != null && array_values.Count == 0)
            return true;

        if (dict_values != null && dict_values.Count == 0)
            return true;

        return false;
    }

    public int Length
    {
        get
        {
            if (array_values != null)
                return array_values.Count;
            else if (dict_values != null)
                return dict_values.Count;
            else
                return 0;
        }
    }
}

public struct AnimationChannelData
{
    public Vector3 position;
    public Quaternion rotation;

    public AnimationChannelData(Vector3 position, Quaternion rotation)
    {
        this.position = position;
        this.rotation = rotation;
    }
}

public class SimplifiedCurve
{
    const float delta = Utility.ANIMATION_DELTA;
    public float[] values;

    public SimplifiedCurve(AnimationCurve curve, float duration)
    {
        values = new float[(int)(duration / delta)];
        for (int i = 0; i < values.Length; i++)
        {
            values[i] = curve.Evaluate(i * delta);
        }
    }

    public float Evaluate(float time)
    {
        int index = (int)(time / delta);
        if (index >= values.Length)
            index = values.Length - 1;

        var value1 = values[index];
        if (index == values.Length - 1)
            return value1;

        var value2 = values[index + 1];

        var coeff = (time - index * delta) / delta;
        return value1 * (1 - coeff) + value2 * coeff;
    }

    public float Evaluate(int index, float coeff)
    {
        var value1 = values[index];
        // if (index == values.Length - 1)
        // 	return value1;

        var value2 = values[index + 1];
        return value1 + (value2 - value1) * coeff;
    }
}

public class AnimationChannel
{
    const float delta = Utility.ANIMATION_DELTA;
    public AnimationClip clip;
    public SimplifiedCurve curve_position_x;
    public SimplifiedCurve curve_position_y;
    public SimplifiedCurve curve_position_z;
    public SimplifiedCurve curve_rotation_x;
    public SimplifiedCurve curve_rotation_y;
    public SimplifiedCurve curve_rotation_z;
    public SimplifiedCurve curve_rotation_w;
    public string path;
    public long hash;
    public bool valid = false;

    public AnimationChannel(AnimationClip clip, string path, AnimationCurveManager manager)
    {
        this.path = path;
        this.clip = clip;
        this.hash = RigController.StringToHash(path);
        GetCurves(manager);
    }

    public int IndexLength()
    {
        return curve_position_x.values.Length;
    }

    void GetCurves(AnimationCurveManager manager)
    {
        float duration = clip.length;
        if (manager.HasCurve(clip, path, "m_LocalPosition.x"))
        {
            curve_position_x = new SimplifiedCurve(
                manager.GetCurve(clip, path, "m_LocalPosition.x"),
                duration
            );
            curve_position_y = new SimplifiedCurve(
                manager.GetCurve(clip, path, "m_LocalPosition.y"),
                duration
            );
            curve_position_z = new SimplifiedCurve(
                manager.GetCurve(clip, path, "m_LocalPosition.z"),
                duration
            );
            curve_rotation_x = new SimplifiedCurve(
                manager.GetCurve(clip, path, "m_LocalRotation.x"),
                duration
            );
            curve_rotation_y = new SimplifiedCurve(
                manager.GetCurve(clip, path, "m_LocalRotation.y"),
                duration
            );
            curve_rotation_z = new SimplifiedCurve(
                manager.GetCurve(clip, path, "m_LocalRotation.z"),
                duration
            );
            curve_rotation_w = new SimplifiedCurve(
                manager.GetCurve(clip, path, "m_LocalRotation.w"),
                duration
            );
            valid = true;
        }
    }

    public float Duration()
    {
        return clip.length;
    }

    public AnimationChannelData Evaluate(float time)
    {
        if (!valid)
            return new AnimationChannelData(Vector3.zero, Quaternion.identity);

        var index = (int)(time / delta);
        var coeff = (time - index * delta) / delta;

        if (index >= curve_position_x.values.Length - 1)
        {
            index = curve_position_x.values.Length - 1;
            return new AnimationChannelData(
                new Vector3(
                    curve_position_x.values[index],
                    curve_position_y.values[index],
                    curve_position_z.values[index]
                ),
                new Quaternion(
                    curve_rotation_x.values[index],
                    curve_rotation_y.values[index],
                    curve_rotation_z.values[index],
                    curve_rotation_w.values[index]
                )
            );
        }
        else if (index < 0)
            return new AnimationChannelData(
                new Vector3(
                    curve_position_x.values[0],
                    curve_position_y.values[0],
                    curve_position_z.values[0]
                ),
                new Quaternion(
                    curve_rotation_x.values[0],
                    curve_rotation_y.values[0],
                    curve_rotation_z.values[0],
                    curve_rotation_w.values[0]
                )
            );

        Vector3 position = new Vector3(
            curve_position_x.Evaluate(index, coeff),
            curve_position_y.Evaluate(index, coeff),
            curve_position_z.Evaluate(index, coeff)
        );
        Quaternion rotation = new Quaternion(
            curve_rotation_x.Evaluate(index, coeff),
            curve_rotation_y.Evaluate(index, coeff),
            curve_rotation_z.Evaluate(index, coeff),
            curve_rotation_w.Evaluate(index, coeff)
        );
        return new AnimationChannelData(position, rotation);
    }

    public void NullifyPosition()
    {
        if (!valid)
            return;
        for (int i = 0; i < curve_position_x.values.Length; i++)
        {
            //curve_position_x.values[i] = 0;
            // curve_position_y.values[i] = 0.1f;
            //curve_position_z.values[i] = 0;
        }
    }
}

public interface IAbstractAnimation
{
    AnimationValues ValuesArray(
        float time,
        bool loop,
        Animatronic animatronic,
        float animation_booster
    );
    float BaseSpeed();
}

public class MyAnimation : IAbstractAnimation
{
    const float delta = Utility.ANIMATION_DELTA;
    AnimationChannel[] animate_channels;
    AnimationCurveManager animation_curve_manager;
    AnimationClip clip;
    float duration;
    long duration_in_steps;
    RigController rig_controller;
    SpeedOverdrive overdrive = default(SpeedOverdrive);

    float[] optimized_storage;

    AnimationCurve GetCurve(string path, string property, float time)
    {
        return animation_curve_manager.GetCurve(clip, path, property);
    }

    public MyAnimation(
        MyList<string> pathes,
        Dictionary<long, int> hash_to_index_map,
        AnimationCurveManager animmanager,
        AnimationClip clip,
        SpeedOverdrive overdrive,
        //string unical_name,
        //string animation_name,
        RigController rig_controller = null
    )
    {
        this.overdrive = overdrive;
        this.rig_controller = rig_controller;
        animation_curve_manager = animmanager;
        this.clip = clip;

        MyList<AnimationChannel> nonsorted_animate_channels = new MyList<AnimationChannel>();
        foreach (string path in pathes)
        {
            if (rig_controller.IsInFilter(path))
                continue;
            AnimationChannel channel = new AnimationChannel(clip, path, animation_curve_manager);
            nonsorted_animate_channels.Add(channel);
        }
        duration = clip.length;
        duration_in_steps = (long)(duration * Utility.GAME_GLOBAL_FREQUENCY);

        animate_channels = new AnimationChannel[hash_to_index_map.Count];
        foreach (AnimationChannel channel in nonsorted_animate_channels)
        {
            int index = hash_to_index_map[channel.hash];
            animate_channels[index] = channel;
        }

        MakeOptimized();
    }

    void MakeOptimized()
    {
        int idxlen = animate_channels[0].IndexLength();
        optimized_storage = new float[animate_channels.Length * 7 * idxlen];

        int frame_size = animate_channels.Length * 7;

        for (int i = 0; i < idxlen; i++)
        {
            for (int j = 0; j < animate_channels.Length; j++)
            {
                int it = i * frame_size + j * 7;

                if (animate_channels[j].valid == false)
                    continue;

                optimized_storage[it] = animate_channels[j].curve_position_x.values[i];
                optimized_storage[it + 1] = animate_channels[j].curve_position_y.values[i];
                optimized_storage[it + 2] = animate_channels[j].curve_position_z.values[i];
                optimized_storage[it + 3] = animate_channels[j].curve_rotation_x.values[i];
                optimized_storage[it + 4] = animate_channels[j].curve_rotation_y.values[i];
                optimized_storage[it + 5] = animate_channels[j].curve_rotation_z.values[i];
                optimized_storage[it + 6] = animate_channels[j].curve_rotation_w.values[i];
            }
        }
    }

    public float Duration()
    {
        return duration;
    }

    // public AnimationValues ValuesArray(float time, bool loop, Animatronic animatronic)
    // {
    // 	bool is_animation_boosted =
    // 		animatronic is MovingAnimatronic || animatronic is DeathAnimatronic;

    // 	float booster = is_animation_boosted ? GameCore.AnimationBooster() : 1.0f;
    // 	time = time / booster;

    // 	while(time < 0) time += duration;

    // 	var time_normalized = time / duration;
    // 	int cycle = (int)time_normalized;

    // 	float loctime;
    // 	if (loop)
    // 		loctime = time - cycle * duration;
    // 	else
    // 		loctime = Mathf.Min(time, duration);

    // 	AnimationChannelData[] values = new AnimationChannelData[animate_channels.Length];
    // 	for (int i = 0; i < animate_channels.Length; i++)
    // 	{
    // 		AnimationChannel channel = animate_channels[i];
    // 		AnimationChannelData data = channel.Evaluate(loctime);
    // 		values[i] = data;
    // 	}
    // 	return new AnimationValues(values);
    // }

    public float BaseSpeed()
    {
        return overdrive.speed;
    }

    public AnimationValues ValuesArray(
        float time,
        bool loop,
        Animatronic animatronic,
        float animation_booster
    )
    {
        //bool is_animation_boosted =
        //	animatronic is MovingAnimatronic || animatronic is DeathAnimatronic;

        //float booster = is_animation_boosted ? GameCore.AnimationBooster() : 1.0f;
        time = time / animation_booster * overdrive.overdrive;

        while (time < 0)
            time += duration;

        var time_normalized = time / duration;
        int cycle = (int)time_normalized;

        float loctime;
        if (loop)
            loctime = time - cycle * duration;
        else
            loctime = Mathf.Min(time, duration);

        var index = (int)(loctime / delta);
        var coeff = (loctime - index * delta) / delta;

        if (index >= animate_channels[0].IndexLength() - 1)
            return LastFrame();
        else if (index < 0)
            return FirstFrame();
        else
            return LerpFrames(index, coeff);
    }

    MyList<AnimationChannelData> values = new MyList<AnimationChannelData>();

    AnimationValues FirstFrame()
    {
        values.ReSize(animate_channels.Length);
        for (int i = 0; i < animate_channels.Length; i++)
        {
            int bidx = i * 7;
            AnimationChannelData data = new AnimationChannelData(
                new Vector3(
                    optimized_storage[bidx],
                    optimized_storage[bidx + 1],
                    optimized_storage[bidx + 2]
                ),
                new Quaternion(
                    optimized_storage[bidx + 3],
                    optimized_storage[bidx + 4],
                    optimized_storage[bidx + 5],
                    optimized_storage[bidx + 6]
                )
            );
            values[i] = data;
        }
        return new AnimationValues(values);
    }

    AnimationValues LastFrame()
    {
        values.ReSize(animate_channels.Length);
        int last = animate_channels[0].IndexLength() - 1;
        int bbidx = animate_channels.Length * 7 * last;
        for (int i = 0; i < animate_channels.Length; i++)
        {
            int bidx = bbidx + i * 7;
            AnimationChannelData data = new AnimationChannelData(
                new Vector3(
                    optimized_storage[bidx],
                    optimized_storage[bidx + 1],
                    optimized_storage[bidx + 2]
                ),
                new Quaternion(
                    optimized_storage[bidx + 3],
                    optimized_storage[bidx + 4],
                    optimized_storage[bidx + 5],
                    optimized_storage[bidx + 6]
                )
            );
            values[i] = data;
        }
        return new AnimationValues(values);
    }

    AnimationValues LerpFrames(int index, float coeff)
    {
        values.ReSize(animate_channels.Length);
        int bbidx = animate_channels.Length * 7 * index;
        for (int i = 0; i < animate_channels.Length; i++)
        {
            int bidx1 = bbidx + i * 7;
            int bidx2 = bbidx + animate_channels.Length * 7 + i * 7;

            float k1 = 1 - coeff;
            float k2 = coeff;

            AnimationChannelData data = new AnimationChannelData(
                new Vector3(
                    optimized_storage[bidx1] * k1 + optimized_storage[bidx2] * k2,
                    optimized_storage[bidx1 + 1] * k1 + optimized_storage[bidx2 + 1] * k2,
                    optimized_storage[bidx1 + 2] * k1 + optimized_storage[bidx2 + 2] * k2
                ),
                new Quaternion(
                    optimized_storage[bidx1 + 3] * k1 + optimized_storage[bidx2 + 3] * k2,
                    optimized_storage[bidx1 + 4] * k1 + optimized_storage[bidx2 + 4] * k2,
                    optimized_storage[bidx1 + 5] * k1 + optimized_storage[bidx2 + 5] * k2,
                    optimized_storage[bidx1 + 6] * k1 + optimized_storage[bidx2 + 6] * k2
                )
            );
            values[i] = data;
        }
        return new AnimationValues(values);
    }

    public AnimationValues FinalState(Animatronic animatronic)
    {
        return ValuesArray(Duration(), false, animatronic, 1.0f);
    }
}

public struct SpeedStruct
{
    public float walk_speed;
    public float run_speed;
    public float crouch_speed;
    public float zero_gravity_walk_speed;
    public float low_gravity_walk_speed;
    public float low_gravity_run_speed;
    public float zero_gravity_crawl_speed;

    public SpeedStruct(bool stub)
    {
        walk_speed = 1.0f;
        run_speed = 2.0f;
        crouch_speed = 1.0f;
        zero_gravity_walk_speed = 1.0f;
        low_gravity_walk_speed = 1.0f;
        low_gravity_run_speed = 1.0f;
        zero_gravity_crawl_speed = 1.0f;
    }
}

[RequireComponent(typeof(ObjectController))]
public class AnimateController : MonoBehaviour
{
    public float MoveAnimationSpeed = 1.0f;
    public float IdleAnimationSpeed = 1.0f;

    public string AnimationKeepsName;
    bool _cached_fog_of_war = false;

    ObjectController _object_controller;
    GameObject _model_object;
    RigController _rig_controller;
    AnimationCurveManager animation_curve_manager;
    ChronoSphere _chronosphere;

    static Dictionary<string, Dictionary<AnimationType, MyAnimation>> animations_by_unical_name =
        new Dictionary<string, Dictionary<AnimationType, MyAnimation>>();

    Dictionary<AnimationType, MyAnimation> my_animations =
        new Dictionary<AnimationType, MyAnimation>();

    Dictionary<string, MyAnimation> my_animations_by_name = new Dictionary<string, MyAnimation>();

    bool _animation_loaded = false;
    bool _model_animation_control = true;

    public SpeedStruct GetSpeedStructFromAnimations()
    {
        LoadAnimations();

        var walk_speed_anim = GetAnimation(AnimationType.Walk);
        var run_speed_anim = GetAnimation(AnimationType.Run);
        var crouch_speed_anim = GetAnimation(AnimationType.CroachWalk);
        var zero_gravity_walk_speed_anim = GetAnimation(AnimationType.ZeroGravityWalk);
        var low_gravity_walk_speed_anim = GetAnimation(AnimationType.LowGravityWalk);
        var zero_gravity_crawl_speed_anim = GetAnimation(AnimationType.ZeroGravityCrawl);
        var low_gravity_run_speed_anim = GetAnimation(AnimationType.LowGravityRun);

        float walk_speed = walk_speed_anim != null ? walk_speed_anim.BaseSpeed() : 1.0f;
        float run_speed = run_speed_anim != null ? run_speed_anim.BaseSpeed() : 1.0f;
        float crouch_speed = crouch_speed_anim != null ? crouch_speed_anim.BaseSpeed() : 1.0f;
        float zero_gravity_walk_speed =
            zero_gravity_walk_speed_anim != null ? zero_gravity_walk_speed_anim.BaseSpeed() : 1.0f;
        float low_gravity_walk_speed =
            low_gravity_walk_speed_anim != null ? low_gravity_walk_speed_anim.BaseSpeed() : 1.0f;
        float zero_gravity_crawl_speed =
            zero_gravity_crawl_speed_anim != null
                ? zero_gravity_crawl_speed_anim.BaseSpeed()
                : 1.0f;
        float low_gravity_run_speed =
            low_gravity_run_speed_anim != null ? low_gravity_run_speed_anim.BaseSpeed() : 1.0f;

        return new SpeedStruct
        {
            walk_speed = walk_speed,
            run_speed = run_speed,
            crouch_speed = crouch_speed,
            zero_gravity_walk_speed = zero_gravity_walk_speed,
            low_gravity_walk_speed = low_gravity_walk_speed,
            zero_gravity_crawl_speed = zero_gravity_crawl_speed,
            low_gravity_run_speed = low_gravity_run_speed
        };
    }

    void Awake()
    {
        _object_controller = GetComponent<ObjectController>();
        _model_object = this.transform.Find("Model").gameObject;
        _rig_controller = GetComponent<RigController>();
        LoadAnimations();
    }

    void Start()
    {
        _chronosphere = GameCore.Chronosphere();
        _cached_fog_of_war = GameCore.GetChronosphereController().FogOfWar;
        ChronosphereController.instance.FogOfWarChanged += SetFogOfWar;
    }

    public void SetFogOfWar(bool value)
    {
        _cached_fog_of_war = value;
    }

    public void SetAnimationsFromOtherObject(AnimateController other)
    {
        my_animations = other.my_animations;
        _animation_loaded = true;
    }

    public MyAnimation GetAnimation(string name)
    {
        if (my_animations_by_name.ContainsKey(name))
        {
            return my_animations_by_name[name];
        }
        return null;
    }

    void LoadAnimations()
    {
        if (_animation_loaded)
            return;

        _rig_controller = GetComponent<RigController>();
        var animation_keeper_obj = GameObject.Find("AnimationKeeper");
        AnimationKeeper keeper = animation_keeper_obj.GetComponent<AnimationKeeper>();
        animation_curve_manager = keeper.GetManager(AnimationKeepsName);
        animation_curve_manager.Init();

        if (animations_by_unical_name.ContainsKey(AnimationKeepsName))
        {
            my_animations = animations_by_unical_name[AnimationKeepsName];
            _animation_loaded = true;
            return;
        }

        foreach (AnimationClip clip in animation_curve_manager.clips)
        {
            string clip_name = clip.name;

            // split by |
            string[] parts = clip_name.Split('|');
            clip_name = parts[parts.Length - 1];
            clip_name = clip_name.Trim();

            MyAnimation myAnimation = new MyAnimation(
                _rig_controller.PathesList,
                _rig_controller.HashToIndexMap,
                animation_curve_manager,
                clip,
                animation_curve_manager.GetOverdrive(clip_name),
                _rig_controller
            );
            //Debug.Log("Loaded animation: " + clip_name);
            my_animations_by_name.Add(clip_name, myAnimation);
        }

        foreach (AnimationType animation_type in Enum.GetValues(typeof(AnimationType)))
        {
            string animation_name = animation_type.ToString();
            AnimationClip clip = animation_curve_manager.GetClipByNamePartial(animation_name);
            if (clip == null)
                continue;

            MyAnimation my_animation = new MyAnimation(
                _rig_controller.PathesList,
                _rig_controller.HashToIndexMap,
                animation_curve_manager,
                clip,
                animation_curve_manager.GetOverdrive(clip.name),
                _rig_controller
            );
            my_animations.Add(animation_type, my_animation);
        }
        _animation_loaded = true;
        animations_by_unical_name.Add(AnimationKeepsName, my_animations);
    }

    MyList<AnimationChannelData> lerp_result = new MyList<AnimationChannelData>();

    MyList<AnimationChannelData> Lerp(
        MyList<AnimationChannelData> a,
        MyList<AnimationChannelData> b,
        float coeff
    )
    {
        if (a.Count != b.Count)
            return empty_values.array_values;

        lerp_result.ReSize(a.Count);
        for (int i = 0; i < a.Count; i++)
        {
            AnimationChannelData data_a = a[i];
            AnimationChannelData data_b = b[i];
            Vector3 position = Vector3.Lerp(data_a.position, data_b.position, coeff);
            Quaternion rotation = Quaternion.Slerp(data_a.rotation, data_b.rotation, coeff);
            lerp_result[i] = new AnimationChannelData(position, rotation);
        }
        return lerp_result;
    }

    public virtual IAbstractAnimation GetAnimation(AnimationType type)
    {
        if (my_animations.ContainsKey(type))
        {
            return my_animations[type];
        }
        //Debug.LogError("No animation found: " + type.ToString() + " in " + AnimationKeepsName + " for " + gameObject.name + " guard");
        return null;
    }

    MyAnimation _external_animation = null;
    float _start_external_animation_time = 0;

    void UpdateViewAnimation()
    {
        var duration = _external_animation.Duration();
        float time = _chronosphere.CurrentTimelineFlowTime();
        if (_external_animation != null)
        {
            //float time_over_step = _chronosphere.TimeOverStep();
            //float time_modifier = _object_controller.GetObject().GetTimeModifier();

            float loctime = time - _start_external_animation_time;

            // loop animation
            if (loctime > duration)
            {
                loctime = loctime % duration;
                _start_external_animation_time = time - loctime;
            }

            var values = _external_animation.ValuesArray(
                time - _start_external_animation_time,
                false,
                null,
                1.0f
            );
            _rig_controller.Apply(values);
        }
        else
        {
            //_model_animation_control = true;
        }
    }

    // Update is called once per frame
    public void UpdateView(Matrix4x4 main_camera)
    {
        if (_object_controller == null)
        {
            Debug.LogError("No object controller" + name);
            return;
        }

        ObjectOfTimeline guard = _object_controller.GetObject();

        if (IsCameraCanSeeMe(main_camera) == false)
            return;

        if (_cached_fog_of_war == true && guard.AnybodyCanSeeMe() != CanSee.See)
            return;

        if (_model_animation_control == false)
        {
            UpdateViewAnimation();
            return;
        }

        // float time_over_step;
        // try {
        // 	time_over_step = _chronosphere.TimeOverStep();
        // }
        // catch (Exception)
        // {
        // 	time_over_step = 0;
        // }

        long step = guard.LocalStep();
        float local_time = guard.LocalTimeRealTime(guard.GetTimeline().CurrentTime());
        float time_modifier = guard.GetTimeModifier();
        Animatronic animatronic = guard.CurrentAnimatronic();
        if (animatronic == null)
            return;

        MyList<AnimatronicAnimationTask> anims = guard.Animations(local_time);
        ApplyAnimationTasks(anims, time_modifier);
    }

    AnimationValues AnimationValuesForAnimatronic(AnimatronicAnimationTask anim)
    {
        var animation_time = anim.animation_time;
        var my_animation = GetAnimation(anim.animation_type);
        if (my_animation == null)
        {
            return empty_values;
        }

        var dataarr = my_animation.ValuesArray(
            animation_time,
            anim.loop,
            anim.animatronic,
            anim.animation_booster
        );
        return dataarr;
    }

    //MyList<Dictionary<long, AnimationChannelData>> datas = new MyList<Dictionary<long, AnimationChannelData>>();
    MyList<AnimationValues> datasarr = new MyList<AnimationValues>();
    MyList<float> coeffs = new MyList<float>();
    AnimationValues empty_values = default(AnimationValues);

    public AnimationValues AnimationValuesForAnimationTasks(
        MyList<AnimatronicAnimationTask> anims,
        float time_modifier
    )
    {
        //datas.Clear();
        datasarr.Clear();
        coeffs.Clear();

        foreach (AnimatronicAnimationTask anim in anims)
        {
            //var animation_name = anim.animation_type;
            //var animation_time = anim.animation_time + time_over_step * time_modifier;

            var coeff = anim.coeff;
            var dataarr = AnimationValuesForAnimatronic(anim);
            datasarr.Add(dataarr);
            coeffs.Add(coeff);
        }

        //AnimationValues result;

        if (datasarr.Count == 0)
        {
            //Debug.LogError("No animation data. name:" + name);
            return empty_values;
        }

        if (datasarr[0].array_values == null)
            return datasarr[0];
        else
        {
            if (datasarr.Count == 1)
            {
                return datasarr[0];
            }
            else if (datasarr.Count > 1)
            {
                var lerped = Lerp(
                    datasarr[0].array_values,
                    datasarr[1].array_values,
                    1 - coeffs[0]
                );
                return new AnimationValues(lerped);
            }
            else
            {
                return empty_values;
            }
        }
    }

    void ApplyAnimationTasks(MyList<AnimatronicAnimationTask> anims, float time_modifier)
    {
        if (_object_controller.GetObject().IsMaterial() == false)
            return;

        if (anims.Count >= 10)
        {
            string text = "";
            foreach (var anim in anims)
            {
                text += anim.animation_type.ToString() + " ";
            }
            Debug.LogError("Too many animations: " + name + ":" + text);
            return;
        }

        var res = AnimationValuesForAnimationTasks(anims, time_modifier);
        if (res.IsNull())
            return;
        try
        {
            _rig_controller.Apply(res);
        }
        catch (Exception e)
        {
            MyList<string> pathes = new MyList<string>();
            // foreach (var anim in anims)
            // {
            // 	pathes.Add(anim.animation_type.ToString());
            // }
            string animsstr = "anims";

            int count_of_pathes = _rig_controller.PathesList.Count;
            int count_of_hash_to_index = res.Length;

            Debug.LogError(
                "Error in ApplyImpl: "
                    + name
                    + ":"
                    + animsstr
                    + " : "
                    + " count_of_pathes: "
                    + count_of_pathes
                    + " count_of_hash_to_index: "
                    + count_of_hash_to_index
                    + " : "
                    + e.Message
            );
            throw;
        }
    }

    bool IsCameraCanSeeMe(Matrix4x4 invmat, Vector3 p, float delta = 0.2f)
    {
        Vector4 p4 = new Vector4(p.x, p.y, p.z, 1);
        var viewport = invmat * p4;
        viewport /= viewport.w;
        return (
            viewport.x > -1.0f - delta
            && viewport.x < 1.0f + delta
            && viewport.y > -1.0f - delta
            && viewport.y < 1.0f + delta
        );
    }

    Vector3 cached_position;

    void Update()
    {
        cached_position = transform.position;
    }

    bool IsCameraCanSeeMe(Matrix4x4 cam, float delta = 0.2f)
    {
        // var obj = _object_controller.GetObject();
        // var global_position = obj.PositionProphet();
        var global_position = cached_position;

        var position_a = global_position;
        bool camera_can_see_me = IsCameraCanSeeMe(cam, position_a, delta);

        return camera_can_see_me;
    }

    public MyAnimation GetAnimationByName(AnimationType name)
    {
        if (my_animations.ContainsKey(name))
        {
            return my_animations[name];
        }
        return null;
    }

    public Dictionary<AnimationType, MyAnimation> GetAnimations()
    {
        return my_animations;
    }

    public void PlayAnimation(MyAnimation animation)
    {
        _model_animation_control = false;
        _external_animation = animation;
        _start_external_animation_time = _chronosphere.CurrentTimelineFlowTime();
    }

    public void EnableUpdatingFromModel()
    {
        _model_animation_control = true;
    }
}
