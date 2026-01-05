using System.Collections;
using System.Collections.Generic;
using System;

#if UNITY_64 || UNITY_EDITOR
using UnityEngine;
using UnityEngine.UIElements;
#endif

public class FunctionKeyTester : MonoBehaviour, IKeyboardReceiver
{
    TimelineGraph time_line_graph;
    MiniMap mini_map;

    bool[] function_keys_pressed = new bool[64];

    Dictionary<KeyCode, AnalyzedKey> keys_list = new Dictionary<KeyCode, AnalyzedKey>();

    UserInterfaceCanvas user_interface_canvas;

    void keys_list_Add(AnalyzedKey key)
    {
        keys_list.Add(key.code, key);
    }

    void Start()
    {
        user_interface_canvas = GameObject.FindFirstObjectByType<UserInterfaceCanvas>();
        time_line_graph = GameObject.Find("TimelineGraphCamera")?.GetComponent<TimelineGraph>();
        mini_map = GameObject.Find("MiniMapCamera")?.GetComponent<MiniMap>();

        keys_list = new Dictionary<KeyCode, AnalyzedKey>();
        keys_list_Add(new AnalyzedKey(KeyCode.F1, GameCore.f1_key_pressed_event));
        keys_list_Add(new AnalyzedKey(KeyCode.F2, GameCore.f2_key_pressed_event));
        keys_list_Add(new AnalyzedKey(KeyCode.F3, GameCore.f3_key_pressed_event));
        keys_list_Add(new AnalyzedKey(KeyCode.F4, GameCore.f4_key_pressed_event));
        keys_list_Add(new AnalyzedKey(KeyCode.F5, GameCore.f5_key_pressed_event));
        keys_list_Add(new AnalyzedKey(KeyCode.F6, GameCore.f6_key_pressed_event));
        keys_list_Add(new AnalyzedKey(KeyCode.F7, GameCore.f7_key_pressed_event));
        keys_list_Add(new AnalyzedKey(KeyCode.F8, GameCore.f8_key_pressed_event));
        keys_list_Add(new AnalyzedKey(KeyCode.F9, GameCore.f9_key_pressed_event));
        keys_list_Add(new AnalyzedKey(KeyCode.F10, GameCore.f10_key_pressed_event));
        keys_list_Add(new AnalyzedKey(KeyCode.F11, GameCore.f11_key_pressed_event));
        keys_list_Add(new AnalyzedKey(KeyCode.F12, GameCore.f12_key_pressed_event));
        keys_list_Add(new AnalyzedKey(KeyCode.Space, GameCore.on_space_pressed));
        keys_list_Add(new AnalyzedKey(KeyCode.Alpha1, GameCore.on_1_pressed));
        keys_list_Add(new AnalyzedKey(KeyCode.Alpha2, GameCore.on_2_pressed));
        keys_list_Add(new AnalyzedKey(KeyCode.Alpha3, GameCore.on_3_pressed));
        keys_list_Add(new AnalyzedKey(KeyCode.Alpha4, GameCore.on_4_pressed));
        keys_list_Add(new AnalyzedKey(KeyCode.Alpha5, GameCore.on_5_pressed));
        keys_list_Add(new AnalyzedKey(KeyCode.Alpha6, GameCore.on_6_pressed));
        keys_list_Add(new AnalyzedKey(KeyCode.Alpha7, GameCore.on_7_pressed));
        keys_list_Add(new AnalyzedKey(KeyCode.Alpha8, GameCore.on_8_pressed));
        keys_list_Add(new AnalyzedKey(KeyCode.Alpha9, GameCore.on_9_pressed));
        keys_list_Add(new AnalyzedKey(KeyCode.Alpha0, GameCore.on_0_pressed));
        keys_list_Add(new AnalyzedKey(KeyCode.Tab, GameCore.on_tab_pressed));
        keys_list_Add(
            new AnalyzedKey(
                KeyCode.P,
                () =>
                {
                    GameCore.print_list_of_selected_actor_animatronis();
                }
            )
        );

        keys_list_Add(
            new AnalyzedKey(
                KeyCode.X,
                GameCore.temporary_double_time_speed,
                GameCore.temporary_normal_time_speed
            )
        );

        keys_list_Add(
            new AnalyzedKey(
                KeyCode.K,
                () =>
                {
                    GameCore.print_list_of_selected_actor_animations();
                }
            )
        );
        keys_list_Add(
            new AnalyzedKey(
                KeyCode.O,
                () =>
                {
                    GameCore.print_list_of_selected_object_time();
                }
            )
        );
        keys_list_Add(
            new AnalyzedKey(
                KeyCode.T,
                () =>
                {
                    GameCore.SelectedActor().CroachSwitch();
                }
            )
        );
        keys_list_Add(
            new AnalyzedKey(
                KeyCode.S,
                () =>
                {
                    GameCore.SelectedActor().Stop();
                    ChronosphereController.instance.ResetTimeSpirit();
                }
            )
        );
        keys_list_Add(
            new AnalyzedKey(
                KeyCode.L,
                () =>
                {
                    GameCore.print_list_of_selected_timeline_events();
                }
            )
        );
        keys_list_Add(
            new AnalyzedKey(
                KeyCode.I,
                () =>
                {
                    GameCore.print_list_of_commands();
                }
            )
        );

        // J
        keys_list_Add(
            new AnalyzedKey(
                KeyCode.J,
                () =>
                {
                    GameCore.maximize_timeline_map();
                }
            )
        );

        // Tilde
        // keys_list_Add(
        // 	new AnalyzedKey(
        // 		KeyCode.BackQuote,
        // 		() =>
        // 		{
        // 			GameCore.maximize_timeline_map();
        // 		}
        // 	)
        // );

        // N
        keys_list_Add(
            new AnalyzedKey(
                KeyCode.N,
                () =>
                {
                    GameCore.link_camera_to_platform();
                }
            )
        );

        keys_list_Add(
            new AnalyzedKey(
                KeyCode.H,
                () =>
                {
                    GameCore.toggle_outline_mode();
                }
            )
        );
        keys_list_Add(
            new AnalyzedKey(
                KeyCode.Delete,
                () =>
                {
                    GameCore.on_delete_pressed();
                }
            )
        );

        // add me to the input controller
        var input_controller = gameObject.GetComponent<InputController>();
        input_controller.PushControlReceiver(this, last: true);
    }

