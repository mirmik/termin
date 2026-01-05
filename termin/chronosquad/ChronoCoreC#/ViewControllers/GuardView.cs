using System.Collections;
using System.Collections.Generic;

#if UNITY_64
using UnityEngine;
#endif

using System;

public class GuardView : ObjectController
{
    static int _id = 0;

    public float RunSpeed = 4.8f;
    public float WalkSpeed = 2.4f;
    public float LowGravityWalkSpeed = 1.7f;
    public float ZeroGravitySpeed = 1.0f;
    public float CroachSpeed = 1.7f;

    bool _updating_from_model = true;

    public float RunSyncPhase = 0.0f;
    public float WalkSyncPhase = 0.0f;
    public float CroachSyncPhase = 0.0f;
    public float Height = 1.8f;

    public bool IsHero = false;
    public bool IsShort = false;
    public bool IsVerySmall = false;

    public bool CanGrab_Corpse = true;
    public bool CanGrabCorpseStayed = false;
    public bool CanGrabAlived = false;

    public bool CroachOnStart = false;
    public bool IsArmored = false;

    public float CameraLevel = 1.5f;

    GameObject VosklicatelReaction = null;

    public GameObject _promise_mark_object = null;
    public BindUiToWorldPosition _promise_mark_text = null;

    AnimateController animctr;

    // AnimationClip _walk_clip;
    // AnimationClip _run_clip;
    // AnimationClip _croach_clip;

    //GuardView _linked_in_time_with = null;
    GameObject _linked_in_time_with_object = null;
    LineRenderer _linked_in_time_with_line = null;

    bool _is_init = false;

    bool _deactivate_on_load = false;

    //MyList<MeshRenderer> _mesh_renderers = new MyList<MeshRenderer>();

    //NavMeshLinkSupervisor _nav_mesh_link_supervisor = null;

    // particle system
    //public GameObject ParticleSystemPrefab = null;


    public void CreatePromiseMarkObject()
    {
        if (_promise_mark_object == null)
        {
            _promise_mark_object = GameObject.CreatePrimitive(PrimitiveType.Cube);
            _promise_mark_object.transform.parent = transform;
            _promise_mark_object.transform.localPosition = new Vector3(0, 0, 0);
            _promise_mark_object.transform.localScale = new Vector3(0.5f, 0.5f, 0.5f);
            _promise_mark_object.GetComponent<Renderer>().material.color = new Color(1, 0, 0, 1);
            _promise_mark_object.layer = (int)Layers.PROMISE_OBJECT_LAYER;
            _promise_mark_object.AddComponent<PromiseMark>().SetObjectController(this);
            _promise_mark_object.SetActive(false);
            _promise_mark_text = Instantiate(MaterialKeeper.Instance.GetPrefab("OnScreenText"))
                .GetComponent<BindUiToWorldPosition>();
            _promise_mark_text.transform.parent = _promise_mark_object.transform;
            _promise_mark_text.transform.localPosition = new Vector3(0, 2, 0) * 2.0f;
        }
        _promise_mark_object.GetComponent<PromiseMark>().SetObjectController(this);
    }

    public bool DisableUpdatingFromModel()
    {
        return _updating_from_model = false;
    }

    public bool EnableUpdatingFromModel()
    {
        return _updating_from_model = true;
    }

    public string generate_id()
    {
        _id += 1;
        return "guard" + _id.ToString();
    }

    public GuardView() { }

    TimelineController TimelineController()
    {
        return GetTimelineController();
    }

    public Actor LinkedInTimeWith()
    {
        var actor = guard();
        var timeline = actor.GetTimeline() as Timeline;
        var linked_in_time_with_name = actor.LinkedInTimeWithName();
        var linked_in_time_with = timeline.TryGetActor(linked_in_time_with_name);
        return linked_in_time_with;
    }

    void Awake()
    {
        FindSubobjectsTransforms();
        _model = this.transform.Find("Model").gameObject;
        // ParticleSystemPrefab = Instantiate(Resources.Load<GameObject>("Prefabs/TimeErrorMarker"));
        // ParticleSystemPrefab.name = "TimeErrorMarker";
        // ParticleSystemPrefab.transform.parent = transform;
        // ParticleSystemPrefab.transform.localPosition = new Vector3(0, 1.9f, 0);

        animctr = gameObject.GetComponent<AnimateController>();
        var subobjects = ListOfActiveSubObjects();
        // foreach (var subobject in subobjects)
        // {
        // 	var mesh_renderer = subobject.GetComponent<MeshRenderer>();
        // 	if (mesh_renderer != null)
        // 		_mesh_renderers.Add(mesh_renderer);
        // }

        // found LinkedLine
        foreach (Transform child in transform)
        {
            if (child.name == "LinkedLine")
            {
                _linked_in_time_with_object = child.gameObject;
                _linked_in_time_with_line =
                    _linked_in_time_with_object.GetComponent<LineRenderer>();
                _linked_in_time_with_object.SetActive(false);
                break;
            }
        }

        if (_linked_in_time_with_object == null)
        {
            _linked_in_time_with_object = new GameObject("LinkedLine");
            _linked_in_time_with_line = _linked_in_time_with_object.AddComponent<LineRenderer>();
            _linked_in_time_with_line.material = new Material(Shader.Find("Sprites/Default"));
            _linked_in_time_with_object.transform.parent = transform;
            _linked_in_time_with_line.startWidth = 0.1f;
            _linked_in_time_with_line.endWidth = 0.1f;
        }

        //_nav_mesh_link_supervisor = GameObject.FindFirstObjectByType<NavMeshLinkSupervisor>();
    }

