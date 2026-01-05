using System;
using System.Collections;
using System.Collections.Generic;
using System.Threading;
#if UNITY_64
using UnityEngine;
using UnityEngine.Rendering;
#endif

struct TaskForPoolUpdate
{
    public string name;
    public GameObject instance_prototype;
    public Transform instance_subpool;
    //public MyList<GameObject> list;
}

public class ChronosphereController : MonoBehaviour
{
    public static ChronosphereController instance = null;

    public static ChronosphereController Instance => instance;

    IGravitySolver _gravity_solver;
    float PredictionTime = 1.5f;
    AbstractCameraController _camera_controller;

    bool _outline_mode_enabled = false;
    bool _instance_pool_initialized = false;
    CustomGlowRenderer _custom_glow_renderer;
    public bool SafetySpace = false;

    public bool FogOfWar = true;
    public event Action<bool> FogOfWarChanged;

    bool _editor_mode_enabled = false;
    public event Action<bool> EditorModeChanged;

    public bool RotateStantionMode = false;

    //public bool EnableGameLogic = true;

    public ControlableActor _selected_actor = null;

    //public TimelineController _selected_actor_timelinectr_lazy = null;

    ChronoSphere _chronosphere;
    TimelineController _current_timeline_controller;
    MyList<TimelineController> _timeline_controllers = new MyList<TimelineController>();
    int unique_id_counter = 0;
    Queue<TaskForPoolUpdate> _tasks_for_pool_update = new Queue<TaskForPoolUpdate>();

    Dictionary<string, GameObject> green_hologram = new Dictionary<string, GameObject>();

    //ControlableActor _selected_actor;
    bool _detect_time_paradox = false;

    //Dictionary<string, MyList<GameObject>> _instance_pool = new Dictionary<string, MyList<GameObject>>();
    MyList<string> _instance_pool_names = new MyList<string>();
    Dictionary<string, GameObject> _instance_prototype = new Dictionary<string, GameObject>();
    GameObject _instance_pool_object = null;

    MainCameraShaderFilter mainCameraShaderFilter;

    //float _last_pool_update_time = 0.0f;
    float level_start_time = 0.0f;

    //static Dictionary<int, PlatformView> Platforms = new Dictionary<int, PlatformView>();

    // static public void RegisterPlatform(PlatformView platform)
    // {
    // 	int area = platform.AreaNo();
    // 	if (area < 4)
    // 		Debug.LogError("Area is less than 4 name:" + platform.name + " area:" + area);
    // 	Platforms.Add(area, platform);
    // }

    public void ToggleFogOfWar()
    {
        FogOfWar = !FogOfWar;
        Shader.SetGlobalInt("FogOfWar", FogOfWar ? 1 : 0);

        // foreach (var timeline_controller in _timeline_controllers)
        // {
        // 	timeline_controller.SetFogOfWar(FogOfWar);
        // }
        FogOfWarChanged?.Invoke(FogOfWar);
    }

    // static public ObjectId GetPlatformName(int area_no)
    // {
    // 	PlatformView platform;
    // 	bool finded = Platforms.TryGetValue(area_no, out platform);
    // 	if (finded)
    // 		return new ObjectId(platform.FrameName());
    // 	return new ObjectId();
    // }

    // static public PlatformView GetPlatform(string name)
    // {
    // 	foreach (var platform in Platforms.Values)
    // 	{
    // 		if (platform.FrameName() == name)
    // 			return platform;
    // 	}
    // 	return null;
    // }

    public Dictionary<string, GameObject> InstancePool()
    {
        return _instance_prototype;
    }

    public TimelineController CurrentTimelineController()
    {
        return _current_timeline_controller;
    }

    public Shader GlowShader()
    {
        var shader = Shader.Find("ActorPass");
        return shader;
    }

    public Shader PhantomShader()
    {
        var shader = Shader.Find("ActorPass");
        return shader;
    }

