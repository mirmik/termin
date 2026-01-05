using System;
using System.Collections;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Threading.Tasks;
#if UNITY_64
using UnityEngine;
#endif

public class TimelineController : MonoBehaviour
{
    NetworkView _network_controller;
    Timeline _timeline;
    bool _prevent_on_awake_initialization = false;
    MyList<string> children_names = new MyList<string>();

    // bool _is_glow_enabled = true;
    // bool _is_phantom_enabled = false;

    bool _late_awake_start = false;

    public float StartTime = 0.0f;
    public bool StartReversed = false;
    bool ignore_start_time = false;

    public List<AnimateController> _animate_controllers = new List<AnimateController>();

    public MyList<ObjectController> _object_controllers = new MyList<ObjectController>();
    public Dictionary<string, ObjectController> _object_controllers_dict =
        new Dictionary<string, ObjectController>();
    public Dictionary<long, ObjectController> _object_controllers_hashes_dict =
        new Dictionary<long, ObjectController>();

    public void SetLateAwakeStart(bool en)
    {
        _late_awake_start = en;
    }

    public void IgnoreStartTime()
    {
        ignore_start_time = true;
    }

    public void InvokeAwake() => ManualAwake();

    public void InvokeStart() => Start();

    public ChronoSphere Chronosphere()
    {
        return ChronosphereController.instance.GetChronosphere();
    }

    public void UpdateViewTimeSpirits(
        Timeline active_timeline,
        Timeline time_spirit_timeline,
        ObjectId reference_object_id
    )
    {
        var reference_frame_active = active_timeline.GetFrame(reference_object_id);
        var reference_frame_time_spirit = time_spirit_timeline.GetFrame(reference_object_id);
        var diffframe = reference_frame_active * reference_frame_time_spirit.Inverse();

        List<ObjectController> to_remove = new List<ObjectController>();
        foreach (var objctr in _object_controllers)
        {
            if (!time_spirit_timeline.HasObject(objctr.name))
            {
                to_remove.Add(objctr);
            }
            else
                objctr.UpdateViewTimeSpirits(diffframe);
        }

        foreach (var objctr in to_remove)
        {
            _object_controllers.Remove(objctr);
            _object_controllers_dict.Remove(objctr.name);
            _object_controllers_hashes_dict.Remove(new ObjectId(objctr.name).hash);
            Destroy(objctr.gameObject);
        }

        UpdateAnimation();
    }

    public void UpdateView()
    {
        foreach (var objctr in _object_controllers)
        {
            objctr.UpdateView();
        }

        UpdateAnimation();
    }

    public void UnbindTimeline()
    {
        _timeline = null;
    }

    // Вызывается из сигнала
    public void SetOutlineMode(bool outline_mode)
    {
        foreach (var objctr in _object_controllers)
        {
            objctr.SetOutlineMode(outline_mode);
        }
    }

    public static Matrix4x4 ViewProjectionMatrix()
    {
        var main_camera = Camera.main;
        var view_matrix = main_camera.worldToCameraMatrix;
        var projection_matrix = main_camera.projectionMatrix;
        return projection_matrix * view_matrix;
    }

    void UpdateAnimation()
    {
        var view_projection_matrix = ViewProjectionMatrix();
        foreach (var objctr in _animate_controllers)
        {
            objctr.UpdateView(view_projection_matrix);
        }
    }

    public void OnObjectAdded(ObjectOfTimeline obj)
    {
        if (TimelineObjectHasGameObjectWithName(obj.Name()))
        {
            return;
        }

        var object_controller = CreateOrGetViewForObject(obj);
        var guard_view = object_controller.GetComponent<GuardView>();

        if (guard_view != null)
        {
            guard_view.InstallTempreatureSubsystem(
                this,
                GlowShader() //,
            //PhantomShader()
            );
        }
    }

    public void OnObjectRemoved(ObjectOfTimeline obj)
    {
        Debug.Log("OnObjectRemoved: " + obj.Name());
        var object_controller = GetObject(obj);
        if (object_controller != null)
        {
            object_controller.OnRemoveMeInvoke();
            _object_controllers.Remove(object_controller);
            _object_controllers_dict.Remove(obj.Name());
            _object_controllers_hashes_dict.Remove(obj.ObjectId().hash);
            _animate_controllers.Remove(object_controller.GetComponent<AnimateController>());
            Destroy(object_controller.gameObject);
        }
    }

    private bool TimelineObjectHasGameObjectWithName(string name)
    {
        foreach (Transform child in transform)
        {
            var name_child = child.gameObject.name;
            if (name_child == name)
            {
                return true;
            }
        }
        return false;
    }

    public MyList<ObjectController> GetGuardControllers()
    {
        return _object_controllers;
    }

    public MyList<ObjectController> Objects()
    {
        return _object_controllers;
    }

    void MakeUnicalName(Transform child)
    {
        var name_child = child.gameObject.name;
        while (children_names.Contains(name_child))
        {
            child.gameObject.name = name_child + "_1";
            name_child = child.gameObject.name;
        }
        children_names.Add(name_child);
    }

