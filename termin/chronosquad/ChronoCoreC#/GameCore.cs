using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using UnityEngine;
using UnityEngine.AI;
using UnityEngine.SceneManagement;
#if UNITY_64
using UnityEngine.Experimental.AI;
using Unity.AI.Navigation;
using UnityEngine.UI;
using UnityEngine.EventSystems;
using Unity.Collections;
#endif

#if UNITY_EDITOR
using UnityEditor.SceneManagement;
#endif

struct SpriteSignature
{
    public string path;
    public int width;
    public int height;

    public SpriteSignature(string path, int width, int height)
    {
        this.path = path;
        this.width = width;
        this.height = height;
    }
}

public static class GameCore
{
    public static int GROUND_LAYER = 6;
    public static int OBSTACLES_LAYER = 7;
    public static int DEFAULT_LAYER = 0;
    public static int ACTOR_LAYER = 11;

    //static CameraController camera_controller = null;

    static Vector3 current_mouse_position = new Vector3(0, 0, 0);
    static string current_mode = "normal";

    static Vector3 right_drag_position = new Vector3(0, 0, 0);

    public static TimelineController CurrentTimelineController()
    {
        return ChronosphereController.instance.CurrentTimelineController();
    }

    public static void toggle_outline_mode()
    {
        GetChronosphereController().ToggleOutlineMode();
    }

    public static string ObjectTMPDirectory()
    {
        var streamingAssetsPath = Application.streamingAssetsPath;
        var directory = streamingAssetsPath + "/ObjectsTMP";
        return directory;
    }

    public static string PatrolPointsTMPDirectory()
    {
        var streamingAssetsPath = Application.streamingAssetsPath;
        var directory = streamingAssetsPath + "/PatrolPointsTMP";
        return directory;
    }

    public static bool TryNavSamplePosition(Vector3 pos, out Vector3 result)
    {
        UnityEngine.AI.NavMeshHit hit;
        if (
            UnityEngine.AI.NavMesh.SamplePosition(
                pos,
                out hit,
                100,
                UnityEngine.AI.NavMesh.AllAreas
            )
        )
        {
            result = hit.position;
            return true;
        }
        result = new Vector3(0, 0, 0);
        return false;
    }

    public static void SceneDirty(Scene scene)
    {
#if UNITY_EDITOR
        UnityEditor.SceneManagement.EditorSceneManager.MarkSceneDirty(scene);
#endif
    }

    public static void on_delete_pressed()
    {
        var selected_actor = SelectedActor();
        if (selected_actor == null)
            return;
        //DeleteVariant(selected_actor.GetObject());

        selected_actor.GetComponent<ObjectController>().RemoveThisObject();
    }

    public static void DeleteVariant(ObjectOfTimeline obj)
    {
        //(obj.GetTimeline() as Timeline).DeleteVariant(obj);
    }

    public static void on_backspace_pressed()
    {
        Chronosphere().ReturnToPreviousTimeline();
    }

    public static Timeline CurrentTimeline()
    {
        return CurrentTimelineController().GetTimeline();
    }

    public static bool IsDropTimeOnEdit()
    {
        return Chronosphere().IsDropTimeOnEdit();
    }

    public static void SetDropTimeOnEdit(bool value)
    {
        Chronosphere().SetDropTimeOnEdit(value);
    }

    public static ControlableActor SelectedActor()
    {
        return GetChronosphereController().SelectedActor();
    }

    public static bool HasActiveAction()
    {
        var selected_actor = SelectedActor();
        if (selected_actor == null)
            return false;

        return selected_actor._used_action != null;
    }

    public static void CancelActiveAction()
    {
        var selected_actor = SelectedActor();
        selected_actor._used_action.Cancel();
    }

    static Dictionary<SpriteSignature, Sprite> _sprite_cache =
        new Dictionary<SpriteSignature, Sprite>();

    public static Sprite LazySpriteGenerate(string path, int width, int height)
    {
        var signature = new SpriteSignature(path, width, height);
        if (_sprite_cache.ContainsKey(signature))
        {
            return _sprite_cache[signature];
        }
        else
        {
            var texture = Resources.Load<Texture2D>(path);
            var sprite = Sprite.Create(texture, new Rect(0, 0, width, height), new Vector2(0, 0));
            _sprite_cache[signature] = sprite;
            return sprite;
        }
    }

    public static Sprite LazySpriteGenerate(Texture2D texture)
    {
        if (texture == null)
        {
            return null;
        }

        var signature = new SpriteSignature(texture.name, texture.width, texture.height);
        if (_sprite_cache.ContainsKey(signature))
        {
            return _sprite_cache[signature];
        }
        else
        {
            var sprite = Sprite.Create(
                texture,
                new Rect(0, 0, texture.width, texture.height),
                new Vector2(0, 0)
            );
            _sprite_cache[signature] = sprite;
            return sprite;
        }
    }

    public static Sprite GetImageSpriteForSpeaker(string speaker)
    {
        MaterialKeeper material_keeper = MaterialKeeper.Instance;
        var texture = material_keeper.GetTexture(speaker);
        return LazySpriteGenerate(texture);
    }

    public static Sprite LazySpriteGenerate(string path)
    {
        var texture = Resources.Load<Texture2D>(path);
        var sprite = Sprite.Create(
            texture,
            new Rect(0, 0, texture.width, texture.height),
            new Vector2(0, 0)
        );
        return sprite;
    }

    public static Sprite LazySpriteGenerate(Texture2D texture, int width, int height)
    {
        var signature = new SpriteSignature(texture.name, width, height);
        if (_sprite_cache.ContainsKey(signature))
        {
            return _sprite_cache[signature];
        }
        else
        {
            var sprite = Sprite.Create(texture, new Rect(0, 0, width, height), new Vector2(0, 0));
            _sprite_cache[signature] = sprite;
            return sprite;
        }
    }

    public static Vector3 get_mouse_position()
    {
        return current_mouse_position;
    }

    public static ChronosphereController GetChronosphereController()
    {
        return ChronosphereController.instance;
    }

    public static ChronoSphere Chronosphere()
    {
        return ChronosphereController.instance.GetChronosphere();
    }

