#if UNITY_64
using UnityEngine;
#endif

using System;
using System.Collections.Generic;
using System.Security.Cryptography;

public enum CanSee
{
    None,
    See,
    Hear
}

public class CommandSpecificState { }

public struct StunState
{
    public bool is_stunned;
    public long start_stun;
    public long finish_stun;

    public StunState(bool is_stunned, long start_stun, long finish_stun)
    {
        this.is_stunned = is_stunned;
        this.start_stun = start_stun;
        this.finish_stun = finish_stun;
    }
}

public struct ObjectId
{
    public string name;
    public long hash;

    public ObjectId(string name)
    {
        this.name = name;
        this.hash = Utility.StringHash(name);
    }

    // equal
    public static bool operator ==(ObjectId a, ObjectId b)
    {
        return a.hash == b.hash;
    }

    // not equal
    public static bool operator !=(ObjectId a, ObjectId b)
    {
        return a.hash != b.hash;
    }

    public override bool Equals(object obj)
    {
        return this == (ObjectId)obj;
    }

    public override int GetHashCode()
    {
        return hash.GetHashCode();
    }

    public override string ToString()
    {
        return name;
    }
}

public abstract class ObjectOfTimeline : ObjectBase
{
    public UnitPath unit_path_storage = new UnitPath();

    //public IBodyPartsPose body_parts_pose = null;
    CommandBufferBehaviour _behaviour = null;
    protected AiController _ai_controller = null;

    bool _is_hero = false;

    protected event Func<string, ITimeline, IAbilityListPanel, bool> dead_hook;
    public ComponentCollection _components = new ComponentCollection();

    protected SpawnInfo? _parent_guard_name = null;
    protected SpawnInfo? _primary_child_info = null;
    protected ReferencedScrew _velocity_screw = new ReferencedScrew(
        new Vector3(0, 0, 0),
        new Vector3(0, 0, 0),
        null
    );

    protected AbilityList abilityList;
    protected string _proto_id = "";
    public float HearRadius = 15.0f;
    bool _is_copy = false;

    private bool _is_hide = false;

    //private bool _controlable_from_user = false;

    CommandSpecificState _command_specific_state = null;

    private bool _is_material = true;
    private bool _is_disguise = false;
    private bool _is_ai_enabled = true;
    bool _is_very_small = false;
    protected StunState _stun_state = new StunState();
    protected bool _has_camera = false;
    public AnimationType current_animation_type { get; set; } = AnimationType.Idle;

    public bool UseSurfaceNormalForOrientation = false;

    public float _sight_distance = Utility.STANDART_MAX_SIGHT_DISTANCE;
    long _preevaluated_local_step = 0;
    long _preevaluated_broken_step = 0;
    public bool Steering = false;

    Vector3 _preevaluated_torso_position = Vector3.zero;
    Vector2 _preevaluated_global_position_xz = Vector2.zero;
    Vector2 _preevaluated_global_direction_xz = Vector2.zero;
    Pose _preevaluated_global_camera_pose = Pose.Identity;
    float _preevaluated_time_modifier = 1.0f;
    protected Pose _local_camera_pose = Pose.Identity;

    public bool _can_grab_corpse = false;
    public bool _can_grab_corpse_stayed = false;
    public bool _can_grab_alived = false;

    CanSee _anybody_can_see_me = CanSee.None;

    //public MyList<AnimatronicAnimationTask> LastAnimTask;

    protected bool _preevaluated_is_valid = false;

    public float RotationNoiseAmplitude = 0.0f;

    public float PositionNoiseAmplitude = 0.0f;
    public float PositionNoiseFrequency = 1.0f;

    protected ObjectId _dirrect_controlled = default(ObjectId);
    public ObjectId DirrectControlled => _dirrect_controlled;

    public bool HasSpecificInteractionPose = false;
    public Pose SpecificInteractionPose = new Pose(
        Vector3.forward * 0.6f,
        Quaternion.Euler(0, 180, 0)
    );

    bool _walkable_walls = false;

    public float CameraLevel = 1.5f;

    BurrowInternalAspect _burrow_aspect = null;

    public MyList<StoryTrigger> _on_death_triggers = new MyList<StoryTrigger>();

    public Animatronic LastAnimatronic => _animatronic_states?.Last?.Value;
    public LinkedListNodeMAL<Animatronic> LastAnimatronicNode => _animatronic_states.Last;
    public ActionList<Animatronic> AnimatronicStates => _animatronic_states;
    public EventLine<ObjectOfTimeline> _changes = new EventLine<ObjectOfTimeline>(true);

    public ItemComponent _interaction_component;

    // Этот action list содержит состояния ответственные за расчёт плавной анимации.
    // соответственно, здесь должны быть действия, ответственные
    // за перемещение, поворот, анимации блинка, лазанья, стрельбы и т.д.
    protected ActionList<Animatronic> _animatronic_states = new ActionList<Animatronic>(true);

    /// Этот лист отвечает за изменение состояний объекта и его компонент
    public EventLine<ObjectOfTimeline> Changes => _changes;

    public bool IsCanGrubAlive()
    {
        return _can_grab_alived;
    }

    public void Disguise(long offset)
    {
        var ev = new ToggleDisguiseEvent(
            step: LocalStep() + offset,
            actor: this,
            active_on_forward: true
        );
        AddCard(ev);

        if (offset == 0)
            SetDisguise(true);
    }

    public ObjectId _hosted;

    public void SetHosted(ObjectId hosted)
    {
        if (hosted != default)
        {
            Disguise(0);
            SetNextAnimatronic(
                new NullAnimatronic(
                    step: LocalStep(),
                    pose: new ReferencedPose(Pose.Identity, hosted)
                )
            );
        }
        else
        {
            UnDisguise();
        }
        _hosted = hosted;
    }

    public void UnDisguise()
    {
        var ev = new ToggleDisguiseEvent(
            step: LocalStep() + 1,
            actor: this,
            active_on_forward: false
        );
        AddCard(ev);
    }

    public void SetVerySmall(bool value)
    {
        _is_very_small = value;
    }

    public ReferencedPose InteractionPose()
    {
        if (HasComponent<BurrowComponent>())
        {
            return GetComponent<BurrowComponent>().InteractionPose();
        }

        if (HasSpecificInteractionPose == false)
            return CurrentReferencedPose();

        var lpose = CurrentReferencedPose().LocalPose() * SpecificInteractionPose;
        var pose = new ReferencedPose(lpose, CurrentReferencedPose().Frame);
        return pose;
    }

    public bool Interested()
    {
        if (_ai_controller != null)
        {
            var attention_module = AiController().AttentionModule();
            if (attention_module != null)
            {
                var alarm_sources = attention_module.AlarmSources();
                if (alarm_sources != null && alarm_sources.Count != 0)
                {
                    var active_alarm = alarm_sources.Last;
                    if (active_alarm != null)
                    {
                        if (active_alarm is FoundInterestAlarmSource)
                        {
                            return true;
                        }
                    }
                }
            }
        }
        return false;
    }

