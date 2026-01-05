using System.Collections;
using System.Collections.Generic;
using System.Linq;
#if UNITY_64
using UnityEngine;
using UnityEngine.UI;
#endif

public class UserInterfaceCanvas : MonoBehaviour
{
    public static UserInterfaceCanvas Instance;

    Canvas canvas;
    GameObject fps_info;

    // font
    TMPro.TMP_FontAsset _font;

    TMPro.TextMeshProUGUI dialogue_text_element;
    TMPro.TextMeshProUGUI clock_text_element;
    TMPro.TextMeshProUGUI debug_text_field;

    GameObject IconLayout;
    GameObject ActivityLayout;

    //TextFlowController _text_flow_controller;

    MyList<Activity> _activities_1;
    MyList<Activity> _activities_2;

    MyList<Activity> _activities_on_panel = new MyList<Activity>();
    MyList<Activity> _activities_on_vertical_panel = new MyList<Activity>();
    MyList<IconedActor> _iconed_actors = new MyList<IconedActor>();
    double filtered_fps = 0.0;
    bool _debug_info_mode = false;

    // tooltip
    GameObject _tooltip;
    GameObject _tooltip_marker;

    ChronosphereController _chronosphere_controller;

    float LEFT_CORN = 0.15f;

    public void SetDebugInfoMode(bool mode)
    {
        _debug_info_mode = mode;
    }

    Texture2D create_monocollored_texture(Color color, int width, int height)
    {
        Texture2D tex = new Texture2D(width, height);
        for (int y = 0; y < tex.height; ++y)
        {
            for (int x = 0; x < tex.width; ++x)
            {
                tex.SetPixel(x, y, color);
            }
        }
        tex.Apply();
        return tex;
    }

    public bool HasActorIcon(string object_id)
    {
        foreach (IconedActor iconed in _iconed_actors)
        {
            if (iconed.name == object_id)
            {
                return true;
            }
        }
        return false;

        //return _iconed_actors.Any((iconed) => iconed.name == object_id);
    }

    TMPro.TextMeshProUGUI CreateTextMarker(TMPro.TextMeshProUGUI text_element)
    {
        var element = new GameObject("Mark" + text_element.name);
        element.transform.SetParent(canvas.transform, false);
        var mark_text_element = element.AddComponent<TMPro.TextMeshProUGUI>();
        mark_text_element.text = text_element.text;
        mark_text_element.fontSize = text_element.fontSize;
        mark_text_element.color = text_element.color;
        mark_text_element.alignment = text_element.alignment;
        mark_text_element.textWrappingMode = text_element.textWrappingMode;
        mark_text_element.rectTransform.anchorMax = text_element.rectTransform.anchorMax;
        mark_text_element.rectTransform.anchorMin = text_element.rectTransform.anchorMin;
        MirrorMarker mel = element.AddComponent<MirrorMarker>();
        mel.SetPrototype(text_element);

        {
            // It is black magic for change elements order in graphic stack.
            text_element.transform.SetParent(null, false);
            text_element.transform.SetParent(canvas.transform, false);
        }

        return mark_text_element;
    }

    public static TMPro.TextMeshProUGUI CreateTextMarker(
        Canvas canvas,
        TMPro.TextMeshProUGUI text_element
    )
    {
        var element = new GameObject("Mark" + text_element.name);
        element.transform.SetParent(canvas.transform, false);
        var mark_text_element = element.AddComponent<TMPro.TextMeshProUGUI>();
        mark_text_element.text = text_element.text;
        mark_text_element.fontSize = text_element.fontSize;
        mark_text_element.color = text_element.color;
        mark_text_element.alignment = text_element.alignment;
        mark_text_element.textWrappingMode = text_element.textWrappingMode;
        mark_text_element.rectTransform.anchorMax = text_element.rectTransform.anchorMax;
        mark_text_element.rectTransform.anchorMin = text_element.rectTransform.anchorMin;
        MirrorMarker mel = element.AddComponent<MirrorMarker>();
        mel.SetPrototype(text_element);

        {
            // It is black magic for change elements order in graphic stack.
            text_element.transform.SetParent(null, false);
            text_element.transform.SetParent(canvas.transform, false);
        }

        return mark_text_element;
    }