    public static Vector3 camera_point_to_world_position(Vector3 p)
    {
        var ray = Camera.main.ScreenPointToRay(new Vector2(p.x, p.y));

        int layerMask =
            Utility.ToMask(Layers.GROUND_LAYER)
            | Utility.ToMask(Layers.DEFAULT_LAYER)
            | Utility.ToMask(Layers.HALF_OBSTACLES_LAYER)
            | Utility.ToMask(Layers.NAVIGATE_HELPER_LAYER);
        if (Physics.Raycast(ray, out RaycastHit hit, 300, layerMask))
        {
            return hit.point;
        }

        throw new Exception("Can't find point");
    }

    public static void set_cursor_mode(string mode)
    {
        current_mode = mode;
    }

    public static void ToggleEditorMode()
    {
        ChronosphereController.instance.ToggleEditorMode();
    }

    public static void on_mouse_right_click()
    {
        right_drag_position = current_mouse_position;
    }

    public static void f1_key_pressed_event()
    {
        GameCore.ToggleEditorMode();
    }

    public static void f2_key_pressed_event()
    {
        var create_point_action = GlobalActions.Instance.CreateYetOnePoint;
        create_point_action.OnIconClick();
    }

    public static void f3_key_pressed_event()
    {
        var create_action = GlobalActions.Instance.CreateGuard;
        create_action.OnIconClick();
    }

    public static void f4_key_pressed_event()
    {
        var move_editor_action = GlobalActions.Instance.MoveEditor;
        move_editor_action.OnIconClick();
    }

    public static void f5_key_pressed_event()
    {
        var remove_editor_action = GlobalActions.Instance.RemoveEditor;
        remove_editor_action.OnIconClick();
        // var copy = Chronosphere().CreateCopyOfCurrentTimeline();
        // Chronosphere().set_current_timeline(copy);
    }

    public static void f6_key_pressed_event()
    {
        // var copy = Chronosphere().CreateReversedCopyOfCurrentTimeline();
        // Chronosphere().TimeReverseImmediate();
        // Chronosphere().set_current_timeline(copy);

        ChronosphereController.instance.ToggleFogOfWar();
    }

    public static void f7_key_pressed_event()
    {
        // var copy = Chronosphere().CreateCopyOfCurrentTimeline();
        // copy.Promote(
        // 	Chronosphere().CurrentTimeline().CurrentStep() - (long)Utility.GAME_GLOBAL_FREQUENCY
        // );
        // var controller = GetChronosphereController().GetTimelineController(copy);
        // //controller.PhantomMaterialModeProperty = true;
        // controller.RunWithCurrentLineProperty = true;
    }

    public static void f8_key_pressed_event()
    {
        // var current_timeline = Chronosphere().CurrentTimeline();
        // current_timeline.DropTimelineToCurrentState();
    }

    public static void f9_key_pressed_event()
    {
        // var current_timeline_controller = GetChronosphereController().CurrentTimelineController();
        // var start_time = 30;
        // var current_timeline = Chronosphere().CurrentTimeline();
        // current_timeline.FastPromote((long)(start_time * Utility.GAME_GLOBAL_FREQUENCY));
    }

    public static void f10_key_pressed_event() { }

    public static void f11_key_pressed_event()
    {
        // GetChronosphereController().DetectStartParradoxOnUpdate();
    }

    public static Vector3 UpForWorldPoint(Vector3 pos, PlatformAreaBase platform)
    {
        var gravity = -ChronosphereController.instance.GetGravityInGlobalPoint(pos, platform);
        return gravity.normalized;
    }

    public static Vector3 UpForWorldPoint(Vector3 pos, ObjectId platform)
    {
        if (ChronosphereController.instance == null)
            return Vector3.up;

        var gravity = -ChronosphereController.instance.GetGravityInGlobalPoint(pos, platform);
        return gravity.normalized;
    }

    public static void f12_key_pressed_event()
    {
        var chronosphere = Chronosphere();
        var trent = chronosphere.ToTrent();

        // start in task
        Task task = new Task(() =>
        {
            var trent_str = SimpleJsonParser.SerializeTrent(trent);
        });
        task.Start();
    }

    public static void select_hero(int no)
    {
        UserInterface().select_hero(no);
    }

    public static Dictionary<string, Timeline> timelines()
    {
        return Chronosphere().timelines();
    }

    public static void create_copy_of_current_timeline()
    {
        var chronosphere_controller = GetChronosphereController();
        chronosphere_controller.CreateCopyOfCurrentTimeline();
    }

    public static void SelectActor(GameObject actor)
    {
        if (actor == null)
        {
            GetChronosphereController().SetSelectedActor(null);
            return;
        }

        var objctr = actor.GetComponent<ObjectController>();

        var controlable_actor = actor.GetComponent<ControlableActor>();
        if (controlable_actor == null)
        {
            return;
        }

        if (
            !controlable_actor.IsControlableByUser()
            && !ChronosphereController.instance.IsEditorMode()
        )
        {
            return;
        }

        GetChronosphereController().SetSelectedActor(controlable_actor);
        controlable_actor.OnSelect();
    }

    // public static void update()
    // {
    // 	Chronosphere().UpdateForGameTime(Time.time);
    // }

    static public void TimeReverse()
    {
        float cur_target_time_multiplier = (float)Chronosphere().target_time_multiplier();
        Chronosphere().set_target_time_multiplier(-cur_target_time_multiplier);
    }

    public static void TimeReverseImmediate()
    {
        Chronosphere().TimeReverseImmediate();
    }

    public static void on_space_pressed()
    {
        var chronosphere_controller = GetChronosphereController();
        var chronosphere = chronosphere_controller.Chronosphere();
        chronosphere.pause();

        bool is_pause_enabled = chronosphere.IsPaused();
        if (is_pause_enabled)
            chronosphere_controller.EnableTimeSpiritTimeline();
        else
            chronosphere_controller.DisableTimeSpiritTimeline();
    }

    public static void DropSelectedActor()
    {
        GetChronosphereController().SetSelectedActor(null);
    }

    static MyList<float> speeds = new MyList<float>()
    {
        4.0f,
        2.0f,
        1.0f,
        0.3f,
        0.1f,
        0.0f,
        -0.1f,
        -0.3f,
        -1.0f,
        -2.0f,
    };
    static int current_speed_index = 2;