    public float StunPart01()
    {
        if (!_stun_state.is_stunned)
            return 0.0f;

        var current_step = LocalStep();
        var start = _stun_state.start_stun;
        var finish = _stun_state.finish_stun;

        float percent = ((float)(current_step - start)) / ((float)(finish - start));
        return Mathf.Clamp(percent, 0.0f, 1.0f);
    }

    public bool IsBurrowed()
    {
        return _burrow_aspect != null;
    }

    public BurrowInternalAspect BurrowAspect()
    {
        return _burrow_aspect;
    }

    public void SetBurrowAspect(BurrowInternalAspect aspect)
    {
        _burrow_aspect = aspect;
    }

    public ReferencedPoint InteractionPosition()
    {
        var ipose = InteractionPose();
        return new ReferencedPoint(ipose.LocalPosition(), ipose.Frame);
    }

    public void SetCanGrabCorpse(bool en)
    {
        _can_grab_corpse = en;
    }

    public void SetCanGrabCorpseStayed(bool en)
    {
        _can_grab_corpse_stayed = en;
    }

    public void SetCanGrabAlived(bool en)
    {
        _can_grab_alived = en;
    }

    public bool CanGrabCorpse()
    {
        return _can_grab_corpse;
    }

    public bool CanGrabCorpseStayed()
    {
        return _can_grab_corpse_stayed;
    }

    public IAbilityListPanel AbilityListPanel()
    {
        return abilityList;
    }

    public virtual bool IsMovable()
    {
        return true;
    }

    public bool IsCopy()
    {
        return _is_copy;
    }

    public bool IsPassiveTimePass()
    {
        return IsReversed() != _timeline?.IsReversedPass();
    }

    public AbilityList AbilityList => abilityList;

    public virtual bool IsDifficultToObserve()
    {
        return false;
    }

    public void MoveToInteraction(ObjectOfTimeline other)
    {
        var command = new MoveToInteractionCommand(other.ObjectId(), WalkingType.Run, LocalStep());
        AddExternalCommand(command);
    }

    public void SetInteraction(ItemComponent component)
    {
        _interaction_component = component;
    }

    public ItemComponent GetInteraction()
    {
        return _interaction_component;
    }

    public bool CanUseAbility<T>(ObjectOfTimeline obj) where T : Ability
    {
        var ability = GetAbility<T>();
        return ability.CanUseAbility(obj);
    }

    public bool AbilityCanUse<T>(ObjectOfTimeline obj) where T : Ability
    {
        return abilityList.CanUse<T>(_timeline);
    }

    public void SetCommandSpecificState(CommandSpecificState state)
    {
        _command_specific_state = state;
    }

    public CommandSpecificState GetCommandSpecificState()
    {
        return _command_specific_state;
    }

    public float LocalTimeByStep()
    {
        return LocalStep() / Utility.GAME_GLOBAL_FREQUENCY;
    }

    public void SetCameraLevel(float level)
    {
        CameraLevel = level;
    }

    public void SetWalkableWalls(bool en)
    {
        _walkable_walls = en;
    }

    // public bool IsControlableByUser()
    // {
    // 	return _controlable_from_user;
    // }

    public bool WalkableWalls()
    {
        return _walkable_walls;
    }

    public int NavArea()
    {
        var is_walls_walkable = WalkableWalls();

        if (is_walls_walkable)
        {
            return Utility.ToMask(Areas.BURROW_LINK_AREA)
                | Utility.ToMask(Areas.BURROW_ZONE_AREA)
                | Utility.ToMask(Areas.WALLS_AREA)
                | Utility.ToMask(Areas.WALLS_FOR_ZERO_GRAVITY_AREA)
                | Utility.ToMask(Areas.WALKABLE_SHORT_AREA);
        }
        else
        {
            return 1 << 0
                | 1 << 3
                | 1 << 4
                | 1 << 6
                | 1 << 7
                | 1 << 8
                | 1 << 9
                | 1 << 10
                | 1 << 11
                | 1 << 12
                | 1 << 13
                | 1 << 14
                | Utility.ToMask(Areas.UPSTAIRS_AREA)
                | Utility.ToMask(Areas.BURROW_LINK_AREA)
                | Utility.ToMask(Areas.BRACED_UPDOWN_LINK_AREA)
                | Utility.ToMask(Areas.BURROW_ZONE_AREA)
                | Utility.ToMask(Areas.SEW_LINK_AREA)
                | Utility.ToMask(Areas.WALLS_FOR_ZERO_GRAVITY_AREA);
        }
    }

    public float CurrentTimeMultiplier()
    {
        return _preevaluated_time_modifier;
    }

    public void AddOnDeathTrigger(StoryTrigger trigger)
    {
        _on_death_triggers.Add(trigger);
    }

    public void CleanFlags()
    {
        _anybody_can_see_me = CanSee.None;
    }

    public virtual Vector3 EvaluateGlobalCameraPosition()
    {
        return GlobalPosition() + Vector3.up * CameraLevel;
    }

    public virtual Vector2 EvaluateGlobalCameraDirectionXZ()
    {
        var direction = MathUtil.QuaternionToXZDirection(GlobalPose().rotation);
        return new Vector2(direction.x, direction.z);
    }

    public void SetAnybodyCanSeeMe(CanSee en)
    {
        _anybody_can_see_me = en;
    }

    public CanSee AnybodyCanSeeMe()
    {
        return _anybody_can_see_me;
    }

    public Vector3 PositionNoise()
    {
        if (PositionNoiseAmplitude == 0)
            return Vector3.zero;
        long hash_of_name = _object_id.hash % 1000;
        float x =
            Easing.PerlinNoise1d(hash_of_name + LocalTimeByStep() * PositionNoiseFrequency)
            * PositionNoiseAmplitude;
        float y =
            Easing.PerlinNoise1d(
                hash_of_name + LocalTimeByStep() * PositionNoiseFrequency * 1.04f + 1000.0423f
            ) * PositionNoiseAmplitude;
        float z =
            Easing.PerlinNoise1d(
                hash_of_name + LocalTimeByStep() * PositionNoiseFrequency * 1.08f + 2000.12442f
            ) * PositionNoiseAmplitude;
        return new Vector3(x, y, z);
    }

    public Quaternion RotationNoise()
    {
        if (RotationNoiseAmplitude == 0)
            return Quaternion.identity;
        long hash_of_name = _object_id.hash % 1000;
        float x =
            Easing.PerlinNoise1d(
                hash_of_name + LocalTimeByStep() * PositionNoiseFrequency * 1.05f + 5000.0423f
            ) * RotationNoiseAmplitude;
        float y =
            Easing.PerlinNoise1d(
                hash_of_name + LocalTimeByStep() * PositionNoiseFrequency * 1.02f + 3000.0423f
            ) * RotationNoiseAmplitude;
        float z =
            Easing.PerlinNoise1d(
                hash_of_name + LocalTimeByStep() * PositionNoiseFrequency * 1.03f + 4000.12442f
            ) * RotationNoiseAmplitude;
        var q = Quaternion.Euler(x, y, z);
        return q;
    }

