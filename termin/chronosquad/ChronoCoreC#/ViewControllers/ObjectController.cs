using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
#if UNITY_EDITOR
using UnityEditor;
#endif

public enum OutlineColor
{
    Red,
    Green,
    Yellow,
    Violent,
    Black,
    Cyan,
    None,
    Hide,
}

public class ObjectController : MonoBehaviour
{
    TimelineController _timeline_controller = null;
    ObjectProxy _object_proxy;
    public bool AlwaysVisible = false;

    public bool is_selected = false;
    bool _cached_fog_of_war = false;
    bool _is_outline_mode_enabled = false;
    public string PrefabLabel;
    public bool HideInTimeSpiritMode = false;

    public static ObjectId HoverredObjectName = default;

    //Color ErrorCollor = new Color(0, 1, 1, 1);
    //float error_period = 1.0f;
    //float error_amplitude = 0.9f;

    public event Action OnHoverEventHook;

    public float SightDistance = Utility.STANDART_MAX_SIGHT_DISTANCE;
    public float SightAngle = 120.0f;

    public Transform _head_transform;
    public Transform _torso_transform;
    public Transform _gun_transform;
    public Transform _camera_transform;
    bool _don_react_on_distruct;

    Material _temp_material;
    bool _temp_material_setted = false;

    //GameObject prediction_object = null;
    //Material prediction_material = null;

    LineRenderer _view_marker_line = null;

    public bool AnigilatedOnStart = false;

    RotaryProgressBarView StunEffect = null;

    public bool UseNormalAsUp = false;

    public bool UseInteractionPosition = false;

    public bool ReverseOnStart = false;
    public bool WalkableWalls = false;

    public bool Steering = false;

    public event Action OnRemoveMe;

    // public void Init(ObjectOfTimeline obj)
    // {
    // 	_object = obj;
    // }

    SoundEffectView _sound_effect = null;

    MyList<Activity> _activities = new MyList<Activity>();

    Camera _camera;

    protected GameObject _model;

    //bool is_showed = true;

    Pose on_init_pose;

    //	public bool ErrorMarkerEnabled = false;

    MyList<GameObject> _list_subchilds = new MyList<GameObject>();
    MyList<Renderer> _renderers = new MyList<Renderer>();
    MyList<Collider> _colliders = new MyList<Collider>();
    MyList<Material> _materials = new MyList<Material>();

    protected Material _phantom_material = null;

    GameObject torso_position_object = null;

    public void SetOutlineMode(bool en)
    {
        _is_outline_mode_enabled = en;
    }

    public void DontReactOnDistruct(bool en)
    {
        _don_react_on_distruct = en;
    }

    protected void HideAllRenderers()
    {
        foreach (var renderer in _renderers)
        {
            renderer.enabled = false;
        }
        torso_position_object?.SetActive(false);
    }

    public void OnRemoveMeInvoke()
    {
        OnRemoveMe?.Invoke();
    }

    public bool IsSelected()
    {
        return is_selected;
    }

    protected void ShowAllRenderers()
    {
        foreach (var renderer in _renderers)
        {
            renderer.enabled = true;
        }
        torso_position_object?.SetActive(true);
    }

    public Pose GetHead()
    {
        if (_head_transform == null)
            return new Pose(transform.position, transform.rotation);

        return new Pose(_head_transform.position, _head_transform.rotation);
    }

    // public Pose GetTorso()
    // {
    // 	if (_torso_transform == null)
    // 		return new Pose(
    // 			transform.position,
    // 			transform.rotation
    // 		);

    // 	return new Pose(
    // 		_torso_transform.position,
    // 		_torso_transform.rotation
    // 	);
    // }

    // public Pose GetGun()
    // {
    // 	if (_gun_transform != null)
    // 		return new Pose(
    // 			_gun_transform.position,
    // 			_gun_transform.rotation
    // 		);

    // 	if (_torso_transform != null)
    // 		return new Pose(
    // 			_torso_transform.position,
    // 			_torso_transform.rotation
    // 		);

    // 	return new Pose(
    // 		transform.position,
    // 		transform.rotation
    // 	);
    // }

    public MyList<Renderer> Renderers()
    {
        return _renderers;
    }

    public virtual float GetSightDistance()
    {
        return SightDistance;
    }

    public Tuple<GameObject, Material> MakePredictionObject()
    {
        var newobj = GameCore.GetChronosphereController().MakeNonUnicalGreenHologram(gameObject);
        if (newobj == null)
            return null;

        if (newobj.Item1 != null)
            newobj.Item1.SetActive(false);
        return newobj;
    }