    public void InitObjCtrLists()
    {
        foreach (var objctr in _object_controllers)
        {
            objctr.InitLists();
        }
    }

    public void MakeGuardsForObjectController(Transform child, bool noinit)
    {
        if (!noinit)
            MakeUnicalName(child);

        var objctr = child.gameObject.GetComponent<ObjectController>();
        if (objctr != null)
        {
            if (!_object_controllers.Contains(objctr))
            {
                _object_controllers.Add(objctr);
                _object_controllers_dict[objctr.gameObject.name] = objctr;
                _object_controllers_hashes_dict[Utility.StringHash(objctr.gameObject.name)] =
                    objctr;

                var animate_controller = objctr.GetComponent<AnimateController>();
                if (animate_controller != null)
                {
                    _animate_controllers.Add(animate_controller);
                }
            }
        }

        if (!noinit)
            objctr.ManualAwake();
    }

    public void MakeGuardsForObjectControllerTree(Transform parent, bool noinit = false)
    {
        foreach (Transform child in parent)
        {
            if (child.TryGetComponent<ObjectController>(out var objctr))
                MakeGuardsForObjectController(child, noinit);
            MakeGuardsForObjectControllerTree(child, noinit);
        }
    }

    void SetupPositionAndFrames()
    {
        foreach (var objctr in _object_controllers)
        {
            bool try_to_find_frame = objctr.GetComponent<GuardView>() != null;
            objctr.SetupFrame(try_to_find_frame);
        }
    }

    public void MakeGuardsForObjectControllers(bool noinit = false)
    {
        MakeGuardsForObjectControllerTree(transform, noinit);
        if (!noinit)
            SetupPositionAndFrames();

        if (!noinit)
            foreach (var objctr in _object_controllers)
            {
                objctr.InitSecondPhase();
            }

        if (!noinit)
            if (_timeline != null)
                _timeline.InitHeroesArray();
    }

    public void InitCreatedObjectController(ObjectController objctr)
    {
        MakeGuardsForObjectController(objctr.transform, false);

        bool try_to_find_frame = objctr.GetComponent<GuardView>() != null;
        objctr.SetupFrame(try_to_find_frame);
        objctr.InitSecondPhase();

        var network_point = objctr.GetComponent<NetPointView>();
        if (network_point != null)
        {
            network_point.StartNetwork();
        }

        if (_timeline != null)
            _timeline.InitHeroesArray();
    }

    public void ManualAwake()
    {
        _network_controller = GetComponent<NetworkView>();
        transform.position = Vector3.zero;
        transform.rotation = Quaternion.identity;

        if (!_prevent_on_awake_initialization)
        {
            _timeline = new Timeline(this.name);
            AttachToTimeline(_timeline);
            MakeGuardsForObjectControllers();
        }

        InitGlowSystem();
    }

    public void ManualStart()
    {
        InitAbilities();
    }

    public void InitAbilities()
    {
        foreach (var objctr in _object_controllers)
            objctr.InitAbilities();
    }

    static void RemoveComponentIfExists<T>(GameObject go)
        where T : Component
    {
        var components = go.GetComponents<T>();
        foreach (var component in components)
        {
            GameObject.Destroy(component);
        }
    }

    public void RemovePartsForTimeSpirit_(Transform trsf)
    {
        foreach (Transform child in trsf)
        {
            var go = child.gameObject;
            if (child.gameObject.GetComponent<Camera>() != null)
            {
                Destroy(child.gameObject);
            }
            else
            {
                RemovePartsForTimeSpirit_(child);
            }

            var objctr = child.gameObject.GetComponent<ObjectController>();
            if (objctr != null)
            {
                objctr.DontReactOnDistruct(true);
            }

            RemoveComponentIfExists<MonoBehaviourAction>(go);
            RemoveComponentIfExists<IconedActor>(go);
            RemoveComponentIfExists<IconedActor>(go);
            RemoveComponentIfExists<ControlableActor>(go);
            RemoveComponentIfExists<TriggerBox>(go);
        }
    }

    public void UpdateObjectPositions()
    {
        foreach (var objctr in _object_controllers)
        {
            try
            {
                objctr.UpdatePosition();
            }
            catch (Exception e)
            {
                Debug.LogError("UpdateObjectPositions: " + e.Message);
            }
        }
    }

    public void RemovePartsForTimeSpirit()
    {
        RemovePartsForTimeSpirit_(transform);
    }

    public void SetAllMaterialsToGreenHologram_(Transform trsf)
    {
        foreach (Transform child in trsf)
        {
            var objctr = child.gameObject.GetComponent<ObjectController>();
            if (objctr != null)
            {
                ChronosphereController.ChangeMaterialToGreenHologram(
                    child.gameObject,
                    change_layer: 13
                );
            }
            SetAllMaterialsToGreenHologram_(child);
        }
    }