    public void SetPositionNoiseAmplitude(float amplitude)
    {
        PositionNoiseAmplitude = amplitude;
    }

    public void MarkAsHero()
    {
        _is_hero = true;
    }

    public bool IsHero()
    {
        return _is_hero;
    }

    bool _time_paradox_detected = false;

    public event Action<bool> OnTimeParadox;

    public string LinkedInTimeWithName()
    {
        return PrimaryChildName();
    }

    public Actor LinkedObjectInTime()
    {
        if (LinkedInTimeWithName() == null)
            return null;
        return _timeline.GetActor(LinkedInTimeWithName());
    }

    public void DeathInReverseTime(ITimeline timeline, string who_kill_me)
    {
        if (IsDead || IsPreDead)
            return;

        if (timeline.IsPast())
            return;
    }

    public void Respawn(ITimeline timeline)
    {
        if (!IsDead && !IsPreDead)
            return;

        IsDead = false;
        IsPreDead = false;
    }

    public string PrimaryChildName()
    {
        return _primary_child_info?.name;
    }

    public ObjectOfTimeline PrimaryChild()
    {
        string n = PrimaryChildName();
        if (n == null)
            return null;
        return _timeline.GetObject(n);
    }

    public ObjectOfTimeline()
    {
        _behaviour = new CommandBufferBehaviour(this);
        abilityList = new AbilityList(this);
        _components.AddComponent(new CroachControlComponent(this));
        fourd = new FourDObject();
        fourd.AddView(this);
    }

    public void ShareFourdFrom(ObjectOfTimeline other)
    {
        fourd = other.fourd;
        fourd.AddView(this);
    }

    public ActionList<Animatronic> Animatronics()
    {
        return _animatronic_states;
    }

    public ObjectTime object_time()
    {
        return _object_time;
    }

    public void EnableAi(bool state)
    {
        _is_ai_enabled = state;
    }

    public ObjectTime ObjectTime()
    {
        return _object_time;
    }

    public Ability GetAbility<T>() where T : Ability
    {
        return abilityList.GetAbility<T>();
    }

    public CommandBufferBehaviour CommandBuffer()
    {
        return _behaviour;
    }

    public float GetAbilityCooldownPercent(Ability ability)
    {
        return abilityList.GetCooldownPercent(ability.GetType());
    }

    public float GetAbilityCooldownPercent<T>() where T : Ability
    {
        return abilityList.GetCooldownPercent<T>();
    }

    public void Death(ITimeline timeline, string who_kill_me)
    {
        if (IsDead || IsPreDead)
        {
            Debug.Log("Already dead");
            return;
        }

        if (dead_hook != null)
        {
            bool is_prevented = dead_hook.Invoke(who_kill_me, timeline, abilityList);
            if (is_prevented)
                return;
        }

        _on_death_triggers.ForEach(trigger => trigger.Trigger(timeline));

        // if (!timeline.IsPast())
        // {
        long local_start_step = LocalStep();
        var state = new DeathAnimatronic(
            start_step: local_start_step + 1,
            finish_step: Int64.MaxValue,
            pose: CurrentReferencedPose()
        );
        SetNextAnimatronic(state);

        var predeath_card = new PreDeathSelfEvent(step: local_start_step);
        AddCard(predeath_card);
        IsPreDead = true; // < раннее применение

        var death_card = new DeathSelfEvent(
            step: local_start_step + (long)(2.0f * Utility.GAME_GLOBAL_FREQUENCY)
        );
        AddCard(death_card);
        //}

        var linkeds = ListOfLinked();
        foreach (var linked in linkeds)
        {
            linked.SetTimeParadox(true);
        }
    }

    // public void SetDead(bool en)
    // {
    // 	_is_dead = en;
    // }

    // 	public bool IsDead
    // {
    // 	return _is_dead;
    // }

    public bool IsStunned()
    {
        return _stun_state.is_stunned;
    }

    public void SetStunStatus(long start, long finish)
    {
        _stun_state = new StunState(true, start, finish);
    }

    public void UnsetStunStatus()
    {
        _stun_state = new StunState(false, 0, 0);
    }

    public MyList<Actor> ListOfLinked()
    {
        var list = new MyList<Actor>();
        AddLinkedActorsToList(list, true);
        return list;
    }

    private void AddLinkedActorsToList(MyList<Actor> list, bool recurse)
    {
        var linked = LinkedObjectInTime();
        if (linked != null)
        {
            list.Add(linked);
            if (recurse)
                linked.AddLinkedActorsToList(list, recurse);
        }
    }

    public void Anigilation()
    {
        SetMaterial(false);
        //OnMaterialization?.Invoke(false);
    }

    public void Materialization()
    {
        SetMaterial(true);
        //OnMaterialization?.Invoke(true);
    }

    public void AbilityUseSelf<T>(bool ignore_cooldown = false) where T : Ability
    {
        var ability = GetAbility<T>();
        ability.UseSelf(_timeline, abilityList, ignore_cooldown);
    }

    public void AddAbility(Ability abil)
    {
        abil = abilityList.AddOrChange(abil);
    }

    public void SetDeadHook(Func<string, ITimeline, IAbilityListPanel, bool> hook)
    {
        dead_hook = hook;
    }

    public void AbilityUseOnObject<T>(ObjectOfTimeline target, bool ignore_cooldown = false)
        where T : Ability
    {
        var ability = GetAbility<T>();
        ability.UseOnObject(target, _timeline, abilityList, ignore_cooldown);
    }

    public void AbilityUseOnEnvironment<T>(ReferencedPoint pos, bool ignore_cooldown = false)
        where T : Ability
    {
        var ability = GetAbility<T>();
        ability.UseOnEnvironment(
            pos,
            _timeline,
            abilityList,
            private_parameters: null,
            ignore_cooldown: ignore_cooldown
        );
    }

    public void AddInternalCommand(ActorCommand command)
    {
        var _cb_behaviour = CommandBuffer();
        _cb_behaviour.AddInternalCommand(command);
    }

    public void StartPhase()
    {
        _components.StartPhase();
    }

    public void DisableBehaviour()
    {
        _behaviour = null;
        _ai_controller = null;
    }

    public void AddExternalCommand(ActorCommand command)
    {
        var _cb_behaviour = CommandBuffer();
        _cb_behaviour.AddExternalCommand(command);
    }

    public void AddExternalCommandAndApplyFromReversePass(ActorCommand command)
    {
        var _cb_behaviour = CommandBuffer();
        _cb_behaviour.AddExternalCommandAndApplyFromReversePass(command);
    }

    public void AddCard(EventCard<ObjectOfTimeline> card)
    {
        _changes.Add(card);
    }