    public bool IsControlableByUser()
    {
        var obj = GetObject();
        //if (obj.IsHero() || obj.IsControlableByUser())
        if (obj.IsHero())
            return true;
        return false;
    }

    public MyList<Activity> Activities()
    {
        return _activities;
    }

    public void SetFogOfWar(bool en)
    {
        _cached_fog_of_war = en;
    }

    public void add_activity(Activity activity)
    {
        _activities.Add(activity);
    }

    public bool PhantomMaterialMode = false;
    bool PhantomMaterialMode_Last = false;

    bool _phantom_material_mode = false;
    public bool PhantomMaterialModeProperty
    {
        get { return _phantom_material_mode; }
        set
        {
            if (value)
            {
                EnablePhantomMaterial();
            }
            else
            {
                EnablePhysicsMaterial();
            }
            PhantomMaterialMode = value;
        }
    }

    public TimelineController FindTimelineController()
    {
        var iterator = this.transform;
        while (iterator != null)
        {
            var timeline_controller = iterator.GetComponent<TimelineController>();
            if (timeline_controller != null)
            {
                return timeline_controller;
            }
            iterator = iterator.parent;
        }
        return null;
    }

    public bool HasFieldOfView()
    {
        var obj = GetObject();
        return obj is Actor || obj is CameraObject;
    }

    void CreateTorsoVisualMarkIfNeed()
    {
        torso_position_object = transform.Find("TorsoPositionObject")?.gameObject;
        if (torso_position_object != null)
            return;

        // create sphere for torso position
        torso_position_object = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        torso_position_object.transform.parent = transform;
        torso_position_object.transform.localPosition = new Vector3(0, 0, 0);
        float r = 0.4f;
        torso_position_object.transform.localScale = new Vector3(r, r, r);
        torso_position_object.GetComponent<Renderer>().material.color = new Color(1, 1, 0, 1);
        torso_position_object.layer = (int)Layers.EFFECTS_LAYER;
        torso_position_object.name = "TorsoPositionObject";
    }

    public virtual void ManualAwake()
    {
        CreateTorsoVisualMarkIfNeed();

        on_init_pose = new Pose(transform.position, transform.rotation);
        _model = transform.Find("Model")?.gameObject;
        _timeline_controller = FindTimelineController();
        InitLists();

        //InitEmmissionMode();
        if (_phantom_material == null)
            InitPhantomMaterial();

        //InitPrediction();
        InitViewMarkerLine();

        if (_timeline_controller == null)
        {
            _timeline_controller = FindTimelineController();
        }

        InitObjectController(_timeline_controller.GetTimeline());

        _camera = transform.Find("CameraOfHero")?.GetComponent<Camera>();

        MakeHearEffectCylinder();
        _cached_fog_of_war = GameCore.GetChronosphereController().FogOfWar;

        ChronosphereController.instance.FogOfWarChanged += SetFogOfWar;
    }

    public void MakeHearEffectCylinder()
    {
        var sound_effect_cylinder = transform.Find("SoundEffectCylinder");
        if (sound_effect_cylinder != null)
        {
            _sound_effect = sound_effect_cylinder.GetComponent<SoundEffectView>();
            _sound_effect.Hide();
            _sound_effect.gameObject.layer = 13;
        }
        else
        {
            var _sound_effect_go = MaterialKeeper.Instance.Instantiate("SoundEffectPrefab");
            _sound_effect = _sound_effect_go.GetComponent<SoundEffectView>();
            _sound_effect.transform.parent = transform;
            _sound_effect.transform.localPosition = new Vector3(0, 0, 0);
            _sound_effect.Hide();
            _sound_effect.name = "SoundEffectCylinder";
            _sound_effect.gameObject.layer = 13;
        }
    }

    public virtual void InitObjectController(ITimeline timeline)
    {
        var obj = CreateObject<PhysicalObject>(gameObject.name, timeline);
        InitVariables(obj);
        obj.DisableBehaviour();
    }

    protected void InitVariables(ObjectOfTimeline obj)
    {
        obj.SetName(this.gameObject.name);

        //if (IsHero)
        //	obj.MarkAsHero();

        obj.SetObjectTimeReferencePoint(0, ReverseOnStart);
        obj.UseSurfaceNormalForOrientation = UseNormalAsUp;
        obj.Steering = Steering;
        obj.SetWalkableWalls(WalkableWalls);
        obj.SetHasCamera(true);
        obj.HasSpecificInteractionPose = UseInteractionPosition;
    }