    public void KeyPressed(KeyCode key)
    {
        // for (int i = 0; i < keys_list.Count; i++)
        // {
        // 	if (key == keys_list[i].code)
        // 	{
        // 		if (keys_list[i].pressed == false)
        // 		{
        // 			keys_list[i].foo();
        // 		}
        // 		keys_list[i].pressed = true;
        // 		return;
        // 	}
        // }

        AnalyzedKey key_analyzed;
        if (keys_list.TryGetValue(key, out key_analyzed))
        {
            key_analyzed.KeyPressed();
        }

        if (key == KeyCode.Q)
        {
            GameCore.SetRealtimeFlow();
            return;
        }

        if (key == KeyCode.W)
        {
            GameCore.SetTimeFlow(0.3f);
            return;
        }

        if (key == KeyCode.E)
        {
            GameCore.SetTimeFlow(0.1f);
            return;
        }

        user_interface_canvas.KeyPressed(key);
    }

    public void KeyReleased(KeyCode key)
    {
        AnalyzedKey key_analyzed;
        if (keys_list.TryGetValue(key, out key_analyzed))
        {
            key_analyzed.KeyReleased();
        }
    }

    void OnGUI()
    {
        var cursor_positon = Event.current.mousePosition;
        if (time_line_graph != null && time_line_graph.IsCursorInViewport())
        {
            return;
        }

        if (mini_map != null && mini_map.IsPointerOver(cursor_positon))
        {
            return;
        }
    }
}

public class AnalyzedKey
{
    public Action pressed_action;
    public Action released_action;
    public KeyCode code;

    public AnalyzedKey(KeyCode code, Action foo)
    {
        this.code = code;
        this.pressed_action = foo;
    }

    public AnalyzedKey(KeyCode code, Action foo, Action released_action)
    {
        this.code = code;
        this.pressed_action = foo;
        this.released_action = released_action;
    }

    public void KeyPressed()
    {
        pressed_action?.Invoke();
    }

    public void KeyReleased()
    {
        released_action?.Invoke();
    }
}