    public void Demask()
    {
        if (_is_disguise)
            UnDisguise();
    }

    public void SetDirectControlled(ObjectId name)
    {
        _dirrect_controlled = name;
    }

    // public void SetControlableFromUser(bool en, ObjectOfTimeline obj)
    // {
    // 	_controlable_from_user = en;
    // }

    public T AddComponent<T>() where T : ItemComponent, new()
    {
        return _components.AddComponent<T>(this);
    }

    public void AddComponent(ItemComponent component)
    {
        _components.AddComponent(component);
    }

    public void set_velocity(ReferencedScrew vel)
    {
        _velocity_screw = vel;
    }

    public bool IsDisguise()
    {
        return _is_disguise;
    }

    public bool IsAlarmState()
    {
        if (_ai_controller == null)
            return false;

        return _ai_controller.IsAlarmState();
    }

    public void SetDisguise(bool en)
    {
        _is_disguise = en;
    }

    public void HideModel()
    {
        _is_hide = true;
    }

    public bool IsHide()
    {
        return _is_hide || !_is_material || _is_disguise;
    }

    public void ShowModel()
    {
        _is_hide = false;
    }

    public bool IsDead;
    public bool IsPreDead;

    // public bool IsFullDead()
    // {
    // 	return _is_dead;
    // }

    // public void SetPreDead(bool en)
    // {
    // 	_is_pre_dead = en;
    // }


    public Pose PoseProphet()
    {
        var current_animatronic = CurrentAnimatronic();
        if (current_animatronic == null)
            return CurrentReferencedPose().GlobalPose_RealTime(GetTimeline());

        var rp = current_animatronic.GetReferencedPose_RealTime(
            LocalTimeRealTime(GetTimeline().CurrentTime()),
            GetTimeline()
        );
        var global_pose = rp.GlobalPose_RealTime(GetTimeline());
        return global_pose;

        // var chronosphere = _timeline.GetChronosphere();
        // var global_velocity_screw = _velocity_screw.GlobalScrew(_timeline);
        // var ppose = GlobalPose().Prophet(global_velocity_screw,
        // 	0.0f
        // );
        // return ppose;
    }

    // public Vector3 RotationProphet()
    // {
    // 	// var chronosphere = _timeline.GetChronosphere();
    // 	// var time_over_step = chronosphere.TimeOverStep();
    // 	// var baserot = GlobalPose().rotation;
    // 	// var q = Quaternion.Euler(
    // 	// 		_velocity.GlobalVelocity(_timeline) *
    // 	// 		time_over_step *
    // 	// 		_preevaluated_time_modifier);
    // }

    // public Pose PoseProphet()
    // {
    // 	return new Pose(PositionProphet(), RotationProphet());
    // }

    public ReferencedScrew GetReferencedVelocity()
    {
        return _velocity_screw;
    }

    public virtual Dictionary<string, object> ToTrent()
    {
        Dictionary<string, object> dict = new Dictionary<string, object>();
        dict["object_type"] = "Unknown";
        dict["velocity"] = _velocity_screw;
        dict["object_id"] = Name();
        dict["proto_id"] = _proto_id;
        //dict["is_croach_control"] = _is_croach_control;
        dict["is_hide"] = _is_hide;
        //dict["is_croach"] = _is_croach;
        dict["is_material"] = _is_material;
        dict["is_disguise"] = _is_disguise;
        dict["object_time"] = _object_time.ToTrent();
        dict["command_buffer"] = _behaviour.ToTrent();
        dict["sight_distance"] = _sight_distance;
        dict["is_ai_enabled"] = _is_ai_enabled;
        dict["is_very_small"] = _is_very_small;
        dict["is_dead"] = IsDead;
        dict["is_pre_dead"] = IsPreDead;
        return dict;
    }

    public virtual void FromTrent(Dictionary<string, object> dict)
    {
        _velocity_screw.FromTrent((Dictionary<string, object>)dict["velocity"]);
        var object_id = (string)dict["object_id"];
        _object_id = new ObjectId(object_id);
        _proto_id = (string)dict["proto_id"];
        _is_hide = (bool)dict["is_hide"];
        //_is_croach = (bool)dict["is_croach"];
        //_is_croach_control = (bool)dict["is_croach_control"];
        _is_material = (bool)dict["is_material"];
        _is_disguise = (bool)dict["is_disguise"];
        _sight_distance = (float)dict["sight_distance"];
        _is_ai_enabled = (bool)dict["is_ai_enabled"];
        _is_very_small = (bool)dict["is_very_small"];
        IsDead = (bool)dict["is_dead"];
        IsPreDead = (bool)dict["is_pre_dead"];
        _behaviour.FromTrent((Dictionary<string, object>)dict["command_buffer"]);
        _object_time.FromTrent((Dictionary<string, object>)dict["object_time"]);
    }

    static public ObjectOfTimeline CreateFromTrent(Dictionary<string, object> dict)
    {
        var object_type = (string)dict["object_type"];
        switch (object_type)
        {
            case "Actor":
                var actor = new Actor();
                actor.FromTrent(dict);
                return actor;
            default:
                throw new Exception("Unknown object type: " + object_type);
        }
    }

    public ITimeline GetTimeline()
    {
        return _timeline;
    }

    public void SetTimeParadox(bool en)
    {
        _time_paradox_detected = en;
        OnTimeParadox?.Invoke(en);
    }

    public bool IsTimeParadox()
    {
        return _time_paradox_detected;
    }

    public ReferencedScrew GetReferencedVelocityScrew()
    {
        return _velocity_screw;
    }

    public virtual void PromoteExtended(long local_step) { }

    public virtual void ExecuteExtended(long timeline_step, long local_step) { }

    public void PromoteChanges()
    {
        _changes.Promote(LocalStep(), this);
    }

    public bool IsAiEnabled()
    {
        return _is_ai_enabled;
    }

    public void PreevaluateLocalStep(long timeline_step)
    {
        _preevaluated_broken_step = _object_time.TimelineToBroken(timeline_step);
        _preevaluated_local_step = _object_time.BrokenToLocal(_preevaluated_broken_step);
        _preevaluated_time_modifier = _object_time.CurrentTimeMultiplier();
    }

    public float LocalTimeRealTime(float timeline_time)
    {
        return _object_time.TimelineToLocal_Time(timeline_time);
    }

    public virtual void CheckAnotherSeenOrHearImpl()
    {
        var enemies = _timeline.Enemies();
        foreach (var enemy in enemies)
        {
            if (enemy.AnybodyCanSeeMe() == CanSee.See)
                continue;

            // var distance = Vector3.Distance(GlobalPosition(), enemy.GlobalPosition());
            // if (distance < 2.0f)
            // {
            // 	enemy.SetAnybodyCanSeeMe(CanSee.See);
            // 	continue;
            // }

            var cansee = (_timeline as Timeline).present.IsCanSee(
                this._timeline_index,
                enemy._timeline_index
            );
            if (cansee == CanSee.See)
            {
                enemy.SetAnybodyCanSeeMe(CanSee.See);
                continue;
            }

            if (enemy.AnybodyCanSeeMe() == CanSee.Hear)
                continue;

            var canhear = GameCore.IsCanHear(this, enemy, HearRadius);
            if (canhear)
            {
                enemy.SetAnybodyCanSeeMe(CanSee.Hear);
                continue;
            }
        }
    }