    public virtual void InitSecondPhase() { }

    public T CreateObject<T>()
        where T : ObjectOfTimeline, new()
    {
        return CreateObject<T>(gameObject.name, _timeline_controller.GetTimeline());
    }

    void InitViewMarkerLine()
    {
        var go = new GameObject("ViewMarkerLine");
        _view_marker_line = go.AddComponent<LineRenderer>();
        _view_marker_line.startWidth = 0.1f;
        _view_marker_line.endWidth = 0.1f;
        _view_marker_line.material = MaterialKeeper.Instance.GetMaterial("ViewMarkerLine");
        _view_marker_line.material.color = Color.red;
        _view_marker_line.positionCount = 2;
        // hide
        _view_marker_line.SetPosition(0, Vector3.zero);
        _view_marker_line.SetPosition(1, Vector3.zero);
        _view_marker_line.enabled = false;

        // disable shadow
        _view_marker_line.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
    }

    Transform FindChildWithSubstringInName(Transform trsf, string substring)
    {
        // deep find child with substring in name
        foreach (Transform child in trsf)
        {
            if (child.name.Contains(substring))
            {
                return child;
            }
            else if (child.childCount > 0)
            {
                var child_result = FindChildWithSubstringInName(child, substring);
                if (child_result != null)
                    return child_result;
            }
        }

        return null;
    }

    public void FindSubobjectsTransforms()
    {
        if (_head_transform == null)
            _head_transform = FindChildWithSubstringInName(transform, "Head");

        if (_torso_transform == null)
            _torso_transform = FindChildWithSubstringInName(transform, "Spine");

        if (_gun_transform == null)
            _gun_transform = FindChildWithSubstringInName(transform, "Gun");
    }

    public void SetViewMarkerLine(Vector3 start, Vector3 end)
    {
        _view_marker_line.SetPosition(0, start);
        _view_marker_line.SetPosition(1, end);
        _view_marker_line.enabled = true;
    }

    public Vector3 CameraPosition()
    {
        var obj = GetObject();
        var camera = obj.CameraPose();
        return camera.position;
    }

    public void HideViewMarkerLine()
    {
        _view_marker_line.enabled = false;
    }

    public DistructStatus DistructLevel()
    {
        var actor = GetObject();
        var aicontroller = actor.AiController();
        if (aicontroller == null)
            return new DistructStatus(0, DistructStateEnum.Green);
        var level = (aicontroller as BasicAiController).DistructLevel();
        return level;
    }

    public void DeepFindChilds_(Transform obj, MyList<GameObject> childs)
    {
        if (obj == null)
            return;

        if (obj.gameObject.activeSelf == false)
            return;

        if (obj != transform && obj.GetComponent<ObjectController>() != null)
            return;

        if (obj.gameObject.activeSelf == false)
            return;

        foreach (Transform child in obj)
        {
            childs.Add(child.gameObject);
            DeepFindChilds_(child, childs);
        }
    }

    public MyList<GameObject> DeepFindChilds(Transform parent)
    {
        MyList<GameObject> childs = new MyList<GameObject>();
        DeepFindChilds_(parent, _list_subchilds);
        return childs;
    }

    public void InitPhantomMaterial()
    {
        _phantom_material = new Material(Shader.Find("Unlit/PhantomShd"));
        _phantom_material_mode = false;
    }

    public void EnablePhantomMaterial()
    {
        foreach (Renderer renderer in _renderers)
        {
            renderer.material = _phantom_material;
        }
        _phantom_material_mode = true;
    }

    public void EnablePhysicsMaterial()
    {
        for (int i = 0; i < _renderers.Count; ++i)
        {
            _renderers[i].material = _materials[i];
        }
        _phantom_material_mode = false;
    }

    void FindRenderersInChilds_(Transform trsf, List<Renderer> renderers)
    {
        if (trsf.gameObject.activeSelf == false)
            return;

        foreach (Transform child in trsf)
        {
            var promise_mark = child.GetComponent<PromiseMark>();
            if (promise_mark != null)
            {
                continue;
            }

            bool ignored =
                child.name == "Vosklicatel(Clone)"
                || child.name == "Ability.GunRenderer"
                || child.name == "StunEffectPrefab(Clone)"
                || child.name == "SoundEffectCylinder";
            if (ignored)
            {
                continue;
            }

            Renderer collider = child.GetComponent<Renderer>();
            if (collider != null && child.gameObject.activeSelf != false)
            {
                renderers.Add(collider);
            }
            FindRenderersInChilds_(child, renderers);
        }
    }