    public static void on_tab_pressed()
    {
        float current_time_multiplier = (float)Chronosphere().target_time_multiplier();
        Chronosphere().set_target_time_multiplier(-current_time_multiplier);
    }

    public static void on_mouse_wheel_time_control(float y)
    {
        if (Chronosphere().CurrentTimeline().IsReversedPass())
        {
            y = -y;
        }

        if (!Chronosphere().is_pause_mode())
        {
            if (y > 0)
            {
                current_speed_index -= 1;
                if (current_speed_index < 0)
                {
                    current_speed_index = 0;
                }
                Chronosphere().set_target_time_multiplier(speeds[current_speed_index]);
            }
            else
            {
                current_speed_index += 1;
                if (current_speed_index >= speeds.Count)
                {
                    current_speed_index = speeds.Count - 1;
                }
                Chronosphere().set_target_time_multiplier(speeds[current_speed_index]);
            }
        }
        else
        {
            float modifier_mul = 0.2f;
            if (y > 0)
                Chronosphere().modify_target_time_in_pause_mode(modifier_mul);
            else
                Chronosphere().modify_target_time_in_pause_mode(-modifier_mul);
        }
    }

    public static void SetRealtimeFlow()
    {
        SetTimeFlow(1.0f);
    }

    public static void SetTimeFlow(float mul)
    {
        if (CurrentTimeline().IsReversedPass())
        {
            mul = -mul;
        }

        if (Chronosphere().is_pause_mode())
        {
            on_space_pressed();
        }
        Chronosphere().set_target_time_multiplier(mul);
    }

    public static void on_mouse_wheel(float y)
    {
        // shift pressed
        if (Input.GetKey(KeyCode.LeftShift) || Input.GetKey(KeyCode.RightShift))
        {
            on_mouse_wheel_time_control(y);
        }
        else
        {
            AbstractCameraController.Instance.move_forward(y);
        }
    }

    // static public float AnimationBooster()
    // {
    // 	return ChronoSphereMain.Instance.AnimationBooster;
    // }

    public static void environment_click(Vector3 pos, ClickInformation click)
    {
        if (ChronosphereController.instance.IsEditorMode())
        {
            if (Input.GetKey(KeyCode.LeftControl) || Input.GetKey(KeyCode.RightControl))
            {
                EditorMarker editorMarker = EditorMarker.Instance;
                var obj = editorMarker.GetMarkedObject();
                var dir = pos - obj.transform.position;
                obj.GetComponent<PatrolPointEditor>()
                    .SetRotation(Quaternion.LookRotation(dir, Vector3.up));
            }
        }

        if (UsedActionBuffer.Instance.UsedAction != null)
        {
            UsedActionBuffer.Instance.UsedAction.OnEnvironmentClick(click);
            return;
        }

        if (SelectedActor() == null)
            return;

        bool only_rotate = Input.GetKey(KeyCode.LeftControl) || Input.GetKey(KeyCode.RightControl);
        SelectedActor()
            .on_enviroment_clicked_while_selected(pos, only_rotate: only_rotate, click: click);

        ChronosphereController.instance.ResetTimeSpirit();
    }

    public static void right_environment_click(Vector3 pos, bool double_click, GameObject hit)
    {
        // if control pressed
        if (Input.GetKey(KeyCode.LeftControl) || Input.GetKey(KeyCode.RightControl))
        {
            ViewMarker.Instance.Attach(pos);
            return;
        }

        if (SelectedActor() == null)
            return;

        SelectedActor().on_right_enviroment_clicked_while_selected(pos, double_click, hit);
    }

    public static void ShowBook(string text)
    {
        Chronosphere().set_pause_mode(true);

        var book = GameObject.Find("BookPrefab");
        var book_script = book.GetComponent<BookPrefab>();
        book_script.SetText(text);
        book_script.Activate(true);
    }

    public static void RestoreAfterBookReading()
    {
        Chronosphere().set_pause_mode(false);
        var book = GameObject.Find("BookPrefab");
        var book_script = book.GetComponent<BookPrefab>();
        book_script.Activate(false);
    }

    public static ObjectController FindObjectControllerInParentTree(GameObject go)
    {
        Transform transform = go.transform;
        while (transform != null)
        {
            var actor = transform.gameObject.GetComponent<ObjectController>();
            if (actor != null)
                return actor;
            transform = transform.parent;
        }
        return null;
    }

    public static T FindInParentTree<T>(GameObject go)
        where T : Component, new()
    {
        Transform transform = go.transform;
        while (transform != null)
        {
            var actor = transform.gameObject.GetComponent<T>();
            if (actor != null)
                return actor;
            transform = transform.parent;
        }
        return null;
    }

    public static void left_click_on_actor(ClickInformation clickInformation)
    {
        var actor = GameCore.FindObjectControllerInParentTree(
            clickInformation.actor_hit.collider.gameObject
        );
        if (actor == null)
            return;

        var obj = actor.GetObject();
        var obj_fourd_start = obj.FourDTimelineStart();
        var current_timeline_step = Chronosphere().CurrentTimeline().CurrentStep();

        if (obj_fourd_start > current_timeline_step)
        {
            Debug.Log("Actor is not born yet");
        }

        if (SelectedActor() != null)
        {
            // Цепочка обязанностей. Или SelectedActor() скажет, что он обработает клик,
            // или управление передасться ниже.
            if (SelectedActor().left_click_on_another_actor(actor.gameObject, clickInformation))
            {
                ChronosphereController.instance.ResetTimeSpirit();
                return;
            }
        }

        //SelectActor(actor.gameObject);
    }

    public static void temporary_double_time_speed()
    {
        Chronosphere().set_target_time_multiplier(2.0f);
    }

    public static void temporary_normal_time_speed()
    {
        Chronosphere().set_target_time_multiplier(1.0f);
    }

    public static void on_0_pressed()
    {
        Chronosphere().Select(null);
    }

    public static void on_1_pressed()
    {
        GameCore.select_hero(1);
    }

    public static void on_2_pressed()
    {
        GameCore.select_hero(2);
    }