    public void CheckAnotherSeenOrHear()
    {
        if (!_is_hero)
        {
            return;
        }
        _anybody_can_see_me = CanSee.See;
        CheckAnotherSeenOrHearImpl();
    }

    public bool HearOnly()
    {
        return _anybody_can_see_me == CanSee.Hear;
    }

    public bool HasEyes()
    {
        if (this is Actor || this is CameraObject)
            return true;

        return false;
    }

    public bool IsMove()
    {
        return CurrentAnimatronic() is MovingAnimatronic;
    }

    public void ApplyAnimatronicsList(MyList<Animatronic> list, bool drop_state = true)
    {
        if (drop_state)
        {
            DropToCurrentState();
            //ReplaceCurrentAnimatronicFinishStep(LocalStep());
        }

        foreach (var anim in list)
        {
            SetNextAnimatronic(anim, false);
        }
    }

    public void Promote(long timeline_step)
    {
        if (!IsMaterial())
            return;

        TimeMultipliersPromote(timeline_step);

        _components.Promote(timeline_step);
        PromoteChanges();

        MyList<Animatronic> goned;
        _animatronic_states.UpdatePresentState(_preevaluated_local_step, out goned);
        _animatronic_states.Current()?.apply(this, _preevaluated_local_step);
        abilityList.PromoteCooldowns();
    }

    public void AiPromotion(long timeline_step)
    {
        _ai_controller?.Promote(_preevaluated_local_step, _timeline);
        _behaviour?.Promote(_preevaluated_local_step, _timeline);
        PromoteExtended(_preevaluated_local_step);
    }

    public AiController AiController()
    {
        if (_ai_controller == null)
            return null;

        return _ai_controller;
    }

    public ActorCommand CurrentCommand()
    {
        return CommandBuffer().CurrentCommand();
    }

    public void TestSeePhase()
    {
        CheckAnotherSeenOrHear();
    }

    public void Execute(long timeline_step)
    {
        if (!IsMaterial())
            return;

        // if (_is_disguise &&
        // 	(CurrentAnimatronic() is not IdleAnimatronic) &&
        // 	(CurrentAnimatronic() is not NullAnimatronic)
        // )
        // {
        // 	UnDisguise();
        // }

        var local_step = _object_time.TimelineToLocal(timeline_step);
        _components.Execute(timeline_step, local_step);

        if (_behaviour != null)
        {
            if (IsDead || IsPreDead || _stun_state.is_stunned)
            {
                _behaviour.CleanArtifacts();
                _ai_controller?.CleanArtifacts();
                return;
            }

            float _object_time_multiplier = _object_time.CurrentTimeMultiplier();
            if (_object_time_multiplier > 0)
            {
                //if (_is_ai_enabled && (local_step + _timeline_index) % Utility.GAME_PLANNING_PERIOD == 0)
                _ai_controller?.Execute(timeline_step, local_step, _timeline);
                _behaviour.Execute(local_step, _timeline);
            }
        }
        ExecuteExtended(timeline_step, local_step);
    }

    public AttentionModule GetAttentionModule()
    {
        var ai = _ai_controller;
        if (ai == null)
            return null;

        return ai.GetAttentionModule();
    }

    public virtual void DropToCurrentState()
    {
        _animatronic_states.DropToCurrentState();
        _changes.DropToCurrentState();
        _object_time.DropToCurrentState();
        _behaviour?.DropToCurrentState(LocalStep());
        _ai_controller?.DropToCurrentState(LocalStep());
        abilityList.DropToCurrentState(LocalStep());
    }

    public void DropToCurrentStateInverted()
    {
        _animatronic_states.DropToCurrentStateInverted();
        _changes.DropToCurrentStateInverted();
        _object_time.DropToCurrentStateInverted();
        _behaviour?.DropToCurrentStateInverted(LocalStep());
        _ai_controller?.DropToCurrentStateInverted(LocalStep());
        abilityList.DropToCurrentState(LocalStep());
    }

    //public abstract ObjectOfTimeline Copy(ITimeline newtimeline);




    // public long HashOfName()
    // {
    // 	return _object_id.hash;
    // }

    // Вызывается таймлайном
    public void OnRemove()
    {
        fourd.RemoveView(this);
    }

    public string ProtoId()
    {
        return _proto_id;
    }

    public void SetProtoId(string proto_id)
    {
        _proto_id = proto_id;
    }

    public bool IsReversed()
    {
        return _object_time.IsReversed;
    }

    public Vector3 HeadPositionCalculation()
    {
        return GlobalPosition() + Vector3.up * CameraLevel;
    }

    public Vector3 HeadPositionView()
    {
        var pose = GlobalPose();
        var diff = new Pose(new Vector3(0, 1.0f, 0), Quaternion.identity);
        return (pose * diff).position;
    }

    public Vector3 TorsoPosition()
    {
        if (_preevaluated_is_valid)
            return _preevaluated_torso_position;

        PreEvaluate();
        return _preevaluated_torso_position;
    }

    public PseudoGravityVectorEvaluator pseudoGravityVectorEvaluator = null;

    // Переопределение вектора ускорение свободного падения
    // для неевклидовых пространств
    public Vector3 PlatformPseudoGravityVector(Vector3 global_point)
    {
        if (pseudoGravityVectorEvaluator != null)
            return pseudoGravityVectorEvaluator.Evaluate(global_point);

        return Vector3.up;
    }

    public Vector3 PreEvaluateTorsoPosition()
    {
        var pose = CurrentReferencedPose().GlobalPose(_timeline);
        var pos = pose.TransformPoint(Vector3.up * Utility.TORSO_LEVEL);

        //var pos = CurrentReferencedPose().GlobalPosition(_timeline)
        //	+ Vector3.up * Utility.TORSO_LEVEL;
        return pos;
    }

    public virtual void PreEvaluateChild() { }

    public void PreEvaluate()
    {
        // if (_preevaluated_is_valid)
        // 	return;

        _preevaluated_is_valid = true;

        PreEvaluateChild();

        _preevaluated_global_pose = PreEvaluateGlobalPose();
        _preevaluated_torso_position = PreEvaluateTorsoPosition();
        //_preevaluated_global_position_xz = PreEvaluateGlobalPositionXZ();
        //_preevaluated_global_direction_xz = PreEvaluateGlobalDirectionXZ();

        if (HasCamera())
            _preevaluated_global_camera_pose = EvaluateGlobalCameraPose();
    }