    void FindRenderersInChilds()
    {
        List<Renderer> renderers = new List<Renderer>();
        FindRenderersInChilds_(this.transform, renderers);
        _renderers = new MyList<Renderer>(renderers);
    }

    void FindCollidersInChilds_(Transform trsf, List<Collider> colliders)
    {
        foreach (Transform child in trsf)
        {
            var promise_mark = child.GetComponent<PromiseMark>();
            if (promise_mark != null)
            {
                continue;
            }

            Collider collider = child.GetComponent<Collider>();
            if (collider != null)
            {
                colliders.Add(collider);
            }
            FindCollidersInChilds_(child, colliders);
        }
    }

    void FindCollidersInChilds()
    {
        List<Collider> colliders = new List<Collider>();
        FindCollidersInChilds_(this.transform, colliders);
        _colliders = new MyList<Collider>(colliders);
    }

    void ExpandRenderBounds()
    {
        foreach (Renderer renderer in _renderers)
        {
            if (renderer is SkinnedMeshRenderer)
            {
                var skinned = renderer as SkinnedMeshRenderer;
                skinned.localBounds = new Bounds(Vector3.zero, new Vector3(4, 4, 4));
            }
        }
    }

    public void InstallTempreatureSubsystem(
        TimelineController timeline,
        Shader shader //,
    //Shader phantom_shader
    )
    {
        _temp_material = new Material(shader);
        _temp_material_setted = true;
        //_phantom_material = new Material(phantom_shader);
        CustomGlowSystem.instance.Add(
            timeline,
            this,
            _temp_material
        //, _phantom_material
        );
    }

    public Material TempMaterial()
    {
        return _temp_material;
    }

    public void InitLists()
    {
        _list_subchilds.Clear();
        _renderers.Clear();
        _materials.Clear();

        _list_subchilds = DeepFindChilds(transform.Find("Model"));
        FindRenderersInChilds();
        FindCollidersInChilds();

        ExpandRenderBounds();
    }

    public ObjectOfTimeline GetObject()
    {
        return _object_proxy.Object();
    }

    public ObjectOfTimeline guard()
    {
        return GetObject();
    }

    public Actor GetActor()
    {
        return _object_proxy.Object() as Actor;
    }

    public Actor TryGetActor()
    {
        return _object_proxy.TryGetObject() as Actor;
    }

    public ObjectOfTimeline TryGetObject()
    {
        return _object_proxy.TryGetObject();
    }

    public void SetObject(ObjectOfTimeline obj)
    {
        _object_proxy.AttachTo(obj.Name(), obj.GetTimeline());
    }

    ObjectId EvaluateFrame(bool with_correction)
    {
        var platform_area_base = GameCore.FindInParentTree<PlatformAreaBase>(gameObject);
        if (platform_area_base != null)
        {
            var is_platform = platform_area_base.IsPlatform;
            if (is_platform)
            {
                return new ObjectId(platform_area_base.ObjectReference.name);
            }
        }
        return default(ObjectId);
    }

    public T CreateObject<T>(string name, ITimeline tl)
        where T : ObjectOfTimeline, new()
    {
        _object_proxy = new ObjectProxy(name, tl);
        var obj = _object_proxy.CreateObject<T>(name, tl);
        obj.PreEvaluate();
        obj.SetMaterial(!AnigilatedOnStart);
        return obj;
    }

    RotaryProgressBarView GetStunEffect()
    {
        if (StunEffect == null)
        {
            StunEffect = this.FindInChildOrCreate(
                    "StunEffect",
                    prefab: MaterialKeeper.Instance.GetPrefab("StunEffectPrefab")
                )
                .GetComponent<RotaryProgressBarView>();
            StunEffect.transform.parent = transform;
            StunEffect.transform.localPosition = new Vector3(0, 2.6f, 0);
            StunEffect.Hide();
        }
        return StunEffect;
    }

    public TimelineController GetTimelineController()
    {
        return _timeline_controller;
    }

    public void AttachToTimeline(ITimeline tl, bool paranoid = false)
    {
        if (_object_proxy == null)
            _object_proxy = new ObjectProxy(name, tl);

        _object_proxy.AttachTo(gameObject.name, tl);
        if (paranoid)
            if (_object_proxy.HasObject() == false)
            {
                gameObject.SetActive(false);
            }
            else
            {
                gameObject.SetActive(true);
            }

        //_object_proxy.Object().SetBodyPartsPose(this);
    }