    public TimelineController CreateEmptyTimeline()
    {
        var name_for_new_timeline = "Empty" + unique_id_counter.ToString();
        unique_id_counter += 1;

        // create new child object
        var new_timeline_object = new GameObject(name_for_new_timeline);
        new_timeline_object.transform.parent = transform;

        var ntc = new_timeline_object.AddComponent<TimelineController>();
        ntc.AttachToTimeline(new Timeline());
        ntc.SetTimelineName(name_for_new_timeline);

        Timeline tl = new Timeline();
        ntc.BindToTimeline(tl);
        AddTimelineToChronosphere(ntc);

        return ntc;
    }

    // public Vector3 UpForWorldPoint(Vector3 point)
    // {


    // 	if (RotateStantionMode)
    // 		return (-point).normalized;
    // 	else
    // 		return Vector3.up;
    // }

    public void InvokeAwake() => Awake();

    public void InvokeStart() => Start();

    void Start()
    {
        var original_timeline = _timeline_controllers[0];
        _chronosphere.set_current_timeline(original_timeline.GetTimeline());
        level_start_time = Time.time;

        foreach (Transform child in transform)
        {
            var timeline = child.gameObject.GetComponent<TimelineController>();
            timeline.ManualStart();
        }

        InitInstancePool();

        PredictionTime = PlayerPrefs.GetFloat("PredictionTime", 1.5f);

        if (FOVRenderFeature.Instance != null)
            FOVRenderFeature.Instance.ReInit();
        else
            FOVRenderFeature.OnCreate += () => FOVRenderFeature.Instance.ReInit();
    }

    public TimelineController CreateTimelineController(string name)
    {
        var new_timeline_object = new GameObject(name);
        new_timeline_object.transform.parent = transform;
        var timeline_controller = new_timeline_object.AddComponent<TimelineController>();
        //new_timeline_object.AddComponent<NetPointView>();
        _timeline_controllers.Add(timeline_controller);
        return timeline_controller;
    }

    TimelineController _time_spirit_timeline = null;
    Timeline _time_spirit_tl = null;

    void RecursiveRemoveGeometryMaps_(GameObject obj)
    {
        var geommap = obj.GetComponent<GeometryMapController>();
        if (geommap != null)
        {
            Destroy(geommap);
        }

        int childCount = obj.transform.childCount;
        for (int i = 0; i < childCount; ++i)
        {
            RecursiveRemoveGeometryMaps_(obj.transform.GetChild(i).gameObject);
        }
    }

    void RecursiveRemoveGeometryMaps(GameObject obj)
    {
        RecursiveRemoveGeometryMaps_(obj);
    }

    public TimelineController CreateCurrentTimelineCopy(string name)
    {
        var curtimeline = _current_timeline_controller;
        var copyctr = GameObject.Instantiate(curtimeline.gameObject);
        RecursiveRemoveGeometryMaps(copyctr);
        copyctr.name = name;
        return copyctr.GetComponent<TimelineController>();
    }

    public void EnableTimeSpiritTimeline()
    {
        if (_time_spirit_timeline != null)
        {
            _time_spirit_timeline.gameObject.SetActive(true);
        }
        else
        {
            _time_spirit_timeline = CreateCurrentTimelineCopy("time_spirit");
            _time_spirit_timeline.transform.parent = this.transform;
            _time_spirit_timeline.SetLateAwakeStart(true);
            _time_spirit_timeline.RemovePartsForTimeSpirit();
            _time_spirit_timeline.SetAllMaterialsToGreenHologram();
            _time_spirit_timeline.InitObjCtrLists();

            _timeline_controllers.Add(_time_spirit_timeline);
        }

        var tlcopy = Chronosphere().CurrentTimeline().Copy();
        tlcopy.IsTimeSpirit = true;
        Chronosphere().AddTimeline(tlcopy);
        _time_spirit_timeline.BindToTimeline2(tlcopy);
        _start_timespirit_time = Time.time - level_start_time;
        //_time_spirit_timeline.ManualAwake();
        //_time_spirit_timeline.ManualStart();


        _time_spirit_tl = tlcopy;
        var curtl = CurrentTimelineController().GetTimeline();

        _time_spirit_timeline.PromoteToStepAndView(curtl.CurrentStep() + 1);
    }