    public static void on_3_pressed()
    {
        GameCore.select_hero(3);
    }

    public static void on_4_pressed()
    {
        GameCore.select_hero(4);
    }

    public static void on_5_pressed()
    {
        GameCore.select_hero(5);
    }

    public static void on_6_pressed()
    {
        GameCore.select_hero(6);
    }

    public static void on_7_pressed()
    {
        GameCore.select_hero(7);
    }

    public static void on_8_pressed()
    {
        GameCore.select_hero(8);
    }

    public static void on_9_pressed()
    {
        GameCore.select_hero(9);
    }

    public static void right_click_on_actor(GameObject actor)
    {
        // if control pressed
        var oc = GameCore.FindObjectControllerInParentTree(actor);
        if (oc == null)
            return;

        if (Input.GetKey(KeyCode.LeftControl) || Input.GetKey(KeyCode.RightControl))
        {
            ViewMarker.Instance.Attach(oc.gameObject);
            return;
        }

        var obj = oc.GetObject();
        if (obj.IsDead || obj.IsPreDead)
            return;

        if (obj.IsHero())
        {
            SelectActor(oc.gameObject);
            return;
        }

        if (ChronosphereController.instance.IsEditorMode())
        {
            SelectActor(oc.gameObject);
            return;
        }

        var fov_tester = GameObject.Find("FOVTester");
        FOVTesterController fov_tester_controller = fov_tester.GetComponent<FOVTesterController>();
        fov_tester_controller.AttachTo(oc.gameObject);
    }

    public static void ui_click(Vector3 pos, GameObject go) { }

    static int GroundLayerMask()
    {
        return 1 << 6;
    }

    static int DefaultLayerMask()
    {
        return 1 << 0;
    }

    static int ObstaclesLayerMask()
    {
        return 1 << 7;
    }

    public static ReferencedPoint Vector3ToReferencedPoint(Vector3 pos)
    {
        var frame = FrameNameForPosition(pos);
        return ReferencedPoint.FromGlobalPosition(pos, frame, CurrentTimeline());
    }

    public static RaycastHit RaycastToNavMeshLinkColliders(
        Vector3 pos,
        bool double_click,
        GameObject hit_for_obstacles
    )
    {
        RaycastHit hit;
        Ray ray = Camera.main.ScreenPointToRay(Input.mousePosition);
        if (Physics.Raycast(ray, out hit, 100, LayerMask.GetMask("NavMeshLinkCollider")))
        {
            NavMeshLink navmeshlink = hit.collider.gameObject.GetComponent<NavMeshLink>();
            return hit;
        }
        return hit;
    }

    public static Vector3 FindNearestPointOnNavMesh(Vector3 pos)
    {
        UnityEngine.AI.NavMeshHit hit;
        UnityEngine.AI.NavMesh.SamplePosition(pos, out hit, 100, UnityEngine.AI.NavMesh.AllAreas);
        return hit.position;
    }

    public static Vector3 NavSamplePosition(Vector3 pos)
    {
        return FindNearestPointOnNavMesh(pos);
    }

    public static ObjectId FrameNameForPosition(Vector3 pos)
    {
        // UnityEngine.AI.NavMeshHit hit;
        // UnityEngine.AI.NavMesh.SamplePosition(pos, out hit, 100, UnityEngine.AI.NavMesh.AllAreas);
        // var area = CountLeadingZeros(hit.mask) - 1;
        // var area_name = ChronosphereController.GetPlatformName(area);
        // return area_name;

        var clossest_collider = Physics.OverlapSphere(
            pos,
            0.5f,
            layerMask: Utility.ToMask(Layers.DEFAULT_LAYER)
                | Utility.ToMask(Layers.OBSTACLES_LAYER)
                | Utility.ToMask(Layers.GROUND_LAYER)
        );

        var platform = clossest_collider[0].gameObject;
        var platform_frame = NavMeshLinkSupervisor.Instance.FoundPlatformId(platform);
        return platform_frame;
    }

    public static ObjectId FrameNameForObject(GameObject obj)
    {
        var objid = NavMeshLinkSupervisor.Instance.FoundPlatformId(obj);
        return objid;
    }

    public static float AnimationDuration(string actor_name, AnimationType animation_name)
    {
        var chronosphereController = ChronosphereController.instance;
        if (chronosphereController == null)
        {
            return 1.0f;
        }

        var current_timeline_controller = chronosphereController.CurrentTimelineController();
        var actor = current_timeline_controller.GetObjectByName(actor_name);
        var animation_controller = actor.GetComponent<AnimateController>();
        if (animation_controller == null)
        {
            return 1.0f;
        }

        var animations = animation_controller.GetAnimations();

        var anim = animation_controller.GetAnimationByName(animation_name);
        if (anim == null)
        {
            var antype = animation_name.ToString();
            return 0.1f;
        }

        return anim.Duration();
    }

    public static UserInterfaceCanvas UserInterface()
    {
        var user_interface_canvas = GameObject.Find("ChronoSphereInterface");
        var user_interface_canvas_script =
            user_interface_canvas.GetComponent<UserInterfaceCanvas>();
        return user_interface_canvas_script;
    }

    public static void SetTextOfDebugField(string text)
    {
        var user_interface_canvas = UserInterface();
        user_interface_canvas.SetTextOfDebugField(text);
    }

    public static void print_list_of_selected_actor_animatronis()
    {
        // if (SelectedActor() == null)
        // 	return;
        // var animatronis = SelectedActor().GetAnimatronicsList();
        // string text = "Animatronics:\n";

        // // print last 30 animatronics
        // int count = animatronis.Count;
        // int spos = count - 30;
        // if (spos < 0)
        // 	spos = 0;
        // for (int i = spos; i < count; i++)
        // {
        // 	var anim = animatronis[i];
        // 	text += anim.info() + "\n";
        // }

        // var curnode = SelectedActor().Object().Animatronics().CurrentNode();
        // var curstr = curnode == null ? "null" : curnode.Value.info();
        // text += "Current: " + curstr + "\n";

        // SetTextOfDebugField(text);
    }