    public void SetHasCamera(bool has_camera)
    {
        _has_camera = has_camera;
    }

    public bool HasCamera()
    {
        return true;
        //return _has_camera != null;
    }

    public int CountOfCards()
    {
        return _animatronic_states.Count + _object_time.CountOfModifiers();
    }

    public Vector3 Position()
    {
        return CurrentReferencedPose().LocalPose().position;
    }

    public Vector3 position()
    {
        return CurrentReferencedPose().LocalPose().position;
    }

    public bool HasComponent<T>() where T : ItemComponent
    {
        return _components.HasComponent<T>();
    }

    public T GetComponent<T>() where T : ItemComponent
    {
        return _components.GetComponent<T>();
    }

    public void InterruptAnimatronic()
    {
        var idle_animatronic = new IdleAnimatronic(
            LocalStep(),
            pose: CurrentReferencedPose(),
            idle_animation: AnimationType.Idle,
            local_camera_pose: new Pose(new Vector3(0, CameraLevel, 0), Quaternion.identity)
        );
        SetNextAnimatronic(idle_animatronic);
    }

    public Vector3 GlobalPositionToLocal(Vector3 global_position)
    {
        var moved_with = MovedWithObject();
        if (moved_with == null)
            return global_position;

        var parent_pose = moved_with.GlobalPose();
        return parent_pose.Inverse().TransformPoint(global_position);
    }

    public abstract ReferencedPose CurrentReferencedPose();

    public ReferencedPoint CurrentReferencedPosition()
    {
        return CurrentReferencedPoint();
    }

    public ReferencedPoint CurrentReferencedPoint()
    {
        return CurrentReferencedPose().ToPoint();
    }

    public void SetSightDistance(float distance)
    {
        _sight_distance = distance;
    }

    public float SightDistance()
    {
        return _sight_distance;
    }

    public float _sight_angle = 120.0f;

    public float SightAngle()
    {
        if (Interested())
            return _sight_angle / 2.0f;
        return _sight_angle;
    }

    // public void ReplaceCurrentAnimatronicFinishStep(long finish_step)
    // {
    // 	var last_active = _animatronic_states.CurrentState();
    // 	if (last_active == null)
    // 		return;

    // 	// var copy_of_last_active = last_active.Clone();
    // 	// copy_of_last_active.SetFinishStep(finish_step);

    // 	// _animatronic_states.Replace(last_active, copy_of_last_active);
    // }


    public Animatronic SetNextAnimatronic(Animatronic state, bool preemptive = true)
    {
        int overlap_count = CountOfAnimsInOverlapZone();
        //Debug.Assert(overlap_count < 10);

        if (preemptive)
        {
            DropToCurrentState();
            //ReplaceCurrentAnimatronicFinishStep(state.StartStep);
        }

        var last_start_step = _animatronic_states.LastStepInStartList();
        if (state.StartStep < last_start_step)
        {
            var who_has_last_start_step = (Animatronic)_animatronic_states.Last.Value;
            if (who_has_last_start_step == null)
                Debug.Log("Аниматроник с наибольшим start_step пустой");
            else
                Debug.Log(
                    $"Аниматроник с наибольшим start_step {last_start_step}: {who_has_last_start_step.info()}"
                );

            Debug.Log(
                $"Замечен аниматроник с меньшим start_step: {state.StartStep} < {last_start_step}. {state.info()}"
            );
        }

        var last_active = _animatronic_states.CurrentState();
        if (last_active is IdleAnimatronic)
        {
            // var copy =  last_active.Clone() as IdleAnimatronic;
            // copy.SetFinishStep(state.StartStep);
            // _animatronic_states.Replace(last_active, copy);
        }

        bool is_not_exists = _animatronic_states.Add(state);

        return state;
    }

    public ObjectId MovedWith()
    {
        return CurrentReferencedPose().Frame;
    }

    public void SetLocalCameraPose(Pose pose)
    {
        _local_camera_pose = pose;
    }

    // public void SetBodyPartsPose(IBodyPartsPose pose)
    // {
    // 	body_parts_pose = pose;
    // }

    public void SetSightAngle(float angle)
    {
        _sight_angle = angle;
    }

    public void HearNoise(
        long step,
        ReferencedPoint position,
        RestlessnessParameters noise_parameters
    )
    {
        _ai_controller?.HearNoise(step, position, noise_parameters);
    }

    public Pose EvaluateGlobalCameraPose()
    {
        var global_pose = GlobalPose();
        return global_pose * _local_camera_pose;
    }

    private Pose GlobalCameraPose()
    {
        if (!_preevaluated_is_valid)
            PreEvaluate();

        return _preevaluated_global_camera_pose;
    }

    public Pose CameraPose()
    {
        return GlobalCameraPose();
    }

    public Vector3 GunPosition()
    {
        var pose = GlobalPose();
        return pose.position + pose.rotation * new Vector3(0, 1.0f, 1.0f);
    }

    public Pose HeadPose()
    {
        var pose = GlobalPose();
        var diff = new Pose(new Vector3(0, 1.0f, 0), Quaternion.identity);
        return pose * diff;
    }

    public ObjectOfTimeline MovedWithObject()
    {
        if (CurrentReferencedPose().Frame == default(ObjectId))
            return null;

        return _timeline.GetObject(CurrentReferencedPose().Frame);
    }

    public Pose PreEvaluateGlobalPose()
    {
        return CurrentReferencedPose().GlobalPose(_timeline);
    }

    // public Pose GlobalPose()
    // {
    // 	if (!_preevaluated_is_valid)
    // 		PreEvaluate();

    // 	return _preevaluated_global_pose;
    // }

    public Vector3 GlobalPosition()
    {
        return GlobalPose().position;
    }

    // public MyList<Animatronic> GetAnimatronicsList()
    // {
    // 	return _animatronic_states.GetList();
    // }


    public Vector3 Direction()
    {
        return MathUtil.QuaternionToXZDirection(CurrentReferencedPose().LocalRotation());
    }

    public Quaternion Rotation()
    {
        return _preevaluated_global_pose.rotation;
    }

    public long LocalStep()
    {
        return _preevaluated_local_step;
    }

    public bool InBrokenInterval()
    {
        var curbroken = _preevaluated_broken_step;
        return curbroken >= fourd_start && curbroken <= fourd_finish;
    }

    public long BrokenStep()
    {
        return _preevaluated_broken_step;
    }

    public void SetTimeline(ITimeline tl)
    {
        _timeline = tl;
    }

    public void SetAiController(AiController controller)
    {
        _ai_controller = controller;
        _behaviour.SetControlledByAi(true);
    }

    public Vector3 LocalPosition()
    {
        return CurrentReferencedPose().LocalPosition();
    }