    public void DisableTimeSpiritTimeline()
    {
        if (_time_spirit_timeline != null)
            _time_spirit_timeline.gameObject.SetActive(false);

        var tl = _time_spirit_timeline.GetTimeline();
        _time_spirit_timeline.UnbindTimeline();
        GetChronosphere().RemoveTimeline(tl);
        _time_spirit_tl = null;
    }

    void OnDestroy()
    {
        instance = null;
    }

    void InitPlatforms()
    {
        NavMeshLinkSupervisor.Instance.InitPlatforms();
        // find all PlatformView
        //var platforms = GameObject.FindObjectsByType<PlatformView>(FindObjectsSortMode.None);
        //foreach (var platform in platforms)
        // {
        // 	//RegisterPlatform(platform);
        // }
    }

    // void InitNavMeshColliders()
    // {
    // 	var nav_mesh_colliders = GameObject.FindObjectsByType<NavMeshSurfaceDrawer>(FindObjectsSortMode.None);
    // 	foreach (var nav_mesh_collider in nav_mesh_colliders)
    // 	{
    // 		nav_mesh_collider.Init();
    // 	}
    // }

    void InitMaterials()
    {
        var materials = GameObject.FindObjectsByType<MaterialKeeper>(FindObjectsSortMode.None);
        foreach (var material in materials)
        {
            material.Init();
        }
    }

    // void InitClimbingBlocks()
    // {
    // 	var climbing_blocks = GameObject.FindObjectsByType<ClimbingBlock>();
    // 	foreach (var climbing_block in climbing_blocks)
    // 	{
    // 		climbing_block.Init();
    // 	}
    // }

    public float MainGravityLevel = 1.0f;

    public Vector3 GetGravityInGlobalPoint(Vector3 point, ObjectId platformId)
    {
        if (platformId == default(ObjectId))
            return Vector3.down * 9.81f * MainGravityLevel;

        var platform = CurrentTimelineController()
            .GetObject(platformId)
            .GetComponent<PlatformAreaBase>();
        if (platform == null)
            return Vector3.down * 9.81f * MainGravityLevel;
        return platform.GetGravity(point);
    }

    public Vector3 GetGravityInGlobalPoint(Vector3 point, PlatformAreaBase platform)
    {
        if (platform == null)
            return Vector3.down * 9.81f * MainGravityLevel;
        return platform.GetGravity(point);
    }

    IGravitySolver FindGravitySolver()
    {
        var all_objects = GameObject.FindObjectsByType<GameObject>(FindObjectsSortMode.None);
        foreach (var obj in all_objects)
        {
            var solver = obj.GetComponent<IGravitySolver>();
            if (solver != null)
                return solver;
        }
        return null;
    }

    void Awake()
    {
        instance = this;
        _gravity_solver = FindGravitySolver();
        _camera_controller = Camera.main.GetComponent<AbstractCameraController>();
        _custom_glow_renderer = GameObject.Find("Main Camera").GetComponent<CustomGlowRenderer>();
        mainCameraShaderFilter = GameObject.FindFirstObjectByType<MainCameraShaderFilter>();

        InitMaterials();
        InitPlatforms();
        //InitNavMeshColliders();
        //InitClimbingBlocks();

        TimelineController original_timeline = null;
        foreach (Transform child in transform)
        {
            var name = child.gameObject.name;
            var timeline = child.gameObject.GetComponent<TimelineController>();

            if (name == "Original")
            {
                original_timeline = timeline;
            }
            timeline.ManualAwake();
            _timeline_controllers.Add(timeline);
        }

        InitChronosphere();

        _chronosphere.SetDropTimeOnEdit(false);
        Shader.SetGlobalInt("FogOfWar", FogOfWar ? 1 : 0);
    }

    public void DetectStartParradoxOnUpdate()
    {
        _detect_time_paradox = true;
    }