    public ObjectProxy ObjectProxy()
    {
        return _object_proxy;
    }

    void UpdateViewPhase2(ObjectOfTimeline guard)
    {
        if (PhantomMaterialMode != PhantomMaterialMode_Last)
        {
            PhantomMaterialModeProperty = PhantomMaterialMode;
            PhantomMaterialMode_Last = PhantomMaterialMode;
        }

        if (guard.IsTimeParadox())
        {
            //var time = _timeline_controller.GetTimeline().CurrentStep() / 240.0f;
            //var sin = Mathf.Sin(time * 2 * Mathf.PI / error_period) / 2 + 0.5f;
            //SetEmmissionIntensivity(sin * error_amplitude);
        }
        else
        {
            //SetEmmissionIntensivity(0);
        }
    }

    void Update()
    {
        if (torso_position_object != null)
            torso_position_object.transform.position = GetTorsoGlobalPosition();
    }

    public void InitAbilities()
    {
        var actions = GetComponents<MonoBehaviourAction>();
        foreach (var action in actions)
        {
            try
            {
                action.Init();
            }
            catch (Exception e)
            {
                Debug.LogError("InitAbilitiesForObjectController: " + e.Message);
            }
        }
    }

    public void UpdateDistruct()
    {
        if (_don_react_on_distruct)
            return;

        ObjectOfTimeline _guard = GetObject();
        var ai = (_guard.AiController() as BasicAiController);
        if (ai != null)
        {
            var distruct_on_this_step = ai.IsYellowDistruct() || ai.IsRedDistruct();

            if (distruct_on_this_step)
            {
                var fov_tester = GameObject.Find("FOVTester").GetComponent<FOVTesterController>();
                fov_tester.ProgramAttachTo(gameObject);
            }
        }
    }

    public float CurrentTimeModifier(ObjectOfTimeline guard)
    {
        return guard.CurrentTimeMultiplier();
    }

    public bool IsHighlighted(ObjectOfTimeline _guard)
    {
        bool pointer_highlighted = HoverredObjectName.name == _guard.Name();
        bool global_enabled = _is_outline_mode_enabled;
        return global_enabled || pointer_highlighted || is_selected;
    }

    public virtual OutlineColor OutlineColorMode(ObjectOfTimeline _guard)
    {
        bool is_highlighted = IsHighlighted(_guard);
        if (!is_highlighted)
            return OutlineColor.None;

        if (_guard == null)
            return OutlineColor.Black;

        bool is_hero = _guard.IsHero();

        if (is_hero)
            return OutlineColor.Green;

        var ai = _guard.AiController();
        if (ai == null)
            return OutlineColor.Yellow;

        bool is_ai_enabled = ai.IsEnabled();

        return is_ai_enabled ? OutlineColor.Red : OutlineColor.Violent;
    }

    float OutlineColorToFloatCode(OutlineColor color)
    {
        switch (color)
        {
            case OutlineColor.Hide:
                return -1.0f;
            case OutlineColor.Red:
                return 0.1f;
            case OutlineColor.Yellow:
                return 0.2f;
            case OutlineColor.Violent:
                return 0.3f;
            case OutlineColor.Black:
                return 0.4f;
            case OutlineColor.Green:
                return 0.5f;
            case OutlineColor.Cyan:
                return 0.6f;
        }
        return 0;
    }

    void SetDirection(Vector3 direction)
    {
        var rotation = Quaternion.LookRotation(direction);
        this.transform.rotation = rotation;
    }

    bool IsNeedDraw(ObjectOfTimeline guard, bool force_hide = false)
    {
        // TODO: Проверить на многократный вызов. Закешировать результат.

        bool in_broken_interval = guard.InBrokenInterval();
        if (!in_broken_interval)
        {
            return false;
        }

        if (force_hide)
            return false;

        var result =
            !guard.IsHide()
            && (_cached_fog_of_war == false || guard.AnybodyCanSeeMe() == CanSee.See);

        //Debug.Log("IsNeedDraw: " + name + " " + result);
        return result;
    }

    public bool IsNeedHide(ObjectOfTimeline guard, bool force_hide = false)
    {
        if (force_hide)
            return true;
        return !IsNeedDraw(guard);
    }