    public static void print_list_of_commands()
    {
        // var guard = SelectedActor().guard();
        // var commands = guard.CommandBuffer().GetCommandQueue();

        // string text = "MyList Of Commands:\n";
        // foreach (var command in commands.AsList())
        // {
        // 	text +=
        // 		command.GetType().Name
        // 		+ " start_step: "
        // 		+ command.StartStep
        // 		+ " finish_step: "
        // 		+ command.FinishStep
        // 		+ "\n";
        // }

        // SetTextOfDebugField(text);
    }

    public static void print_list_of_selected_object_time()
    {
        // var object_time = SelectedActor().guard().ObjectTime();
        // //var modifiers = object_time.Modifiers.AsList();

        // //string text = "Object Time Modifiers: \n" + object_time.info() + "\n";

        // SetTextOfDebugField(text);
    }

    public static void print_list_of_selected_actor_animations()
    {
        var animations = SelectedActor().guard().Animations(SelectedActor().guard().LocalStep());

        string text = "Animations:\n";
        foreach (var anim in animations)
        {
            text += anim.info() + "\n";
        }

        SetTextOfDebugField(text);
    }

    public static void print_list_of_selected_timeline_events()
    {
        // var current_timeline = Chronosphere().current_timeline();
        // var events = current_timeline.EventsAsList();

        // string text = "Timeline events:\n";
        // int count = events.Count;
        // int spos = count - 30;
        // if (spos < 0)
        // 	spos = 0;
        // for (int i = spos; i < count; i++)
        // {
        // 	var ev = events[i];
        // 	text += ev.info() + "\n";
        // }

        // text += "\n";

        // MyList<ObjectOfTimeline> actors = current_timeline.Heroes();
        // text += "Heroes: ";
        // foreach (var actor in actors)
        // {
        // 	text += actor.Name() + " ";
        // }

        // SetTextOfDebugField(text);
    }

    public static int CountLeadingZeros(int value)
    {
        int count = 0;
        while (value != 0)
        {
            value >>= 1;
            count++;
        }
        return count;
    }

    public static Vector3 RayOrigin(Vector2 mouse_position, float vertical_start)
    {
        var ray = Camera.main.ScreenPointToRay(mouse_position);
        var ydist = ray.origin.y - vertical_start;
        var direction = ray.direction;
        var shift = direction / direction.y * ydist;
        var shifted_origin = ray.origin - shift;
        return shifted_origin;
    }

    static Ray CreateRay(Vector2 mouse_position, float vertical_start)
    {
        var ray = Camera.main.ScreenPointToRay(mouse_position);
        var ydist = ray.origin.y - vertical_start;
        var direction = ray.direction;
        var shift = direction / direction.y * ydist;
        ray.origin -= shift;
        return ray;
    }

    public static Vector3 AirEnvironmentHit(Vector2 mousePosition)
    {
        float vertical_start = 4.0f;
        var shifted_origin = RayOrigin(mousePosition, vertical_start);
        return shifted_origin;
    }

    // static public float VerticalStart()
    // {
    // 	var _vertical_navigation = VerticalNavigation.Instance;
    // 	if (_vertical_navigation == null)
    // 		return Camera.main.transform.position.y;
    // 	return _vertical_navigation.GetCurrentVerticalLevel();
    // }

    public static RaycastHit CursorEnvironmentHit(
        Vector2 mousePosition,
        ref RaycastHit envhit,
        ref RaycastHit acthit,
        bool add_ui_layer,
        bool ignore_actor_layer = false
    )
    {
        //var vertical_start = VerticalStart();
        //var raylayer = CreateRay(mousePosition, vertical_start);
        Ray raylayer;
        Ray rayfull = Camera.main.ScreenPointToRay(mousePosition);

        if (VerticalNavigation.Instance != null)
        {
            raylayer = VerticalNavigation.Instance.RayForEnvironment(mousePosition);
        }
        else
        {
            raylayer = rayfull;
        }

        RaycastHit hitlayer;
        RaycastHit hitfull = default;

        int add_mask = add_ui_layer ? 1 << 5 : 0;

        int layerMask_hitfull =
            1 << (int)Layers.ACTOR_LAYER
            | 1 << (int)Layers.PROMISE_OBJECT_LAYER
            | 1 << (int)Layers.ACTOR_NON_TRANSPARENT_LAYER
            | 1 << (int)Layers.EDITOR_LAYER
            | add_mask;

        int layerMask_hitlayer =
            1 << (int)Layers.GROUND_LAYER
            | 1 << (int)Layers.DEFAULT_LAYER
            | 1 << (int)Layers.FIELD_OF_VIEW_LAYER
            | 1 << 21
            | 1 << (int)Layers.CORNER_LEAN_LAYER
            |
            //1 << (int)Layers.NAVMESH_LINK_COLLIDER_LAYER |
            add_mask;

        bool _is_down = Input.GetKey(KeyCode.Z);
        if (_is_down)
        {
            layerMask_hitlayer = 1 << 26;
        }
        bool actor_found = false;
        if (!ignore_actor_layer)
            actor_found = Physics.Raycast(rayfull, out hitfull, Mathf.Infinity, layerMask_hitfull);
        bool layer_found = Physics.Raycast(
            raylayer,
            out hitlayer,
            Mathf.Infinity,
            layerMask_hitlayer
        );

        envhit = hitlayer;
        acthit = hitfull;

        var distance_between_origins = Vector3.Distance(raylayer.origin, rayfull.origin);
        if (actor_found && layer_found)
        {
            if (hitfull.distance - distance_between_origins < hitlayer.distance)
            {
                return hitfull;
            }
            return hitlayer;
        }

        if (actor_found)
        {
            return hitfull;
        }

        if (layer_found)
        {
            return hitlayer;
        }

        return new RaycastHit();
    }

    public static RaycastHit CursorEnvironmentHit(
        Vector2 mousePosition,
        bool add_ui_layer = false,
        bool ignore_actor_layer = false
    )
    {
        RaycastHit env = new RaycastHit();
        RaycastHit act = new RaycastHit();
        return CursorEnvironmentHit(
            mousePosition,
            ref env,
            ref act,
            add_ui_layer: add_ui_layer,
            ignore_actor_layer: ignore_actor_layer
        );
    }