    public void InitChronosphere()
    {
        _chronosphere = new ChronoSphere();

        TimelineController original_timeline = _timeline_controllers[0];
        //original_timeline.CreateTimeline();
        //original_timeline.SetChronosphereController(this);

        // foreach (TimelineController timeline in _timeline_controllers)
        // {
        // 	if (timeline == null)
        // 	{
        // 		Debug.Log("Timeline is null??");
        // 		return;
        // 	}

        // 	timeline.MakeGuards();

        // 	timeline.SetChronosphereController(this);
        // 	timeline.BindTimelineGuards();
        // 	timeline.InitGlowSystem();
        // }

        _current_timeline_controller = original_timeline;

        // foreach (var name in _instance_pool_names)
        // {
        // 	var instance_subpool = _instance_pool_object.transform.Find(name);
        // }

        // _current_timeline_controller.InitGlowSystem();
        // if (_custom_glow_renderer != null)
        // 	_custom_glow_renderer.ResetCommandBuffer();

        BindCallbacks(_chronosphere);
    }

    public void OnObjectAddedToTimeline(ObjectOfTimeline obj)
    {
        if (obj.GetTimeline() != _chronosphere.CurrentTimeline())
            return;

        //_current_timeline_controller.CreateOrGetViewForObject(obj);
        _current_timeline_controller.OnObjectAdded(obj);
    }

    public void OnObjectRemovedFromTimeline(ObjectOfTimeline obj)
    {
        if (obj.GetTimeline() != _chronosphere.CurrentTimeline())
            return;

        _current_timeline_controller.OnObjectRemoved(obj);
    }

    public TimelineController GetTimelineController(ITimeline tl)
    {
        foreach (var timeline_controller in _timeline_controllers)
        {
            if (timeline_controller.GetTimeline() == tl)
            {
                return timeline_controller;
            }
        }
        return null;
    }

    public void InitInstancePool()
    {
        if (_instance_pool_initialized)
            return;
        _instance_pool_object = new GameObject("InstancePool");

        foreach (Transform timeline in transform)
        {
            // foreach (Transform guard in timeline)
            // {
            // 	if (_instance_pool_names.Contains(guard.gameObject.name))
            // 		continue;
            // 	_instance_pool_names.Add(guard.gameObject.name);
            // 	var prototype = guard.gameObject;
            // 	_instance_prototype.Add(guard.gameObject.name, prototype);
            // }

            TimelineController timelineController = timeline.GetComponent<TimelineController>();
            foreach (var objctr in timelineController._object_controllers)
            {
                if (_instance_pool_names.Contains(objctr.gameObject.name))
                    continue;
                _instance_pool_names.Add(objctr.gameObject.name);
                var prototype = objctr.gameObject;
                _instance_prototype.Add(objctr.gameObject.name, prototype);
            }
        }

        foreach (var name in _instance_pool_names)
        {
            // create subpool
            var subpool = new GameObject(name);
            subpool.transform.parent = _instance_pool_object.transform;
        }

        _instance_pool_initialized = true;
    }

    public void BindCallbacks(ChronoSphere chronosphere)
    {
        chronosphere.OnTimelineAdded += OnTimelineAdded;
        chronosphere.OnCurrentTimelineChanged += OnCurrentTimelineChanged;
        chronosphere.OnSelectedObjectChanged += OnSelectedObjectChanged;
        chronosphere.OnObjectAddedToTimeline += OnObjectAddedToTimeline;
        chronosphere.OnObjectRemovedFromTimeline += OnObjectRemovedFromTimeline;
    }

    public void OnSelectedObjectChanged(ObjectOfTimeline obj)
    {
        if (obj == null)
        {
            Debug.Log("Selected object is null");
            _selected_actor = null;
            return;
        }

        var actor = _current_timeline_controller.GetObject(obj).GetComponent<ControlableActor>();
        SetSelectedActor(actor);
    }

    public void SetSelectedActor(ControlableActor actor)
    {
        if (_selected_actor == actor)
            return;

        GetChronosphere().Select(actor.GetObject());
        if (_selected_actor != null)
            _selected_actor.GetComponent<ObjectController>().is_selected = false;
        _selected_actor = actor;
        if (_selected_actor != null)
            _selected_actor.GetComponent<ObjectController>().is_selected = true;
    }

    public ControlableActor SelectedActor()
    {
        return _selected_actor;
    }

    void OnTimelineAdded(ITimeline tl) { }