    TMPro.TextMeshProUGUI CreateTextField(
        string name,
        string text,
        Vector2 anchor_min,
        Vector2 anchor_max
    )
    {
        var element = new GameObject(name);
        element.transform.SetParent(canvas.transform, false);
        var text_element = element.AddComponent<TMPro.TextMeshProUGUI>();
        text_element.text = text;
        text_element.fontSize = 14;
        text_element.color = Color.white;
        text_element.alignment = TMPro.TextAlignmentOptions.TopLeft;
        text_element.textWrappingMode = TMPro.TextWrappingModes.Normal;
        text_element.rectTransform.anchorMax = anchor_max;
        text_element.rectTransform.anchorMin = anchor_min;
        CreateTextMarker(text_element);
        return text_element;
    }

    TMPro.TextMeshProUGUI CreateDebugText()
    {
        return CreateTextField("DebugText", "", new Vector2(0.5f, 0.1f), new Vector2(1f, 0.8f));
    }

    void create_dialogue_text_element()
    {
        var element = new GameObject("DialogueText");
        element.transform.SetParent(canvas.transform, false);
        var text_element = element.AddComponent<TMPro.TextMeshProUGUI>();
        text_element.text = "> Initial message. System test.";
        text_element.fontSize = 14;
        text_element.color = Color.green;
        text_element.alignment = TMPro.TextAlignmentOptions.TopLeft;
        text_element.textWrappingMode = TMPro.TextWrappingModes.Normal;
        text_element.rectTransform.anchorMax = new Vector2(0.5f, 0.3f);
        text_element.rectTransform.anchorMin = new Vector2(0.3f, 0.1f);
        dialogue_text_element = text_element;
        dialogue_text_element.gameObject.AddComponent<TextFlowController>();

        CreateTextMarker(text_element);
    }

    void create_clock_text_element()
    {
        var element = new GameObject("CurrentTime");
        element.transform.SetParent(canvas.transform, false);
        var text_element = element.AddComponent<TMPro.TextMeshProUGUI>();
        text_element.text = "0.0";

        text_element.fontSize = 24;
        text_element.color = Color.white;
        text_element.alignment = TMPro.TextAlignmentOptions.TopLeft;
        text_element.textWrappingMode = TMPro.TextWrappingModes.Normal;

        text_element.rectTransform.anchorMax = new Vector2(0.55f, 0.90f);
        text_element.rectTransform.anchorMin = new Vector2(0.50f, 0.89f);

        clock_text_element = text_element;
        CreateTextMarker(text_element);
    }

    public void SetTextOfDebugField(string text)
    {
        debug_text_field.text = text;
    }

    void Awake()
    {
        Instance = this;
        IconLayout = this.transform.Find("IconLayout").gameObject;
        ActivityLayout = this.transform.Find("ActivityLayout").gameObject;
    }

    void Start()
    {
        _font = MaterialKeeper.Instance.GetTMPFont("Naga");
        _chronosphere_controller = GameCore.GetChronosphereController();

        canvas = this.GetComponent<Canvas>();
        create_clock_text_element();
        draw_timeline_image();

        setup_fps_counter();
        debug_text_field = CreateDebugText();

        CreateNovelScreen();
    }

    public void CreateNovelScreen()
    {
        var novel_screen = new GameObject("NovelScreen");
        novel_screen.transform.SetParent(canvas.transform, false);
        var novel_screen_component = novel_screen.AddComponent<NovelScreen>();
        novel_screen.transform.localScale = new Vector3(1, 1, 1);
        novel_screen.transform.localPosition = new Vector3(0, 0, 0);
        novel_screen_component.SetCanvas(canvas);
    }

    void setup_fps_counter()
    {
        // create text element
        fps_info = new GameObject("FPSInfo");
        fps_info.transform.SetParent(canvas.transform, false);
        var text_element = fps_info.AddComponent<TMPro.TextMeshProUGUI>();
        text_element.text = "FPS: 0.0";

        text_element.fontSize = 14;
        text_element.font = _font;
        text_element.color = Color.white;
        text_element.alignment = TMPro.TextAlignmentOptions.TopLeft;
        text_element.textWrappingMode = TMPro.TextWrappingModes.Normal;
        text_element.rectTransform.anchorMax = new Vector2(LEFT_CORN + 0.15f, 0.90f);
        text_element.rectTransform.anchorMin = new Vector2(LEFT_CORN, 0.89f);

        CreateTextMarker(text_element);
    }

    string current_timeline_string()
    {
        var timeline = _chronosphere_controller.Chronosphere().current_timeline();
        return timeline.name();
    }