    public static ClickInformation CursorHit(Vector2 mouse_position, bool double_click = false)
    {
        RaycastHit envhit = new RaycastHit();
        RaycastHit acthit = new RaycastHit();
        var hit = GameCore.CursorEnvironmentHit(
            mouse_position,
            ref envhit,
            ref acthit,
            add_ui_layer: true
        );
        if (hit.collider == null)
            return new ClickInformation();

        var obj = hit.collider.gameObject;
        var layer = obj.layer;
        var pos = hit.point;

        ClickInformation clickInformation = new ClickInformation(
            actor_hit: acthit,
            environment_hit: envhit,
            actor_position: acthit.point,
            environment_position: envhit.point,
            double_click: double_click
        );
        return clickInformation;
    }

    public static int GetNavmMeshAreaForPosition(Vector3 pos)
    {
        UnityEngine.AI.NavMeshHit hit;
        UnityEngine.AI.NavMesh.SamplePosition(pos, out hit, 100, UnityEngine.AI.NavMesh.AllAreas);
        return CountLeadingZeros(hit.mask) - 1; // Почему они смещены на 1?
    }

    public static Actor GetClosestActor(Vector3 pos, MyList<ObjectOfTimeline> ignore)
    {
        return Utility.GetClosestActor(pos, Chronosphere().current_timeline(), ignore);
    }

    static float Distance2(Vector3 a, Vector3 b)
    {
        return (a - b).sqrMagnitude;
    }

    public static bool IsCanHear(ObjectOfTimeline actor, ObjectOfTimeline target, float radius)
    {
        var distance = Distance2(actor.TorsoPosition(), target.TorsoPosition());
        if (distance > radius * radius)
        {
            return false;
        }
        return true;
    }

    public static void maximize_timeline_map()
    {
        // get TimelineGraphCamera
        var timeline_graph_camera = GameObject.Find("TimelineGraphCamera");
        var tg = timeline_graph_camera.GetComponent<TimelineGraph>();
        tg.MaximizeSwap();
    }

    public static void UpdateTimelineSightMatrix(ITimeline tl)
    {
        //try {
#if UNITY_64
        var timeline_controller = ChronosphereController.instance.GetTimelineController(tl);
        timeline_controller.UpdateObjectPositions();
        Physics.Simulate(Time.fixedDeltaTime);
#endif
        Raycaster.TestSightPhase(tl as Timeline);
        // }
        // catch
        // {
        // 	throw;
        // }
    }

    public static string WithoutPostfix(string str)
    {
        var lst = str.Split("|");
        return lst[0];
    }

    // Проверяет, может ли попасть из предмета
    // похожего на пистолет.
    public static bool InLineOfSight(
        ObjectOfTimeline actor,
        ObjectOfTimeline target_actor,
        float maxdistance
    )
    {
        return InLineOfSight(actor, target_actor.TorsoPosition(), maxdistance);
    }

    // Проверяет, может ли попасть из предмета
    // похожего на пистолет.
    public static bool InLineOfSight(
        ObjectOfTimeline actor,
        ReferencedPoint target,
        Timeline timeline,
        float maxdistance
    )
    {
        return InLineOfSight(actor, target.GlobalPosition(timeline), maxdistance);
    }

    public static bool InLineOfSight(
        ObjectOfTimeline actor,
        Vector3 target,
        float maxdistance,
        float epsilon = 0.03f
    )
    {
        var actor_position = actor.TorsoPosition();
        var diff = target - actor_position;
        var distance = diff.magnitude;

        if (distance > maxdistance)
        {
            return false;
        }

        var layerMask =
            1 << GROUND_LAYER
            | 1 << OBSTACLES_LAYER
            | 1 << DEFAULT_LAYER
            | 1 << (int)Layers.ACTOR_NON_TRANSPARENT_LAYER;

        RaycastHit hit;
        if (!Physics.Raycast(actor_position, diff, out hit, distance, layerMask))
        {
            return true;
        }

        var hit_distance = hit.distance;
        if (Mathf.Abs(hit_distance - distance) < epsilon)
        {
            return true;
        }

        return false;
    }

    public static void environment_hover(Vector3 pos, GameObject go)
    {
        CursorController.Instance.SetCursor(CursorType.Default);
        //return;

        var selected_object = SelectedActor();
        if (selected_object == null)
            return;

        if (selected_object.GetComponent<DroneController>() != null)
        {
            var drone = selected_object.GetComponent<DroneController>();
            PathViewer.Instance.DrawLine(pos, pos + new Vector3(0, drone.AirLevel, 0));
            return;
        }

        PathViewer.Instance.UpdatePathView(pos, go, selected_object.GetObject().NavArea());
    }

    static void SetGreenHologramInPosition(
        GameObject green_hologram,
        AnimateController animation_controller,
        Vector3 pos,
        Quaternion rot,
        AnimationType animtype
    )
    {
        var rig_controller = green_hologram.GetComponent<RigController>();

        if (animation_controller != null)
        {
            var animation = animation_controller.GetAnimationByName(animtype);

            if (animation != null)
            {
                var final_state = animation.FinalState(null);
                rig_controller.Apply(final_state);
            }
        }

        green_hologram.SetActive(true);
        green_hologram.transform.position = pos;
        green_hologram.transform.rotation = rot;
    }

    static void SetGreenHologramInBracedPosition(
        GameObject green_hologram,
        AnimateController animation_controller,
        Vector3 pos,
        Quaternion rot
    )
    {
        SetGreenHologramInPosition(
            green_hologram,
            animation_controller,
            pos,
            rot,
            AnimationType.IdleToBraced_BracedPhase
        );
    }

    public static void climbing_block_hover(Vector3 glbpos, GameObject go)
    {
        var chronosquad_controller = ChronosphereController.instance;
        if (go == null)
        {
            chronosquad_controller.DisableCurrentGreenHologram();
            return;
        }

        var climbing_block = go.transform.parent.GetComponent<CommonClimbingBlock>();
        var braced_coordinates = climbing_block.GetBracedCoordinates(glbpos);

        var selected_object = chronosquad_controller.SelectedActor();

        if (selected_object == null)
            return;

        Debug.Log("climbing_block_hover:" + braced_coordinates.Rotation);

        var green_hologram = chronosquad_controller.GreenHologram(selected_object.gameObject);
        var animation_controller = selected_object.GetComponent<AnimateController>();
        SetGreenHologramInBracedPosition(
            green_hologram,
            animation_controller,
            braced_coordinates.TopPosition,
            braced_coordinates.Rotation
        );

        //PathFinding.UpdatePathViewToBraced(braced_coordinates, go);
    }