    public void ToggleEditorMode()
    {
        _editor_mode_enabled = !_editor_mode_enabled;
        EditorModeChanged?.Invoke(_editor_mode_enabled);
    }

    public bool IsEditorMode()
    {
        return _editor_mode_enabled;
    }

    public void EnableTimelineController(TimelineController timeline_controller)
    {
        timeline_controller.gameObject.SetActive(true);
    }

    void OnCurrentTimelineChanged(Timeline tl)
    {
        _current_timeline_controller.AttachToTimeline(tl, paranoid: true);
    }

    public ChronoSphere Chronosphere()
    {
        return _chronosphere;
    }

    public Timeline CurrentTimeline()
    {
        return _chronosphere.CurrentTimeline();
    }

    void OptimizeMeshRecurse(GameObject prototype, GameObject instance)
    {
        // TODO: Заменяет меш на инстансе на меш с прототипа
        // Проверить, даёт ли это какие-то преимущества
        // После начала плотной работы  с инстансами

        SkinnedMeshRenderer instance_mesh_comp;
        if (instance.TryGetComponent<SkinnedMeshRenderer>(out instance_mesh_comp))
        {
            SkinnedMeshRenderer prototype_mesh_comp;
            if (prototype.TryGetComponent<SkinnedMeshRenderer>(out prototype_mesh_comp))
            {
                instance_mesh_comp.sharedMesh = prototype_mesh_comp.sharedMesh;
            }
        }

        foreach (Transform child in prototype.transform)
        {
            var name = child.gameObject.name;
            var instance_child = instance.transform.Find(name);
            if (instance_child != null)
            {
                OptimizeMeshRecurse(child.gameObject, instance_child.gameObject);
            }
        }
    }

    public void DestroyTimeline(TimelineController tc)
    {
        _timeline_controllers.Remove(tc);
        _chronosphere.DestroyTimeline(tc.GetTimeline());
    }

    void OptimizeMesh(GameObject prototype, GameObject instance)
    {
        OptimizeMeshRecurse(prototype, instance);
    }

    GameObject InstatiateAndInit(GameObject instance_prototype, Transform instance_subpool)
    {
        var instance = GameObject.Instantiate(instance_prototype);
        instance.transform.position = new Vector3(0, 0, -100);
        instance.transform.parent = instance_subpool;
        instance.SetActive(false);
        instance.name = instance_prototype.name;
        var animcontr = instance.GetComponent<AnimateController>();
        if (animcontr != null)
            animcontr.SetAnimationsFromOtherObject(
                instance_prototype.GetComponent<AnimateController>()
            );
        OptimizeMesh(instance_prototype, instance);
        var rig_controller = instance.GetComponent<RigController>();
        if (rig_controller != null)
            rig_controller.Init();
        return instance;
    }

    public ChronoSphere GetChronosphere()
    {
        return _chronosphere;
    }

    public GameObject GetFromInstancePool(string name)
    {
        name = GameCore.WithoutPostfix(name);
        var list = _instance_pool_object.transform.Find(name);
        if (list == null)
            Debug.Log("Cannot found pool for " + name);

        var count = list.childCount;

        if (count == 0)
            return null;

        var instance = list.GetChild(count - 1).gameObject;
        instance.transform.parent = null;

        _tasks_for_pool_update.Enqueue(
            new TaskForPoolUpdate
            {
                name = name,
                instance_prototype = _instance_prototype[name],
                instance_subpool = _instance_pool_object.transform.Find(name),
            }
        );

        return instance;
    }

    public void AddTimelineToChronosphere(TimelineController timeline)
    {
        _timeline_controllers.Add(timeline);
    }

    public MyList<TimelineController> Timelines()
    {
        return _timeline_controllers;
    }

    public void CreateCopyOfCurrentTimeline()
    {
        _chronosphere.CreateCopyOfCurrentTimeline();
    }