    void update_current_time()
    {
        var timeline = _chronosphere_controller.Chronosphere().CurrentTimeline();
        double current_time = _chronosphere_controller
            .Chronosphere()
            .current_timeline()
            .current_time();
        double last_timeline_time = _chronosphere_controller
            .Chronosphere()
            .current_timeline()
            .last_timeline_time();
        double diff = timeline.CurrentToPresentDiffereceSeconds();
        long current_step = timeline.CurrentStep();
        string text =
            (timeline.IsPresent() ? "(Настоящее)" : $"(Прошлое {diff:F2})")
            + $"\nЧасы: {current_time:F2}/{last_timeline_time:F2} : {current_step}";

        if (diff < 0)
            text =
                "Разрыв временного континуума случился по непредвиденным причинам. Пожалуйста, сообщите творцу.";

        float time_multiplier = _chronosphere_controller.Chronosphere().time_multiplier();
        string multiplier = $"Поток: {time_multiplier:F2}";

        bool editor_mode = ChronosphereController.instance.IsEditorMode();
        if (editor_mode)
        {
            text += "\nРежим редактора";
        }

        clock_text_element.text = text + "\n" + multiplier;
    }

    string system_info_text()
    {
        var fps = 1.0f / Time.deltaTime;
        filtered_fps = filtered_fps * 0.9 + fps * 0.1;
        //return $"FPS: {filtered_fps:F2}\n";

        string text = "";
        text +=
            $"FPS: {filtered_fps:F2}\nGameFreq: {Utility.GAME_GLOBAL_FREQUENCY}\nCards: {BasicMultipleAction.TotalCardsCounter}";

        if (_debug_info_mode)
        {
            var selected_object = GameCore.SelectedActor();

            var memory = System.GC.GetTotalMemory(false);

            string tl_direction = _chronosphere_controller
                .Chronosphere()
                .current_timeline()
                .IsReversedPass()
                ? "Backward"
                : "Forward";

            text += $"MemoryUsage: {memory / 1024 / 1024} MB\n";
            text += $"CountOfCards: {_chronosphere_controller.Chronosphere().CountOfCards()}\n";
            //text += $"CameraPosition: {GameCore.GetCameraPosition()}\n";
            text += "\n";
            text += $"Timelines: {GameCore.timelines().Count}\n";
            text += $"TL: {current_timeline_string()}\n";
            text += $"TL_Direction: {tl_direction}\n";
            text +=
                $"Events: {_chronosphere_controller.Chronosphere().current_timeline().events_count()}\n";
            text +=
                $"CurrentStep: {_chronosphere_controller.Chronosphere().current_timeline().CurrentStep()}\n";
            text +=
                $"LastPositiveStep: {_chronosphere_controller.Chronosphere().current_timeline().LastPositiveTimelineStep()}\n";
            text +=
                $"LastNegativeStep: {_chronosphere_controller.Chronosphere().current_timeline().LastNegativeTimelineStep()}\n";

            text +=
                $"MinimalStep: {_chronosphere_controller.Chronosphere().current_timeline().MinimalStep()}\n";
            text +=
                $"MaximalStep: {_chronosphere_controller.Chronosphere().current_timeline().MaximalStep()}\n";

            text +=
                $"Прошлое: {_chronosphere_controller.Chronosphere().current_timeline().IsPast()}\n";
            text += "\n";

            if (selected_object != null)
            {
                var select_object_tmod = selected_object
                    .GetObject()
                    .object_time()
                    .ActiveModifiers()
                    .Count;
                text += "Selected:\n";
                text += $"{selected_object.Info()}\n";
            }
        }
        return text;
    }

    void update_fps_info()
    {
        fps_info.GetComponent<TMPro.TextMeshProUGUI>().text = system_info_text();
    }

    void update_cooldowns()
    {
        foreach (Activity activity in _activities_on_panel)
        {
            activity.UpdateCooldownPercent();
        }

        foreach (Activity activity in _activities_on_vertical_panel)
        {
            activity.UpdateCooldownPercent();
        }
    }

    public void KeyPressed(KeyCode key)
    {
        if (_activities_on_panel != null)
        {
            foreach (Activity activity in _activities_on_panel)
            {
                if (activity.hotkey() == key)
                {
                    activity.Click();
                    return;
                }
            }
        }
    }

    public void enable_debug_mode()
    {
        _debug_info_mode = true;
    }

    void draw_timeline_image() { }

    public void add_icon_for_actor(IconedActor actor)
    {
        var image = actor.image();
        int index = _iconed_actors.Count;

        image.transform.SetParent(IconLayout.transform, false);
        _iconed_actors.Add(actor);
    }

    void clean_activities()
    {
        foreach (Activity activity in _activities_on_panel)
        {
            activity.hide();
        }
        _activities_on_panel.Clear();
    }

    void clean_vertical_activities()
    {
        foreach (Activity activity in _activities_on_vertical_panel)
        {
            activity.hide();
        }
        _activities_on_vertical_panel.Clear();
    }