    public void UpdateTempreature(ObjectOfTimeline guard)
    {
        if (_temp_material_setted)
        {
            if (IsNeedDraw(guard))
            {
                _temp_material.SetFloat("_Temperature", CurrentTimeModifier(guard));
                _temp_material.SetFloat(
                    "OutlineColorMode",
                    OutlineColorToFloatCode(OutlineColorMode(guard))
                );
            }
            else
            {
                _temp_material.SetFloat("_Temperature", 0.0f);
                _temp_material.SetFloat(
                    "OutlineColorMode",
                    OutlineColorToFloatCode(OutlineColor.Hide)
                );
            }
        }
    }

    public ObjectOfTimeline GetObjectGlobal()
    {
        var current_timeline = GameCore.CurrentTimelineController().GetTimeline();
        var obj = current_timeline.GetObject(name);
        return obj;
    }

    [ContextMenu("PrintCommandList")]
    public void PrintCommandList()
    {
        var obj = GetObjectGlobal();
        var command_buffer = obj.CommandBuffer();
        if (command_buffer == null)
        {
            Debug.Log("CommandBuffer is null");
            return;
        }
        var commands = command_buffer.GetCommandQueue().AsList();
        foreach (var command in commands)
        {
            Debug.Log(command.ToString());
        }

        var current_command = command_buffer.GetCommandQueue().Current();
        if (current_command != null)
        {
            Debug.Log("Current command: " + current_command.ToString());
        }
    }

    protected void UpdateStunEffect(ObjectOfTimeline guard)
    {
        if (_don_react_on_distruct)
        {
            GetStunEffect().Hide();
            return;
        }

        if (guard.IsDead || guard.IsPreDead || guard.IsHide())
        {
            GetStunEffect().Hide();
            return;
        }

        if (guard.IsStunned())
        {
            GetStunEffect().Show();
            var main_camera = Camera.main;
            var main_camera_position = main_camera.transform.position;
            // rotate VosklicatelReaction to camera direction
            var direction = main_camera_position - transform.position;
            //direction.y = 0;
            GetStunEffect().transform.rotation = Quaternion.LookRotation(direction);
            GetStunEffect().SetProgressValue(guard.StunPart01());
        }
        else
        {
            GetStunEffect().Hide();
        }
    }

    public SpeedStruct GetSpeedStruct()
    {
        var animate_controller = GetComponent<AnimateController>();
        if (animate_controller != null)
        {
            return animate_controller.GetSpeedStructFromAnimations();
        }
        return new SpeedStruct();
    }

    public void UpdateCameraPose(ObjectOfTimeline guard)
    {
        if (_camera != null && guard is PhysicalObject)
        {
            var camera_pose = (guard as PhysicalObject).CameraPose();
            _camera.transform.SetPositionAndRotation(camera_pose.position, camera_pose.rotation);
        }
    }

    public void UpdateEffects(ObjectOfTimeline guard)
    {
        UpdateStunEffect(guard);
        UpdateSoundEffect();
    }

    public virtual void UpdateView()
    {
        var guard = GetObject();
        UpdateTempreature(guard);
        UpdateViewPhase2(guard);
        UpdateHideOrMaterial(guard);
        UpdateEffects(guard);
        //UpdatePredictionObject(guard);

        var pose = guard.PoseProphet();
        this.transform.position = pose.position;
        this.transform.rotation = pose.rotation;
        UpdateCameraPose(guard);
    }

    public virtual void UpdateViewTimeSpirits(Pose InversePose)
    {
        if (HideInTimeSpiritMode)
        {
            HideAllRenderers();
            DisableColliders();
            ShowLinkedInTimeWithObject(false);
            return;
        }

        var guard = GetObject();
        //UpdateTempreature(guard);
        UpdateViewPhase2(guard);
        UpdateHideOrMaterial(guard);
        //UpdateEffects(guard);

        var pose = guard.PoseProphet();
        pose = InversePose * pose;
        this.transform.position = pose.position;
        this.transform.rotation = pose.rotation;
        //UpdateCameraPose(guard);
    }

    public void UpdatePosition()
    {
        var guard = GetObject();
        var pose = guard.GlobalPose();
        this.transform.position = pose.position;
        this.transform.rotation = pose.rotation;
        UpdateCameraPose(guard);
    }

    public virtual void ShowLinkedInTimeWithObject(bool show)
    {
        //_linked_in_time_with_object.SetActive(show);
    }

    // void HideModel()
    // {
    // 	_model.SetActive(false);
    // 	torso_position_object.SetActive(false);
    // }

    // void ShowModel()
    // {
    // 	_model.SetActive(true);
    // 	ShowAllRenderers();
    // 	torso_position_object.SetActive(true);
    // }