    void Update()
    {
        var chronosphere_time = Chronosphere().CurrentTimeline().CurrentTime();

        FixedUpdateDoit();

        var main_camera = Camera.main;
        var camera_position = main_camera.transform.position;
        var view_matrix = main_camera.worldToCameraMatrix;
        var projection_matrix = main_camera.projectionMatrix;
        Shader.SetGlobalFloat("_CurrentTimelineTime", chronosphere_time);

        foreach (var timeline_controller in _timeline_controllers)
        {
            timeline_controller.UpdateView();
        }

        if (_time_spirit_tl != null)
        {
            UpdateViewTimeSpirits();
        }

        Raycaster.TestSightPhase(Chronosphere().CurrentTimeline());
    }

    void LateUpdate()
    {
        _camera_controller.LateUpdateImpl();
    }

    void UpdateViewTimeSpirits()
    {
        var active_timeline = Chronosphere().CurrentTimeline();
        var spirit_timeline = _time_spirit_tl;
        var refobj = _camera_controller.ReferenceObjectId();
        _time_spirit_timeline.UpdateViewTimeSpirits(
            active_timeline: active_timeline,
            time_spirit_timeline: spirit_timeline,
            reference_object_id: refobj
        );
    }

    float _start_timespirit_time = 0.0f;

    public void ResetTimeSpirit()
    {
        if (_time_spirit_tl != null)
        {
            DisableTimeSpiritTimeline();
            EnableTimeSpiritTimeline();
            _time_spirit_tl.Promote(CurrentTimeline().CurrentStep());
            UpdateViewTimeSpirits();
        }
    }

    void FixedUpdateDoit()
    {
        // update physics
        Physics.Simulate(Time.fixedDeltaTime);

        var chronosphere_time = Time.time - level_start_time;
        _chronosphere.UpdateForGameTime(chronosphere_time, Time.deltaTime);

        if (_detect_time_paradox)
        {
            _detect_time_paradox = false;
            var current_timeline = Chronosphere().CurrentTimeline();
            ParadoxStatus stat = current_timeline.CheckTimeParadox();
            if (stat == ParadoxStatus.ParadoxDetected)
            {
                Debug.Log("ParadoxDetected");
            }
            else
            {
                Debug.Log("NoParadox");
            }
        }

        var current_time = _chronosphere.CurrentTimeline().CurrentTime();

        var diff = (float)(chronosphere_time - _start_timespirit_time);
        var moddiff = diff % PredictionTime;
        //float alpha = moddiff / 2.5f;

        bool current_timeline_is_reversed = _chronosphere.CurrentTimeline().IsReversedPass();
        if (current_timeline_is_reversed)
            moddiff = -moddiff;
        if (_time_spirit_tl != null)
        {
            var t = current_time + moddiff + 0.5f;
            _time_spirit_tl.Promote((long)(t * Utility.GAME_GLOBAL_FREQUENCY));
        }
    }

    public GameObject GetCopyInstance(GameObject proto)
    {
        var copy = GetFromInstancePool(proto.name);
        return copy;
    }

    public GameObject GetCopyInstance(string name)
    {
        //var copy = GetFromInstancePool(name);
        GameObject copy = null;

        if (copy == null)
        {
            if (!_instance_prototype.ContainsKey(GameCore.WithoutPostfix(name)))
            {
                Debug.Log("Cannot found prototype for " + name);
                return null;
            }

            var prototype = _instance_prototype[GameCore.WithoutPostfix(name)];
            copy = InstatiateAndInit(prototype, _instance_pool_object.transform.Find(name));
        }

        return copy;
    }

    public TimelineController GetCurrentTimeline()
    {
        return _current_timeline_controller;
    }

    GameObject _current_green_hologram = null;

    void SetCurrentGreenHologram(GameObject obj)
    {
        if (_current_green_hologram == null)
        {
            _current_green_hologram = obj;
            return;
        }

        if (_current_green_hologram != obj)
        {
            _current_green_hologram.SetActive(false);
            _current_green_hologram = obj;
        }
    }