    void set_activity_to_slot(Activity activity, int slot)
    {
        // get screen height
        float screen_height = Screen.height;
        float screen_width = Screen.width;

        activity.attach_to_canvas(canvas);
        activity.show();
        activity.image().transform.SetParent(ActivityLayout.transform, false);
        _activities_on_panel.Add(activity);
    }

    void set_activity_to_vertical_slot(Activity activity, int slot)
    {
        // get screen height
        float screen_height = Screen.height;
        float screen_width = Screen.width;

        activity.attach_to_canvas(canvas);
        activity.show();

        Debug.Log($"Set activity to vertical slot {slot}");
        activity.set_position(new Vector2(1800, 200 + 120 * slot));
        _activities_on_vertical_panel.Add(activity);
    }

    public void set_activity_list_to_panel(MyList<Activity> activities)
    {
        clean_activities();

        if (activities == null)
        {
            return;
        }

        int index = 0;
        foreach (Activity activity in activities)
        {
            set_activity_to_slot(activity, index);
            index += 1;
        }
    }

    public void set_activity_list_to_vertical_panel(MyList<Activity> activities)
    {
        clean_vertical_activities();

        if (activities == null)
        {
            return;
        }

        int index = 0;
        foreach (Activity activity in activities)
        {
            set_activity_to_vertical_slot(activity, index);
            index += 1;
        }
    }

    public void set_additional_activity_list_to_panel(MyList<Activity> activities)
    {
        if (activities == null)
        {
            return;
        }

        int index = _activities_on_panel.Count + 1;
        foreach (Activity activity in activities)
        {
            set_activity_to_slot(activity, index);
            index += 1;
        }
    }

    public void SetActivities(MyList<Activity> activities)
    {
        if (_activities_1 != activities)
        {
            _activities_1 = activities;
            set_activity_list_to_panel(_activities_1);
            set_additional_activity_list_to_panel(_activities_2);
        }
    }

    public void SetVerticalActivities(MyList<Activity> activities)
    {
        set_activity_list_to_vertical_panel(activities);
    }

    public void SetAdditionalActivities(MyList<Activity> activities)
    {
        if (activities == null && _activities_2 == null)
        {
            return;
        }

        if (_activities_2 != activities)
        {
            if (_activities_2 != null)
            {
                var acts = new MyList<Activity>();
                _activities_2 = null;
                set_activity_list_to_panel(_activities_1);
                set_additional_activity_list_to_panel(acts);
            }

            _activities_2 = activities;
            set_activity_list_to_panel(_activities_1);
            set_additional_activity_list_to_panel(_activities_2);
        }
    }

    public void clean_activities_on_panel()
    {
        clean_activities();
    }

    public void select_hero(int hero_id)
    {
        if (hero_id > _iconed_actors.Count)
        {
            return;
        }

        _iconed_actors[hero_id - 1].clicked();
    }

    float XUnitForPixel(float pixel)
    {
        return pixel / Screen.width;
    }

    float YUnitForPixel(float pixel)
    {
        return pixel / Screen.height;
    }

    float XPixelForUnit(float unit)
    {
        return unit * Screen.width;
    }

    float YPixelForUnit(float unit)
    {
        return unit * Screen.height;
    }

    void ShowTooltip(Activity activity)
    {
        if (_tooltip != null)
        {
            Destroy(_tooltip);
            Destroy(_tooltip_marker);
        }

        var key = activity.hotkey();
        var cooldown = activity.CooldownTime();
        var text = activity.TooltipText() + $"\n\nКлавиша: {key}" + $"\nОткат: {cooldown}";

        var element = new GameObject("Tooltip");
        element.layer = 5;
        var text_element = element.AddComponent<TMPro.TextMeshProUGUI>();
        text_element.text = text;
        text_element.font = MaterialKeeper.Instance.GetTMPFont("Naga");
        text_element.fontSize = 22;
        text_element.color = Color.white;
        text_element.alignment = TMPro.TextAlignmentOptions.TopLeft;
        text_element.textWrappingMode = TMPro.TextWrappingModes.Normal;
        _tooltip = element;

        var tooltip_offset = activity.TooltipOffset();

        var corner = activity.RightTopCorner();
        var xcenter = XUnitForPixel(corner.x + tooltip_offset.x);
        var ycenter = YUnitForPixel(corner.y + 100 + tooltip_offset.y);

        text_element.rectTransform.anchorMax = new Vector2(xcenter, ycenter);
        text_element.rectTransform.anchorMin = new Vector2(xcenter, ycenter);

        int pixel_width = 300;
        int pixel_height = 140;

        text_element.rectTransform.sizeDelta = new Vector2(pixel_width, pixel_height);

        _tooltip_marker = new GameObject("TooltipMarker");
        _tooltip_marker.transform.SetParent(canvas.transform, false);
        element.transform.SetParent(canvas.transform, false);

        // create rectangle with shader for tooltip marker
        var image = _tooltip_marker.AddComponent<Image>();
        var material = new Material(MaterialKeeper.Instance.GetMaterial("TooltipMarker"));

        image.color = Color.white;
        image.rectTransform.sizeDelta = new Vector2(pixel_width + 50, pixel_height + 50);
        image.material = material;
        image.rectTransform.anchorMax = new Vector2(xcenter, ycenter);
        image.rectTransform.anchorMin = new Vector2(xcenter, ycenter);

        material.SetFloat("Width", pixel_width + 50);
        material.SetFloat("Height", pixel_height + 50);
        material.SetFloat("Transparency", 1.0f);
    }