    public void SetLinkedColorForPass(bool is_reversed)
    {
        if (is_reversed)
        {
            _linked_in_time_with_line.startColor = Color.black;
            _linked_in_time_with_line.endColor = Color.red;
        }
        else
        {
            _linked_in_time_with_line.startColor = Color.black;
            _linked_in_time_with_line.endColor = Color.blue;
        }
    }

    // public MyList<MeshRenderer> GetMeshRenderers()
    // {
    // 	return _mesh_renderers;
    // }

    public void SetDeactivateOnLoad(bool deactivate_on_load)
    {
        _deactivate_on_load = deactivate_on_load;
    }

    // Start is called before the first frame update
    void Start()
    {
        CreatePromiseMarkObject();

        // instance prefab Vosklicatel
        VosklicatelReaction = this.FindInChildOrCreate(
            "VosklicatelReaction",
            prefab: MaterialKeeper.Instance.GetPrefab("Vosklicatel")
        );
        VosklicatelReaction.transform.parent = transform;
        VosklicatelReaction.transform.localPosition = new Vector3(0, 1.9f, 0);
        // var up = ChronosphereController.Instance.GetGravityInGlobalPoint(
        // 	transform.position
        // );
        VosklicatelReaction.SetActive(false);
    }

    public Actor GetGuard()
    {
        return (Actor)GetObject();
    }

    public override void InitObjectController(ITimeline tl)
    {
        if (_is_init)
        {
            return;
        }

        Actor actor = CreateObject<Actor>();
        InitVariables(actor);
        UpdateHideOrMaterial(actor);
        _is_init = true;
    }

    public void InitVariables(Actor _guard)
    {
        base.InitVariables(_guard);
        _guard.SetName(this.gameObject.name);

        if (IsHero)
            _guard.MarkAsHero();

        _guard.SetShort(IsShort);
        _guard.SetVerySmall(IsVerySmall);
        // _guard.walk_speed = WalkSpeed;
        // _guard.low_gravity_walk_speed = LowGravityWalkSpeed;
        // _guard.zero_gravity_speed = ZeroGravitySpeed;
        // _guard.run_speed = RunSpeed;
        // _guard.croach_speed = CroachSpeed;
        _guard.SetSpeedStruct(GetSpeedStruct());

        _guard.walk_sync_phase = WalkSpeed;
        _guard.run_sync_phase = RunSpeed;
        _guard.croach_sync_phase = CroachSpeed;
        _guard.SetIsArmored(IsArmored);
        _guard.SetObjectTimeReferencePoint(0, ReverseOnStart);
        _guard.SetCameraLevel(CameraLevel);
        _guard.UseSurfaceNormalForOrientation = UseNormalAsUp;
        _guard.Steering = Steering;
        _guard.SetWalkableWalls(WalkableWalls);
        _guard.SetSightDistance(base.GetSightDistance());
        _guard.SetHasCamera(true);
        _guard.SetCanGrabCorpse(CanGrab_Corpse);
        _guard.SetCanGrabCorpseStayed(CanGrabCorpseStayed);
        _guard.SetCanGrabAlived(CanGrabAlived);
        _guard.SetSightAngle(base.SightAngle);
        _guard.croachControlComponent.IsCroach = CroachOnStart;
        _guard.croachControlComponent.IsCroachControl = CroachOnStart;
    }

    public void SetGuard(Actor guard)
    {
        ObjectProxy().AttachTo(guard.Name(), guard.GetTimeline());
        Actor _guard = GetGuard();

        _is_init = true;

        if (!_guard.IsCopy())
        {
            _guard.SetName(this.gameObject.name);
            InitVariables(_guard);
        }

        UpdateHideOrMaterial(_guard);
    }

    void set_transparency(float alpha) { }

    void SetDirection(Vector3 direction)
    {
        var rotation = Quaternion.LookRotation(direction);
        this.transform.rotation = rotation;
    }