    public Tuple<GameObject, Material> MakeNonUnicalGreenHologram(GameObject obj)
    {
        var name = obj.name;

        var hologram = new GameObject("TimePhantomGreenHologram");
        var model = obj.transform.Find("Model");

        // set layer 13 recurse ("Effects")

        if (model == null)
        {
            //Debug.Log("Cannot find model for " + name);
            return null;
        }

        var hologram_model = GameObject.Instantiate(model.gameObject);
        hologram_model.name = "Model";
        hologram_model.transform.parent = hologram.transform;

        hologram.transform.position = obj.transform.position;
        hologram.transform.rotation = obj.transform.rotation;
        hologram.transform.localScale = obj.transform.localScale;
        hologram.SetActive(true);
        hologram_model.SetActive(true);
        //green_hologram.Add(name, hologram);

        hologram.AddComponent<RigController>();

        // Get material with GreehHologram name
        var material = MaterialKeeper.Instance.GetMaterial("GreenHologram");
        material = new Material(material);
        var subobjects = hologram_model.GetComponentsInChildren<Transform>();
        foreach (var subobject in subobjects)
        {
            // get render
            var render = subobject.gameObject.GetComponent<Renderer>();
            if (render != null)
            {
                // set material
                render.material = material;
            }
        }
        GameCore.SetLayerRecursevely(hologram, 13);
        GameCore.SetLayerRecursevely(hologram_model, 13);
        return new Tuple<GameObject, Material>(hologram, material);
    }

    public static void ChangeMaterialToGreenHologram_(
        GameObject gh,
        int change_layer,
        Material material,
        bool remove_render
    )
    {
        var objctr = gh.gameObject.GetComponent<ObjectController>();
        if (objctr != null)
        {
            remove_render = objctr.HideInTimeSpiritMode;
        }

        var render = gh.gameObject.GetComponent<Renderer>();
        if (render != null)
        {
            if (remove_render)
            {
                render.enabled = false;
                //Destroy(render);
            }
            else
                render.material = material;
        }

        if (change_layer != -1)
        {
            var collider = gh.gameObject.GetComponent<Collider>();
            if (collider != null)
            {
                collider.gameObject.layer = change_layer;
            }
        }

        int childCount = gh.transform.childCount;
        for (int i = 0; i < childCount; ++i)
        {
            ChangeMaterialToGreenHologram_(
                gh.transform.GetChild(i).gameObject,
                change_layer,
                material,
                remove_render
            );
        }
    }

    public static void ChangeMaterialToGreenHologram(GameObject gh, int change_layer = -1)
    {
        var material = MaterialKeeper.Instance.GetMaterial("GreenHologram");
        ChangeMaterialToGreenHologram_(gh, change_layer, material, false);
    }

    public GameObject GreenHologram(GameObject obj)
    {
        var name = obj.name;

        GameObject ghologram;
        if (green_hologram.TryGetValue(name, out ghologram))
        {
            SetCurrentGreenHologram(ghologram);
            ghologram.SetActive(true);
            return ghologram;
        }

        var hologram = new GameObject("GreenHologram");
        var model = obj.transform.Find("Model");
        var hologram_model = GameObject.Instantiate(model.gameObject);
        hologram_model.name = "Model";
        hologram_model.transform.parent = hologram.transform;
        //hologram.transform.parent = obj.transform;

        hologram.transform.position = obj.transform.position;
        hologram.transform.rotation = obj.transform.rotation;
        hologram.transform.localScale = obj.transform.localScale;
        hologram.SetActive(true);
        hologram_model.SetActive(true);
        green_hologram.Add(name, hologram);

        hologram.AddComponent<RigController>();

        // Get material with GreehHologram name
        ChangeMaterialToGreenHologram(hologram_model);

        SetCurrentGreenHologram(hologram);
        GameCore.SetLayerRecursevely(hologram, 13);
        GameCore.SetLayerRecursevely(hologram_model, 13);

        return hologram;
    }

    public void DisableCurrentGreenHologram()
    {
        if (_current_green_hologram != null)
        {
            _current_green_hologram.SetActive(false);
            _current_green_hologram = null;
        }
    }

    public void ToggleOutlineMode()
    {
        _outline_mode_enabled = !_outline_mode_enabled;
        _current_timeline_controller.SetOutlineMode(_outline_mode_enabled);
    }

    // public bool IsOutlineModeEnabled()
    // {
    // 	return _outline_mode_enabled;
    // }
}