    void ShowTooltip(IconedActor activity)
    {
        if (_tooltip != null)
        {
            Destroy(_tooltip);
            Destroy(_tooltip_marker);
        }

        var text = activity.TooltipText;

        var element = new GameObject("Tooltip");
        element.layer = 5;
        var text_element = element.AddComponent<TMPro.TextMeshProUGUI>();
        text_element.text = text;
        text_element.font = MaterialKeeper.Instance.GetTMPFont("Naga");
        text_element.fontSize = 22;
        text_element.color = Color.white;
        text_element.alignment = TMPro.TextAlignmentOptions.TopLeft;
        text_element.textWrappingMode = TMPro.TextWrappingModes.Normal;
        _tooltip = element;

        var corner = activity.RightTopCorner();
        var xcenter = XUnitForPixel(corner.x);
        var ycenter = YUnitForPixel(corner.y + 100);

        text_element.rectTransform.anchorMax = new Vector2(xcenter, ycenter);
        text_element.rectTransform.anchorMin = new Vector2(xcenter, ycenter);

        int pixel_width = 300;
        int pixel_height = 140;

        text_element.rectTransform.sizeDelta = new Vector2(pixel_width, pixel_height);

        _tooltip_marker = new GameObject("TooltipMarker");
        _tooltip_marker.transform.SetParent(canvas.transform, false);
        element.transform.SetParent(canvas.transform, false);

        // create rectangle with shader for tooltip marker
        var image = _tooltip_marker.AddComponent<Image>();
        var material = new Material(MaterialKeeper.Instance.GetMaterial("TooltipMarker"));

        image.color = Color.white;
        image.rectTransform.sizeDelta = new Vector2(pixel_width + 50, pixel_height + 50);
        image.material = material;
        image.rectTransform.anchorMax = new Vector2(xcenter, ycenter);
        image.rectTransform.anchorMin = new Vector2(xcenter, ycenter);

        material.SetFloat("Width", pixel_width + 50);
        material.SetFloat("Height", pixel_height + 50);
        material.SetFloat("Transparency", 1.0f);
    }

    void HideTooltip()
    {
        if (_tooltip != null)
        {
            Destroy(_tooltip);
            Destroy(_tooltip_marker);
        }
    }

    public void UpdateIconTooltips()
    {
        foreach (IconedActor actor in _iconed_actors)
        {
            if (actor.IsMouseOverImage())
            {
                ShowTooltip(actor);
                return;
            }
        }

        foreach (Activity activity in _activities_on_panel)
        {
            if (activity.IsMouseOverImage())
            {
                ShowTooltip(activity);
                return;
            }
        }

        foreach (Activity activity in _activities_on_vertical_panel)
        {
            if (activity.IsMouseOverImage())
            {
                ShowTooltip(activity);
                return;
            }
        }

        HideTooltip();
        return;
    }

    // Update is called once per frame
    void Update()
    {
        UpdateIconTooltips();
        update_current_time();
        update_cooldowns();
        update_fps_info();
    }

    public bool Click(Vector2 position)
    {
        foreach (IconedActor actor in _iconed_actors)
        {
            if (actor.IsMouseOverImage())
            {
                actor.clicked();
                return true;
            }
        }

        foreach (Activity activity in _activities_on_panel)
        {
            if (activity.IsMouseOverImage())
            {
                activity.Click();
                return true;
            }
        }

        foreach (Activity activity in _activities_on_vertical_panel)
        {
            if (activity.IsMouseOverImage())
            {
                activity.Click();
                return true;
            }
        }

        return false;
    }
}
