using System.Collections;
using System.Collections.Generic;
using UnityEngine;

#if UNITY_64
using UnityEngine.UI;
#endif

public class BookPrefab : MonoBehaviour
{
    Canvas canvas;
    TMPro.TextMeshProUGUI textMesh;

    // button
    Button button;

    // image
    Image image;

    // Start is called before the first frame update
    void Start()
    {
        canvas = GetComponentInChildren<Canvas>();
        textMesh = GetComponentInChildren<TMPro.TextMeshProUGUI>();
        image = GetComponentInChildren<Image>();
        button = GetComponentInChildren<Button>();

        // set text color
        textMesh.color = new Color(0, 1, 0, 1);

        canvas.enabled = false;
        button.enabled = false;
    }

    public void Activate(bool en)
    {
        canvas.enabled = en;
        button.enabled = en;
    }

    // on click event
    public void OnClick()
    {
        Debug.Log("OnClick");
        GameCore.RestoreAfterBookReading();
    }

    public void SetText(string text)
    {
        textMesh.text = text;
    }

    public void SetImage(Sprite sprite)
    {
        image.sprite = sprite;
    }

    public float GetTextWidth()
    {
        return textMesh.preferredWidth;
    }

    public float GetTextHeight()
    {
        return textMesh.preferredHeight;
    }

    public void SetAnchor(Vector2 anchor)
    {
        RectTransform rt = GetComponent<RectTransform>();
        rt.anchorMin = anchor;
        rt.anchorMax = anchor;
        rt.pivot = anchor;

        rt.anchoredPosition = new Vector2(0, 0);
    }

    // set position of text and image
    public void SetPositionFromBottom(int pixels)
    {
        Debug.Log("SetPositionFromBottom " + pixels);
        int ScreenHeightD2 = Screen.height / 2;

        // set position of text
        var rt = textMesh.GetComponent<RectTransform>();
        rt.anchoredPosition = new Vector2(0, -ScreenHeightD2 + pixels);

        // set position of image
        rt = image.GetComponent<RectTransform>();
        rt.anchoredPosition = new Vector2(-500, -ScreenHeightD2 + pixels);
    }

    // Update is called once per frame
    void Update() { }
}