    bool IsActivePass()
    {
        Actor _guard = GetGuard();
        return _guard.IsReversed() == _guard.GetTimeline().IsReversedPass();
    }

    public Vector3 RaycastGroundPosition(Vector3 vec)
    {
        var down_direction = Vector3.down; // TODO: in frame
        var up_direction = Vector3.up;
        var layer_mask = 1 << 6 | 1 << 0;
        RaycastHit hit;
        if (
            Physics.Raycast(
                vec + up_direction * 1.0f,
                down_direction,
                out hit,
                Mathf.Infinity,
                layer_mask
            )
        )
        {
            return hit.point;
        }
        else
        {
            return vec;
        }
    }

    public void UpdatePromiseMark(Actor guard)
    {
        bool is_promise = guard.HasPromiseMark();
        if (!is_promise)
            return;

        var promise_pose = guard.PromiseMarkPose();
        var promise_pose_global = promise_pose.GlobalPose(guard.GetTimeline());

        if (!_promise_mark_object.activeSelf)
        {
            _promise_mark_object.SetActive(true);
            _promise_mark_object.transform.parent = transform.parent;
        }

        _promise_mark_object.transform.position = promise_pose_global.position;
        _promise_mark_object.transform.rotation = promise_pose_global.rotation;

        var promise_step = guard.PromiseMarkTimelineStep2();
        var current_step = guard.GetTimeline().CurrentStep();
        var timediff = Utility.DurationFromSteps(promise_step - current_step);
        _promise_mark_text.SetText(timediff.ToString("F2"));
    }

    public override void UpdateView()
    {
        if (!_updating_from_model)
            return;

        Actor _guard = GetGuard();
        base.UpdateView();

        var linked_actor = LinkedInTimeWith();
        if (linked_actor != null)
        {
            _linked_in_time_with_line.SetPosition(0, _guard.Position());
            _linked_in_time_with_line.SetPosition(1, linked_actor.Position());

            if (linked_actor.IsMaterial() && _guard.IsMaterial())
            {
                if (IsActivePass())
                {
                    if (!_linked_in_time_with_object.activeSelf)
                        _linked_in_time_with_object.SetActive(true);
                    SetLinkedColorForPass(_guard.IsReversed());
                }
                else
                {
                    if (!_linked_in_time_with_object.activeSelf)
                        _linked_in_time_with_object.SetActive(true);
                    SetLinkedColorForPass(_guard.IsReversed());
                }
            }
            else
            {
                if (_linked_in_time_with_object.activeSelf)
                {
                    _linked_in_time_with_object.SetActive(false);
                }
            }
        }
        else
        {
            if (_linked_in_time_with_object.activeSelf)
            {
                _linked_in_time_with_object.SetActive(false);
            }
        }

        UpdateVosklicatelReaction(_guard);
        UpdatePromiseMark(_guard);
        UpdateDistruct();
    }

    void UpdateVosklicatelReaction(Actor guard)
    {
        if (VosklicatelReaction == null)
            return;

        if (guard.IsDead || guard.IsDead || guard.IsHide())
        {
            if (VosklicatelReaction.activeSelf)
                VosklicatelReaction.SetActive(false);
            return;
        }

        if (guard.IsAlarmState())
        {
            if (!VosklicatelReaction.activeSelf)
                VosklicatelReaction.SetActive(true);
            var main_camera = Camera.main;
            var main_camera_position = main_camera.transform.position;
            // rotate VosklicatelReaction to camera direction
            var direction = main_camera_position - transform.position;
            //direction.y = 0;
            var moved_with = guard.MovedWith();
            var up = -ChronosphereController.instance.GetGravityInGlobalPoint(
                transform.position,
                moved_with
            );
            VosklicatelReaction.transform.rotation = Quaternion.LookRotation(direction, up);
        }
        else
        {
            if (VosklicatelReaction.activeSelf)
                VosklicatelReaction.SetActive(false);
        }
    }

    // public Material PhantomMaterial()
    // {
    // 	return _phantom_material;
    // }

    // public void SetPosition(Vector3 pos)
    // {
    // 	this.transform.position = pos;
    // }

    public override void ShowLinkedInTimeWithObject(bool show)
    {
        if (_linked_in_time_with_object == null)
            return;
        _linked_in_time_with_object.SetActive(show);
    }

    void AddSubObjectToList(GameObject sub_object, MyList<GameObject> list)
    {
        if (sub_object.activeSelf)
            list.Add(sub_object);

        foreach (Transform child in sub_object.transform)
        {
            AddSubObjectToList(child.gameObject, list);
        }
    }

    public MyList<GameObject> ListOfActiveSubObjects()
    {
        MyList<GameObject> list = new MyList<GameObject>();
        AddSubObjectToList(gameObject, list);
        return list;
    }
}
