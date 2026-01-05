using System;
using System.Collections;
using System.Collections.Generic;
#if UNITY_64
using UnityEngine;
using UnityEngine.UI;
#endif

public class Activity
{
    GameObject _activity_object;
    Image _image;

    //Image _back_image;
    //Texture2D _texture;
    Sprite _sprite;
    Button _button;
    GameAction _action_back;
    KeyCode _hotkey;
    Material _material;
    Canvas _canvas;
    Vector2 _tooltip_offset = new Vector2(0, 0);

    public Activity(Texture2D texture, GameAction clicked_action, KeyCode hotkey)
    {
        _activity_object = new GameObject("ActivityObject");
        _activity_object.layer = 5;
        _button = _activity_object.AddComponent<Button>();
        _action_back = clicked_action;
        _hotkey = hotkey;
        _material = new Material(Shader.Find("Unlit/ActivityImageShader"));

        setup_image(texture);
        hide();
    }

    public float CooldownTime()
    {
        return _action_back.CooldownTime();
    }

    public Image image()
    {
        return _image;
    }

    public GameObject activity_object()
    {
        return _activity_object;
    }

    void setup_image(Texture2D tex)
    {
        _image = _activity_object.AddComponent<Image>();
        _sprite = GameCore.LazySpriteGenerate(tex);
        _image.sprite = _sprite;

        _image.material = _material;
    }

    public Vector2 TooltipOffset()
    {
        return _tooltip_offset;
    }

    public void SetTooltipOffset(Vector2 offset)
    {
        _tooltip_offset = offset;
    }

    public void set_position(Vector2 position)
    {
        _activity_object.transform.position = new Vector3(position.x, position.y, 0);
    }

    public void attach_to_canvas(Canvas canvas)
    {
        _canvas = canvas;
        _activity_object.transform.SetParent(canvas.transform, false);
    }

    public void UpdateCooldownPercent()
    {
        //Debug.Log("Activity.UpdateCooldownPercent: " + _action_back.GetFillPercent());
        _image.material.SetFloat("discard_angle", _action_back.GetFillPercent());
    }

    public void hide()
    {
        _activity_object.SetActive(false);
    }

    public void show()
    {
        _activity_object.SetActive(true);
    }

    public void Click()
    {
        _action_back.OnIconClick();
    }

    // public bool Click(Vector2 position)
    // {
    // 	bool is_clicked = RectTransformUtility.RectangleContainsScreenPoint(
    // 		_image.rectTransform,
    // 		position
    // 	);

    // 	if (is_clicked)
    // 	{
    // 		Debug.Log("Activity.Click: clicked");
    // 		_action_back.OnIconClick();
    // 	}

    // 	return is_clicked;
    // }

    public string TooltipText()
    {
        return _action_back.TooltipText();
    }

    public Vector2 RightTopCorner()
    {
        var rect = _image.rectTransform.rect;
        var pos = _image.rectTransform.position;
        return new Vector2(pos.x + rect.width / 2, pos.y + rect.height / 2);
    }

    public KeyCode hotkey()
    {
        return _hotkey;
    }

    public bool IsMouseOverImage()
    {
        var width = Screen.width;
        var height = Screen.height;
        var h2 = new Vector2(width / 2, height / 2);

        var position = Input.mousePosition;
        var rectpos = _image.rectTransform.position;
        var rectscl = new Vector3(
            _image.rectTransform.rect.width,
            _image.rectTransform.rect.height,
            0
        );

        var rectmin = rectpos - rectscl / 2;
        var rectmax = rectpos + rectscl / 2;

        return position.x < rectmax.x
            && position.x > rectmin.x
            && position.y < rectmax.y
            && position.y > rectmin.y;
    }
}