    public virtual void CopyFrom(ObjectOfTimeline other, ITimeline newtimeline)
    {
        _object_id = other._object_id;
        _proto_id = other._proto_id;
        _time_paradox_detected = other._time_paradox_detected;

        _is_hide = other._is_hide;
        _is_material = other._is_material;
        _is_disguise = other._is_disguise;
        _is_hero = other._is_hero;
        _is_very_small = other._is_very_small;

        // Копия обычно выполняется для переноса объекта в другой таймлайн,
        // поэтому таймлайн не копируется, а задаётся устанавливается новым.
        _timeline = newtimeline;
        _object_time = new ObjectTime(other._object_time);
        _animatronic_states = new ActionList<Animatronic>(other._animatronic_states);
        _components = new ComponentCollection(other._components, this);
        abilityList = other.abilityList.Copy(newowner: this);

        _on_death_triggers = new MyList<StoryTrigger>(other._on_death_triggers);

        if (other._behaviour != null)
            _behaviour = (CommandBufferBehaviour)other._behaviour.Copy(newactor: this);
        else
            _behaviour = null;

        if (other._ai_controller != null)
            _ai_controller = other._ai_controller.Copy(newactor: this);
        else
            _ai_controller = null;

        _preevaluated_torso_position = other._preevaluated_torso_position;
        _preevaluated_global_position_xz = other._preevaluated_global_position_xz;
        _preevaluated_global_pose = other._preevaluated_global_pose;
        _preevaluated_global_direction_xz = other._preevaluated_global_direction_xz;
        _preevaluated_local_step = other._preevaluated_local_step;
        _preevaluated_broken_step = other._preevaluated_broken_step;
        _preevaluated_global_camera_pose = other._preevaluated_global_camera_pose;

        fourd_finish = other.fourd_finish;
        fourd_start = other.fourd_start;

        _dirrect_controlled = other._dirrect_controlled;
        _sight_distance = other._sight_distance;
        _is_copy = true;
        _walkable_walls = other._walkable_walls;
        UseSurfaceNormalForOrientation = other.UseSurfaceNormalForOrientation;

        _has_camera = other._has_camera;
        _local_camera_pose = other._local_camera_pose;
        //_is_croach_control = other._is_croach_control;
        _stun_state = other._stun_state;
        IsDead = other.IsDead;
        IsPreDead = other.IsPreDead;
        _is_ai_enabled = other._is_ai_enabled;

        _can_grab_corpse = other._can_grab_corpse;
        _can_grab_corpse_stayed = other._can_grab_corpse_stayed;
        _can_grab_alived = other._can_grab_alived;
        HasSpecificInteractionPose = other.HasSpecificInteractionPose;
        _anybody_can_see_me = other._anybody_can_see_me;
        _sight_angle = other._sight_angle;
    }

    string MakeNewUnicalName(string name)
    {
        lbl:
        var variant = name + "_1";
        var test = _timeline.GetObject(variant);
        if (test == null)
            return variant;
        name = variant;
        goto lbl;
    }

    public ObjectOfTimeline TearWithReverse()
    {
        var copy = Copy(_timeline);
        copy.SetName(MakeNewUnicalName(Name()));
        copy.SetReversed(!IsReversed());
        copy.ShareFourdFrom(this);
        (_timeline as Timeline).AddObject(copy);
        return copy;
    }

    public bool IsVerySmall()
    {
        return _is_very_small;
    }

    public long ObjectStartTimelineStep()
    {
        //var local_step = fourd_start;
        return _object_time.BrokenPointInTimeline();
    }

    public bool CurrentAnimatronicIsFinished()
    {
        // return _animatronic_states.ActiveStates().Count == 0
        //	&& _animatronic_states.CurrentNode().next == _animatronic_states.NullNode();
        if (_animatronic_states.CurrentState() != null)
            return false;

        if (_animatronic_states.Current() == null)
            return true;

        var local_step = LocalStep();
        return _animatronic_states.Current().FinishStep < local_step;
    }

    protected virtual bool IsStateEqualImpl(ObjectOfTimeline obj)
    {
        if (_object_id != obj._object_id)
        {
            Debug.Log("ObjectOfTimeline: _object_id is not equal");
            return false;
        }

        if (_proto_id != obj._proto_id)
        {
            Debug.Log("ObjectOfTimeline: _proto_id is not equal");
            return false;
        }

        // if (!_object_time.IsEqual(obj._object_time)) {
        // 	Debug.Log("ObjectOfTimeline: _object_time is not equal");
        // 	return false;
        // }

        // if (_behaviour != null && obj._behaviour != null)
        // {
        // 	if (_behaviour.IsEqual(obj._behaviour) == false)
        // 		return false;
        // }

        // if (_ai_controller != null && obj._ai_controller != null)
        // {
        // 	if (_ai_controller.IsEqual(obj._ai_controller) == false)
        // 		return false;
        // }

        if (CurrentReferencedPose() != obj.CurrentReferencedPose())
        {
            Debug.Log("ObjectOfTimeline: poses is not equal");
            return false;
        }

        return true;
    }

    public void CleanAllQueues()
    {
        _animatronic_states.Clean();
        _changes.Clean();
        _object_time.Clean();
        _behaviour?.Clean();
        //_ai_controller?.Clean();
        //abilityList.Clean();
    }

    public ObjectOfTimeline SpawnCopyToPosition(ReferencedPoint pos)
    {
        var copy = Copy(GetTimeline());
        copy.SetName(MakeNewUnicalName(Name()));
        copy.CleanAllQueues();
        var pose = copy.CurrentReferencedPose();
        var global_pose = pose.GlobalPose(GetTimeline());
        var pnt = pos.GlobalPosition(GetTimeline());
        var npose = ReferencedPose.FromGlobalPose(
            new Pose(pnt, global_pose.rotation),
            pos.Frame,
            GetTimeline()
        );
        (copy as Actor).SetReferencedPose(npose);
        copy.fourd_start = BrokenStep();
        return copy;
    }

    public long FourDTimelineStart()
    {
        return _object_time.BrokenToTimeline(fourd_start);
    }

    public bool IsStateEqual(ObjectOfTimeline obj)
    {
        Type t1 = this.GetType();
        Type t2 = obj.GetType();

        if (t1 != t2)
            return false;

        return IsStateEqualImpl(obj);
    }

    public virtual bool IsEqual(ObjectOfTimeline obj)
    {
        return IsStateEqual(obj);
    }

    public long ReverseMultiplier()
    {
        return IsReversed() ? -1 : 1;
    }

    public float GetTimeModifier()
    {
        return _object_time.CurrentTimeMultiplier() * ReverseMultiplier();
    }

    public void AddBrokenOffsetToLocalTime(long broken_offset)
    {
        //_object_time.AddBrokenOffset(broken_offset);
    }

    public bool IsMaterial()
    {
        return _is_material;
    }

    public void SetMaterial(bool en)
    {
        _is_material = en;
    }