    public virtual void UpdateHideOrMaterial(
        ObjectOfTimeline guard,
        bool force_hide = false,
        bool always_visible = false
    )
    {
        if (AlwaysVisible)
            return;

        if (_model == null)
            return;

        bool need_hide = IsNeedHide(guard);

        if (always_visible)
            need_hide = false;

        if (IsRenderersActive() && need_hide)
        {
            HideAllRenderers();
            DisableColliders();
            ShowLinkedInTimeWithObject(false);
        }
        else if (!IsRenderersActive() && !need_hide)
        {
            ShowAllRenderers();
            EnableColliders();
            ShowLinkedInTimeWithObject(true);
        }
    }

    public void EnableColliders()
    {
        foreach (var collider in _colliders)
        {
            collider.enabled = true;
        }
    }

    public void DisableColliders()
    {
        foreach (var collider in _colliders)
        {
            collider.enabled = false;
        }
    }

    //[ContextMenu("RemoveThisObject")]
    public void RemoveThisObject()
    {
        (GetObject().GetTimeline() as Timeline).RemoveObject(GetObject());
    }

    public static void NoOneHovered()
    {
        HoverredObjectName = default;
    }

    public void OnHover()
    {
        var myid = new ObjectId(name);
        OnHoverEventHook?.Invoke();
    }

    public void UpdateSoundEffect()
    {
        if (AlwaysVisible)
            return;

        if (_sound_effect == null)
            return;

        if (_don_react_on_distruct)
        {
            _sound_effect.Hide();
            return;
        }

        if (GetObject().HearOnly() && _cached_fog_of_war == true)
        {
            _sound_effect.Show();
        }
        else
        {
            _sound_effect.Hide();
        }
    }

    public bool IsRenderersActive()
    {
        if (_model == null)
            return false;

        if (_renderers.Count == 0)
            return false;

        return _renderers[0].enabled;
    }

    public bool IsModelActive()
    {
        if (_model == null)
            return false;

        return _model.activeSelf;
    }

    public void InvokeAwake() => ManualAwake();

    public void InvokeStart() { }

    bool IsCameraCanSeeMe(Camera cam, float delta = 0.05f)
    {
        var position = transform.position;
        var viewport = cam.WorldToViewportPoint(position);
        return (
            viewport.x > -delta
            && viewport.x < 1 + delta
            && viewport.y > -delta
            && viewport.y < 1 + delta
        );
    }

    public void SetupFrame(bool try_to_find_frame)
    {
        if (_timeline_controller == null)
        {
            _timeline_controller = FindTimelineController();
        }

        ObjectId frame = default(ObjectId);
        if (try_to_find_frame)
            frame = EvaluateFrame(with_correction: true);
        SetPoseFromView(frame);
    }

    public void SetPoseFromView(ObjectId frame)
    {
        var obj = GetObject();
        if (obj is PhysicalObject)
        {
            var physical = obj as PhysicalObject;
            var referencedPose = ReferencedPose.FromGlobalPose(
                new Pose(transform.position, transform.rotation),
                frame,
                _timeline_controller.GetTimeline()
            );
            physical.SetPose(referencedPose);
        }

        obj.PreEvaluate();
    }

    public Transform GetTorsoObject()
    {
        return _torso_transform;
    }

    [ContextMenu("Info")]
    void Info()
    {
        Debug.Log("ObjectController: " + name);
        Debug.Log(
            "fourd: "
                + GetObject().fourd_start
                + " "
                + GetObject().fourd_finish
                + "current_broken: "
                + GetObject().BrokenStep()
        );
        Debug.Log("in_broken_interval: " + GetObject().InBrokenInterval());
        Debug.Log("in_need_draw: " + IsNeedDraw(GetObject()));

        var curtl = GameCore.CurrentTimelineController().GetTimeline();
        var obj = curtl.GetObject(name);
        if (obj == null)
        {
            Debug.Log("Object not found in timeline");
            return;
        }
        Debug.Log("anims: " + obj.Animatronics().Count);
        Debug.Log("changes: " + obj.Changes.Count);
        if (obj.CommandBuffer() == null)
        {
            Debug.Log("CommandBuffer is null");
        }
        else
            Debug.Log("commands: " + obj.CommandBuffer().GetCommandQueue().Count);
    }

    public Transform GetHeadObject()
    {
        return _head_transform;
    }

    // public Transform GetGunObject()
    // {
    // 	return _gun_transform;
    // }

    public Vector3 GetTorsoGlobalPosition()
    {
        return GetObject().TorsoPosition();
    }