    public static void editor_object_click(Vector3 glbpos, GameObject go)
    {
        EditorMarker.Instance.SetMarkerObject(go);
    }

    public static void promise_click(Vector3 glbpos, GameObject go)
    {
        Debug.Log("promise_click");

        PromiseMark promiseMark = go.GetComponent<PromiseMark>();
        if (promiseMark == null)
        {
            Debug.Log("promise_click promiseMark is null");
            return;
        }
        ObjectId objid = promiseMark.GetObjectController();
        if (objid == default(ObjectId))
        {
            Debug.Log("promise_click objctr is null");
            return;
        }
        //Debug.Log("promise_click " + objid.name);

        Timeline timeline = GameCore.CurrentTimeline();
        var obj = timeline.GetObject(objid);

        var linkpose = (obj as Actor).PromiseMarkPose();
        ControlableActor actor = GameCore.SelectedActor();

        if (actor == null)
        {
            Debug.Log("promise_click actor is null");
            return;
        }

        actor.on_promise_clicked_while_selected(glbpos, false, go);
        //actor.on_enviroment_clicked_while_selected(glbpos, false);
    }

    public static void corner_lean_hover(Vector3 glbpos, GameObject go)
    {
        var chronosquad_controller = ChronosphereController.instance;
        if (go == null)
        {
            chronosquad_controller.DisableCurrentGreenHologram();
            return;
        }

        var corner_lean_block = go.GetComponent<CornerLeanZone>();
        var braced_coordinates = corner_lean_block.GetBracedCoordinates();

        var selected_object = chronosquad_controller.SelectedActor();

        if (selected_object == null)
            return;

        var green_hologram = chronosquad_controller.GreenHologram(selected_object.gameObject);
        var animation_controller = selected_object.GetComponent<AnimateController>();

        AnimationType lean_animation =
            braced_coordinates.CornerLean == CornerLeanZoneType.Right
                ? AnimationType.LeanStandRight
                : AnimationType.LeanStandLeft;

        SetGreenHologramInPosition(
            green_hologram,
            animation_controller,
            braced_coordinates.TopPosition,
            braced_coordinates.Rotation,
            lean_animation
        );

        PathViewer.Instance.UpdatePathViewToLean(braced_coordinates, go);
    }

    public static string DialoguePathBase()
    {
        return Application.streamingAssetsPath + "/Dialogue/Ru/";
    }

    public static string GeometryTexturePath()
    {
        return Application.streamingAssetsPath + "/GeometryTexture/";
    }

    public static string GeometryTextureForScenePath(string scene_name)
    {
        return Application.streamingAssetsPath + "/GeometryTexture/" + scene_name + "/";
    }

    public static Vector3 NormalForSurfacePoint(Vector3 pos)
    {
        var colliders = Physics.OverlapSphere(pos, 0.1f, 1 << (int)Layers.DEFAULT_LAYER);

        if (colliders.Length == 0)
        {
            return Vector3.up;
        }

        BSPTree bsptree = null;
        foreach (var col in colliders)
        {
            bsptree = col.GetComponent<BSPTree>();
            if (bsptree != null)
            {
                break;
            }
        }

        if (bsptree == null)
        {
            Debug.Log("BSPTree not found");
            return Vector3.up;
        }

        //Vector3 point = bsptree.ClosestPointOn(pos, 10000000.0f);

        Vector3 normal = bsptree.NormalForClossesPointOn(pos, 10000000.0f);
        return normal;
    }

    public static void climbing_surface_hover(Vector3 glbpos, GameObject go) { }

    public static MyList<T> GetChildrenComponentsRecurse<T>(GameObject go, MyList<T> result = null)
        where T : Component, new()
    {
        if (result == null)
        {
            result = new MyList<T>();
        }

        foreach (Transform child in go.transform)
        {
            var component = child.gameObject.GetComponent<T>();
            if (component != null)
            {
                result.Add(component);
            }
            GetChildrenComponentsRecurse(child.gameObject, result);
        }

        return result;
    }

    public static void hover_actor(GameObject obj, int layer)
    {
        if (obj == null)
        {
            ObjectController.NoOneHovered();
            return;
        }

        var objctr = FindObjectControllerInParentTree(obj);
        objctr.OnHover();

        var selected_actor = SelectedActor();
        if (selected_actor == null)
        {
            CursorController.Instance.SetCursor(CursorType.Default);
            return;
        }
        else
            selected_actor.on_hover_another_while_selected(objctr.gameObject, layer);
    }

    public static int? GetNavMeshAgentID(string name)
    {
        for (int i = 0; i < NavMesh.GetSettingsCount(); i++)
        {
            NavMeshBuildSettings settings = NavMesh.GetSettingsByIndex(index: i);
            if (name == NavMesh.GetSettingsNameFromID(agentTypeID: settings.agentTypeID))
            {
                return settings.agentTypeID;
            }
        }
        return null;
    }

    public static void SetLayerRecursevely(GameObject go, int layer)
    {
        go.layer = layer;
        foreach (Transform child in go.transform)
        {
            SetLayerRecursevely(child.gameObject, layer);
        }
    }

    public static Vector3 CameraUp()
    {
        return Camera.main.transform.up;
    }

    public static Vector3 CameraPosition()
    {
        return Camera.main.transform.position;
    }

    public static void LevelComplete()
    {
        Debug.Log("LevelComplete");
        SceneManager.LoadScene("Menu");
    }

    public static void hover_unkown(GameObject obj, int layer)
    {
        PathViewer.Instance.DisableView();
    }