    public string Info()
    {
        string text = "";

        string td = IsReversed() ? "Reversed" : "Forward";
        text += $"Pose: {CurrentReferencedPose()}\n";
        text += $"TimeDirection: {td}\n";
        text += $"ActiveTimeModifiers: {_object_time.ActiveModifiers().Count}\n";
        text += $"LocalTimeOffset: {LocalTimeOffset}\n";
        text += $"ObjectTime.Offset: {_object_time.Offset}\n";
        text += $"CurrentAnimatronic: {CurrentAnimatronic()}\n";

        // count of animatronic states
        text += $"Animatronics: {_animatronic_states.Count}\n";

        var time_from_animation_start = _animatronic_states.Current()?.TimeFromStart(LocalStep());
        text += $"TimeFromAnimationStart: {time_from_animation_start:0.00}\n";
        if (_animatronic_states.Current() != null)
        {
            text +=
                $"AnimationTimeOnStep(current): {_animatronic_states.Current().AnimationTimeOnStep(LocalStep()):0.00} {_animatronic_states.Current()} initial_time:{_animatronic_states.Current().InitialAnimationTime():0.00}\n";
        }
        if (_animatronic_states.Previous() != null)
        {
            text +=
                $"AnimationTimeOnStep(previous): {_animatronic_states.Previous().AnimationTimeOnStep(LocalStep()):0.00} {_animatronic_states.Previous()} initial_time:{_animatronic_states.Previous().InitialAnimationTime():0.00}\n";
        }
        text += $"LocalStep: {LocalStep()}\n";

        text += $"IsMaterial: {IsMaterial()}\n";
        text += $"IsDisguise: {IsDisguise()}\n";
        text += $"IsDead: {IsDead} IsDead: {IsPreDead}\n";
        text += $"IsHide: {IsHide()}\n";
        text += $"IsAiEnabled: {IsAiEnabled()}\n";
        text += $"IsHero: {IsHero()}\n";
        text += $"IsTimeParadox: {IsTimeParadox()}\n";
        text += $"IsReversed: {IsReversed()}\n";

        return text;
    }

    public Animatronic CurrentAnimatronic()
    {
        return _animatronic_states.Current();
    }

    public long LocalTimeOffset
    {
        get { return _object_time.Offset; }
    }

    int CountOfAnimsInOverlapZone()
    {
        long local_step = LocalStep();
        var nullnode = _animatronic_states.NullNode();
        var current_node = _animatronic_states.CurrentNode();
        if (current_node == nullnode)
            return 0;
        var iterator = current_node;
        var current_animation_time = current_node.Value.LocalTimeForStep(local_step);
        float OVERLAP = current_node.Value.OverlapTime();
        int i = 0;
        while (
            iterator == current_node
            || (
                iterator != nullnode
                && current_animation_time - iterator.Value.FinishLocalTime() < OVERLAP
            )
        )
        {
            i++;
            iterator = iterator.Previous;
            if (i > 100)
                break;
        }
        return i;
    }

    MyList<AnimatronicAnimationTask> anims_result = new MyList<AnimatronicAnimationTask>();

    public MyList<AnimatronicAnimationTask> Animations(float local_time)
    {
        //Debug.Log("Animations local_time: " + local_time);
        long local_step = (long)(local_time / Utility.GAME_GLOBAL_FREQUENCY);
        anims_result.Clear();
        if (!IsMaterial())
            return anims_result;

        var result = anims_result;

        var current_node = _animatronic_states.CurrentNode();
        var nullnode = _animatronic_states.NullNode();
        if (current_node == nullnode)
            return result;
        var iterator = current_node;
        //var time_from_start_last = current_node.Value.TimeFromStart(local_time);

        //float OVERLAP = current_node.Value.OverlapTime();
        float OVERLAP = 0.5f;

        // result.Add(
        // 	new AnimatronicAnimationTask(
        // 		current_node.Value.GetAnimationType(local_step),
        // 		current_node.Value.AnimationTimeOnLocalTime(local_time),
        // 		1.0f,
        // 		current_node.Value,
        // 		loop: current_node.Value.IsLooped()
        // 	)
        // );
        // if (time_from_start_last > OVERLAP)
        // 	return result;

        float backpack = 1;
        int maxanims = 3;
        while (iterator == current_node || (iterator != nullnode))
        {
            if (result.Count >= maxanims)
                break;

            if (backpack < 0.01f)
                break;

            //if (

            var time_from_iterator_start = iterator.Value.TimeFromStart(local_time);
            var coeff = time_from_iterator_start / OVERLAP;

            //Debug.Log("current_animation_time: " + current_animation_time);
            //Debug.Log("iterator.Value.FinishLocalTime(): " + iterator.Value.FinishLocalTime());

            //float coeff = 1;
            //if (OVERLAP != 0)
            //	coeff = iterator.Value.TimeFromStart(local_time) / OVERLAP;

            if (coeff > 1)
                coeff = 1;

            if (coeff < 0)
                coeff = 0;

            // if (!(coeff >= 0 && coeff <= 1))
            // {
            // 	Debug.Log("coeff: " + coeff);
            // }

            coeff = coeff * backpack;
            backpack = backpack - coeff;

            if (backpack > 1)
                backpack = 1;

            if (backpack < 0)
                backpack = 0;

            //Debug.Log("anim: " + iterator.Value.GetAnimationType(local_step));
            result.Add(
                new AnimatronicAnimationTask(
                    iterator.Value.GetAnimationType(local_step),
                    iterator.Value.AnimationTimeOnLocalTime(local_time),
                    coeff,
                    iterator.Value,
                    loop: iterator.Value.IsLooped(),
                    animation_booster: iterator.Value.AnimationBooster()
                )
            );
            iterator = iterator.Previous;
        }
        //LastAnimTask = result;
        return result;
    }

    public Tuple<ReferencedPose, long> AddPoseLerp(
        ReferencedPose apose,
        ReferencedPose bpose,
        long start_step,
        long finish_step
    )
    {
        var anim = new PoseLerpAnimatronic(apose, bpose, start_step, finish_step);
        _animatronic_states.Add(anim);
        return new Tuple<ReferencedPose, long>(bpose, finish_step);
    }

    public Tuple<ReferencedPose, long> AddPoseBezierLerp(
        ReferencedPose apose,
        ReferencedPose bpose,
        ReferencedPose cpose,
        long start_step,
        long finish_step
    )
    {
        var anim = new PoseBezierLerpAnimatronic(apose, bpose, cpose, start_step, finish_step);
        _animatronic_states.Add(anim);
        return new Tuple<ReferencedPose, long>(cpose, finish_step);
    }

    public Tuple<ReferencedPose, long> AddPoseLerp_Duration(ReferencedPose target, float duration)
    {
        var curstep = LocalStep();
        var curpose = CurrentReferencedPose();
        long final_step = curstep + (long)(duration * Utility.GAME_GLOBAL_FREQUENCY);
        //Debug.Log("AddPoseLerp_Duration: " + final_step);
        return AddPoseLerp(curpose, target, curstep, final_step);
    }
}
