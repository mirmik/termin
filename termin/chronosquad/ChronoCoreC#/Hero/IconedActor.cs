using System.Collections;
using System.Collections.Generic;
#if UNITY_64
using UnityEngine;
using UnityEngine.UI;
#endif

public class IconedActor : MonoBehaviour
{
    static Dictionary<string, Sprite> _sprites = new Dictionary<string, Sprite>();

    Canvas canvas;
    UserInterfaceCanvas _user_interface_canvas;

    string _actor_id;

    GameObject _icon_object;

    //Texture2D _texture;
    Sprite _sprite;

    float _last_click_time = 0;

    public Texture2D ActorIconTexture;
    public Image ActorIcon;

    public string TooltipText = "TooltipText";

    MyList<Activity> _activities = new MyList<Activity>();

    void Start()
    {
        var controlable_actor = this.GetComponent<ControlableActor>();
        _actor_id = this.name;
        InstalIconIfNeed();
    }

    ControlableActor Actor()
    {
        var current_timeline_controller = GameCore.CurrentTimelineController();
        current_timeline_controller.GetControlableActor(_actor_id);
        return current_timeline_controller.GetControlableActor(_actor_id);
    }

    public Vector2 RightTopCorner()
    {
        var rect = _icon_object.GetComponent<RectTransform>();
        var position = _icon_object.transform.position;
        var size = rect.sizeDelta;
        return new Vector2(position.x + size.x / 2 + 100, position.y + size.y / 2);
    }

    public void InstalIconIfNeed()
    {
        var chronosphere_controller = GameObject
            .Find("ChronoSphere")
            .GetComponent<ChronoSphereMain>();
        canvas = chronosphere_controller.user_interface_canvas();
        _user_interface_canvas = canvas.GetComponent<UserInterfaceCanvas>();

        if (_user_interface_canvas.HasActorIcon(_actor_id))
        {
            return;
        }

        _icon_object = new GameObject("IconObject");
        _icon_object.layer = 5;

        ActorIcon = _icon_object.AddComponent<Image>();

        var uniqname = ActorIconTexture.name;
        if (_sprites.ContainsKey(uniqname))
        {
            _sprite = _sprites[uniqname];
        }
        else
        {
            _sprite = GameCore.LazySpriteGenerate(ActorIconTexture);
            _sprites.Add(uniqname, _sprite);
        }

        ActorIcon.sprite = _sprite;
        ActorIcon.transform.SetParent(canvas.transform, false);
        _user_interface_canvas.add_icon_for_actor(this);
    }

    public void double_clicked()
    {
        Actor().double_clicked_by_interface();
    }

    public void clicked()
    {
        if (Time.time - _last_click_time < 0.5f)
        {
            double_clicked();
            return;
        }

        GameCore.SelectActor(Actor().gameObject);
        _last_click_time = Time.time;
    }

    public Image image()
    {
        return ActorIcon;
    }

    public Sprite sprite()
    {
        return _sprite;
    }

    void Update() { }

    public void set_icon_position(Vector2 position)
    {
        _icon_object.transform.position = new Vector3(position.x, position.y, 0);
    }

    public bool IsMouseOverImage()
    {
        Vector3 mouse_position = Input.mousePosition;
        Vector2 image_position = new Vector2(
            _icon_object.transform.position.x,
            _icon_object.transform.position.y
        );
        Vector2 image_size = _icon_object.GetComponent<RectTransform>().sizeDelta;
        float image_width = image_size.x;
        float image_height = image_size.y;

        if (
            mouse_position.x > image_position.x - image_width / 2
            && mouse_position.x < image_position.x + image_width / 2
        )
        {
            if (
                mouse_position.y > image_position.y - image_height / 2
                && mouse_position.y < image_position.y + image_height / 2
            )
            {
                return true;
            }
        }

        return false;
    }
}