    public Transform GetCameraObject()
    {
        if (_camera_transform == null)
            return GetHeadObject();
        return _camera_transform;
    }

    public Pose GetCameraPose()
    {
        if (_camera_transform == null)
            return GetHead();

        return new Pose(_camera_transform.position, _camera_transform.rotation);
    }

    public bool HasCameraSlot()
    {
        return _camera_transform != null;
    }

#if UNITY_EDITOR
    public void OnApplicationQuit()
    {
        var scene_name = UnityEngine.SceneManagement.SceneManager.GetActiveScene().name;
        var dn = Application.streamingAssetsPath + "/ObjectsTMP/";
        var dirname = dn + scene_name + "/";
        var store_path = dirname + name + ".json";

        if (!System.IO.File.Exists(dn))
        {
            System.IO.Directory.CreateDirectory(dn);
        }

        if (!System.IO.File.Exists(dirname))
        {
            System.IO.Directory.CreateDirectory(dirname);
        }

        try
        {
            var obj = GetObject();
        }
        catch (Exception)
        {
            return;
        }

        BotInfoForSerialize bot_info = new BotInfoForSerialize(
            PrefabLabel,
            name,
            //obj.GlobalPose(),
            on_init_pose
        );

        if (PrefabLabel != null && PrefabLabel != "")
        {
            var trent = bot_info.ToTrent();
            var json = SimpleJsonParser.SerializeTrent(trent);
            System.IO.File.WriteAllText(store_path, json);
        }
        else
        {
            System.IO.File.WriteAllText(store_path, "null");
        }
    }

    [MenuItem("Tools/ObjectController/FindPrefabsForTemporarlyObjects")]
    public static void FindPrefabsForTemporarlyObjects()
    {
        var scene_name = UnityEngine.SceneManagement.SceneManager.GetActiveScene().name;
        var dn = Application.streamingAssetsPath + "/ObjectsTMP/";
        var dirname = dn + scene_name + "/";

        // find all files in directory
        var files = System.IO.Directory.GetFiles(dirname);

        foreach (var file in files)
        {
            var file_name = System.IO.Path.GetFileName(file);
            // file must be json
            if (file_name.EndsWith(".json") == false)
                continue;

            Debug.Log("File: " + file);
            var json = System.IO.File.ReadAllText(file);
            if (json == "null")
                continue;

            var trent = SimpleJsonParser.DeserializeTrent(json);
            var bot_info = new BotInfoForSerialize();
            bot_info.FromTrent(trent);

            var prefab = MaterialKeeper.Instance.FindPrefabInList(bot_info.prefab_label);
            if (prefab == null)
            {
                Debug.Log("Prefab not found: " + bot_info.prefab_label);
                continue;
            }

            Debug.Log("Prefab found: " + bot_info.prefab_label);
            var name = bot_info.object_name;

            // is object exists in original timeline
            GameObject original_timeline = GameCore.GetOriginalTimelineGO();

            var probe = original_timeline.transform.Find(name);

            if (probe == null)
            {
                Debug.Log("Restore objects from editor data");

                var pos = bot_info.on_init_pose.position;
                var rot = bot_info.on_init_pose.rotation;
                var obj = GameObject.Instantiate(prefab, pos, rot);
                obj.name = name;
                obj.transform.parent = original_timeline.transform;
            }
        }
    }
#endif
}

public struct BotInfoForSerialize : ITrentCompatible
{
    public string prefab_label;
    public string object_name;

    //public Pose pose;
    public Pose on_init_pose;

    public BotInfoForSerialize(
        string prefab_label,
        string object_name,
        //Pose pose,
        Pose on_init_pose
    )
    {
        this.prefab_label = prefab_label;
        this.object_name = object_name;
        //this.pose = pose;
        this.on_init_pose = on_init_pose;
    }

    public void FromTrent(object trent)
    {
        var tr = trent as Dictionary<string, object>;
        prefab_label = tr["prefab_label"] as string;
        object_name = tr["object_name"] as string;
        //pose = new Pose();
        //pose.FromTrent(tr["pose"]);
        on_init_pose = new Pose();
        on_init_pose.FromTrent(tr["on_init_pose"]);
    }

    public object ToTrent()
    {
        var tr = new Dictionary<string, object>();
        tr["prefab_label"] = prefab_label;
        tr["object_name"] = object_name;
        //tr["pose"] = pose.ToTrent();
        tr["on_init_pose"] = on_init_pose.ToTrent();
        return tr;
    }
}