    public void SetAllMaterialsToGreenHologram()
    {
        SetAllMaterialsToGreenHologram_(transform);
    }

    public void BindToTimeline(Timeline tl)
    {
        _timeline = tl;
        IgnoreStartTime();
    }

    public void BindToTimeline2(Timeline tl)
    {
        _timeline = tl;
        _prevent_on_awake_initialization = true;
        IgnoreStartTime();

        MakeGuardsForObjectControllers(true);

        foreach (var objctr in _object_controllers)
        {
            objctr.AttachToTimeline(_timeline);
            //objctr.UpdateView();
        }
    }

    public void AttachToTimeline(Timeline tl, bool paranoid = false)
    {
        _timeline = tl;

        foreach (var objctr in _object_controllers)
        {
            objctr.AttachToTimeline(tl, paranoid);
        }

        try
        {
            ResetGlowRender();
        }
        catch { }
    }

    public void PromoteToStepAndView(long step)
    {
        _timeline.Promote(step);
        UpdateView();
    }

    public ObjectController GetObjectByName(string name)
    {
        return _object_controllers_dict[name];
    }

    public void AddObjectToObjectList(ObjectController object_controller, ObjectOfTimeline obj)
    {
        _object_controllers.Add(object_controller);
        _object_controllers_dict[obj.Name()] = object_controller;
        _object_controllers_hashes_dict[obj.ObjectId().hash] = object_controller;
    }

    public ObjectController CreateOrGetViewForObject(ObjectOfTimeline obj)
    {
        foreach (ObjectController gv in _object_controllers)
        {
            if (gv.GetObject().Name() == obj.Name())
            {
                return gv;
            }
        }

        var proto_id = obj.ProtoId();
        var go = ChronosphereController.instance.GetCopyInstance(proto_id);

        go.name = obj.Name();
        go.transform.parent = transform;
        go.SetActive(true);

        var object_controller = go.GetComponent<ObjectController>();
        object_controller.ManualAwake();

        object_controller.InitAbilities();
        AddObjectToObjectList(object_controller, obj);

        var animate_controller = object_controller.GetComponent<AnimateController>();
        if (animate_controller != null)
            _animate_controllers.Add(animate_controller);

        return object_controller;
    }

    public ControlableActor GetControlableActorByName(string name)
    {
        var objctr = _object_controllers_dict[name];
        return objctr.GetComponent<ControlableActor>();
    }

    void ResetGlowRender()
    {
        var custom_glow_renderer = GameObject
            .Find("Main Camera")
            .GetComponent<CustomGlowRenderer>();
        if (custom_glow_renderer != null)
            custom_glow_renderer.ResetCommandBuffer();
    }

    void Start()
    {
        if (!ignore_start_time)
        {
            _timeline.PromoteToTime(StartTime);

            if (StartReversed)
            {
                _timeline.SetReversedPass(true);
                _timeline.DropTimelineToCurrentState();
                Chronosphere().TimeReverseImmediate();
            }
        }

        StartNetwork();
        if (_late_awake_start)
        {
            ManualAwake();
            ManualStart();
        }
    }

    public MyList<ObjectController> GetObjects()
    {
        return _object_controllers;
    }

    void StartNetwork() => _network_controller?.StartNetwork();

    public Timeline GetTimeline()
    {
        return _timeline;
    }

    public void SetTimelineName(string name)
    {
        _timeline.SetName(name);
    }

    Shader GlowShader()
    {
        return ChronosphereController.instance.GlowShader();
    }

    public void InitGlowSystem()
    {
        CustomGlowSystem.instance.RegisterTimeline(this);
        foreach (var objctr in _object_controllers)
        {
            var guard_view = objctr.GetComponent<ObjectController>();
            if (guard_view != null)
            {
                guard_view.InstallTempreatureSubsystem(this, GlowShader());
            }
        }
    }

    public ObjectController GetObjectController(string name)
    {
        ObjectController objctr;
        _object_controllers_dict.TryGetValue(name, out objctr);
        return objctr;
    }

    public ObjectController GetObjectController(long name)
    {
        ObjectController objctr;
        _object_controllers_hashes_dict.TryGetValue(name, out objctr);
        return objctr;
    }

    public ControlableActor GetActor(string name)
    {
        ObjectController objctr;
        _object_controllers_dict.TryGetValue(name, out objctr);
        return objctr.GetComponent<ControlableActor>();
    }

    public ObjectController GetObject(string name)
    {
        ObjectController objctr;
        _object_controllers_dict.TryGetValue(name, out objctr);
        return objctr;
    }

    public ObjectController GetObject(long name)
    {
        ObjectController objctr;
        _object_controllers_hashes_dict.TryGetValue(name, out objctr);
        return objctr;
    }

    public ObjectController GetObject(ObjectId name)
    {
        return GetObject(name.hash);
    }

    public ObjectController GetObject(ObjectOfTimeline obj)
    {
        return GetObject(obj.ObjectId());
    }

    public ControlableActor GetControlableActor(string name)
    {
        return GetActor(name);
    }
}