    public static void navmeshlink_hover(Vector3 pos, GameObject go)
    {
        var on_bottom_script = go.GetComponent<OnBottomMove>();

        if (on_bottom_script != null)
        {
            bool is_ctrl_pressed =
                Input.GetKey(KeyCode.LeftControl) || Input.GetKey(KeyCode.RightControl);
            if (is_ctrl_pressed)
            {
                //int bottom_area = (int)Areas.BOTTOM_AREA_MASK;
                //var position_on_bottom_navmesh = GameCore.NavSamplePosition(pos, bottom_area);
            }
        }

        var selected_object = SelectedActor();
        PathViewer.Instance.UpdatePathView(pos, go, selected_object.GetObject().NavArea());
    }

    public static void navmeshlink_click(Vector3 pos, bool double_click, GameObject go)
    {
        // Debug.Log("navmeshlink_click");
        // if (Chronosphere().selected_object() == null)
        // 	return;

        // var chronosquad_controller = GetChronosphereController();
        // NavMeshLink link = NavMeshLinkSupervisor.GetLinkByCollider(go);

        // BracedCoordinates braced_coordinates = NavMeshLinkSupervisor.GetBracedCoordinatesByLink(
        // 	link,
        // 	pos
        // );
        // var braced_direction = braced_coordinates.Direction;
        // braced_direction.y = 0;
        // braced_direction.Normalize();

        // var top_position = braced_coordinates.TopPosition;

        // SelectedActor().on_braced_clicked_while_selected(top_position, double_click, go);
    }

    public static void climbing_block_click(
        Vector3 pos,
        bool double_click,
        GameObject go,
        ClickInformation click
    )
    {
        if (SelectedActor() == null)
            return;

        var climbing_block = go.transform.parent.GetComponent<CommonClimbingBlock>();
        var braced_coordinates = climbing_block.GetBracedCoordinates(pos);

        SelectedActor()
            .on_braced_clicked_while_selected(
                braced_coordinates.NavPosition,
                double_click,
                go,
                braced_coordinates,
                click
            );

        ChronosphereController.instance.ResetTimeSpirit();
    }

    public static int NavSampleAreaMask(Vector3 pos)
    {
        UnityEngine.AI.NavMeshHit hit;
        UnityEngine.AI.NavMesh.SamplePosition(pos, out hit, 100, UnityEngine.AI.NavMesh.AllAreas);
        return hit.mask;
    }

    public static void corner_lean_click(
        Vector3 pos,
        bool double_click,
        GameObject go,
        ClickInformation click
    )
    {
        if (SelectedActor() == null)
            return;

        var block = go.transform.GetComponent<CornerLeanZone>();
        var braced_coordinates = block.GetBracedCoordinates();

        SelectedActor()
            .on_lean_clicked_while_selected(
                braced_coordinates.TopPosition,
                double_click,
                go,
                braced_coordinates,
                click
            );

        ChronosphereController.instance.ResetTimeSpirit();
    }

    public static Vector3 GetGravityInGlobalPoint(Vector3 pnt, PlatformAreaBase platform)
    {
        if (ChronosphereController.instance == null)
        {
            return Vector3.down * 9.8f;
        }

        return ChronosphereController.instance.GetGravityInGlobalPoint(pnt, platform);
    }

    public static Vector3 GetGravityInGlobalPoint(Vector3 pnt, ObjectId platform)
    {
        if (ChronosphereController.instance == null)
        {
            return Vector3.down * 9.8f;
        }

        return ChronosphereController.instance.GetGravityInGlobalPoint(pnt, platform);
    }

    public static void link_camera_to_platform()
    {
        var mouse_position = Input.mousePosition;
        var ray = Camera.main.ScreenPointToRay(mouse_position);
        var layerMask = 1 << 0 | 1 << 6 | 1 << 7;
        if (Physics.Raycast(ray, out RaycastHit hit, 200, layerMask))
        {
            var go = hit.collider.gameObject;
            AbstractCameraController.Instance.ChangeCameraFrame(go.transform);
        }
    }

    public static PlatformView FindPlatformInGameObjectIerarchy(GameObject go)
    {
        var platform_view = go.GetComponent<PlatformView>();
        if (platform_view != null)
        {
            return platform_view;
        }

        var parent = go.transform.parent;
        if (parent == null)
        {
            return null;
        }

        return FindPlatformInGameObjectIerarchy(parent.gameObject);
    }

    // static public PlatformView FindPlatform(string name)
    // {
    // 	var platform = ChronosphereController.GetPlatform(name);
    // 	if (platform != null)
    // 	{
    // 		return platform;
    // 	}
    // 	return platform;

    // }

    static MaterialKeeper FindMaterialKeeperOnScene()
    {
        var material_keeper = GameObject.Find("MaterialKeeper");
        if (material_keeper == null)
        {
            Debug.Log("MaterialKeeper not found");
            return null;
        }
        return material_keeper.GetComponent<MaterialKeeper>();
    }

    static GameObject FindPrefabInMaterialKeeper(string name)
    {
        var material_keeper = FindMaterialKeeperOnScene();
        if (material_keeper == null)
        {
            return null;
        }
        return material_keeper.GetPrefab(name);
    }

    public static string MakeUnicalName(string name)
    {
        var unical_name = name;
        var i = 0;
        while (GameObject.Find(unical_name) != null)
        {
            unical_name = name + i.ToString();
            i++;
        }
        Debug.Log("Unical name: " + unical_name);
        return unical_name;
    }

#if UNITY_EDITOR
    public static void PlacePrefab(
        string prefab_name,
        string place_with_name,
        Vector3 pos,
        Quaternion rot
    )
    {
        var prefab = GameCore.FindPrefabInMaterialKeeper(prefab_name);
        if (prefab == null)
        {
            Debug.Log("Prefab not found");
            return;
        }
        var go = GameObject.Instantiate(prefab, pos, rot);
        go.name = place_with_name;

        // find original timeline
        var original_timeline = GameObject.Find("Original");
        if (original_timeline == null)
        {
            Debug.Log("Original timeline not found");
            return;
        }

        go.transform.parent = original_timeline.transform;

        // mark scene as dirty
        EditorSceneManager.MarkSceneDirty(EditorSceneManager.GetActiveScene());
    }
#endif

    public static GameObject GetOriginalTimelineGO()
    {
        var tl = GameObject.Find("Original");
        if (tl == null)
        {
            Debug.Log("Original timeline not found");
            return null;
        }
        return tl;
    }
}
