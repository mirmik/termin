using UnityEngine;

public class BindUiToWorldPosition : MonoBehaviour
{
    public Transform Target;
    TMPro.TextMeshProUGUI text;
    RectTransform rect;

    // Start is called once before the first execution of Update after the MonoBehaviour is created
    void Awake()
    {
        text = Target.GetComponent<TMPro.TextMeshProUGUI>();
        rect = Target.GetComponent<RectTransform>();
    }

    Vector2 PositionOnScreen(Vector3 position)
    {
        var screenpos = Camera.main.WorldToScreenPoint(position);
        return new Vector2(screenpos.x, screenpos.y);
    }

    void SetTextPosition(Vector2 screenpos)
    {
        //rect.anchoredPosition = screenpos;
        rect.transform.position = screenpos;
    }

    public void SetText(string str)
    {
        text.text = str;
    }

    // Update is called once per frame
    void Update()
    {
        var screenpos = PositionOnScreen(transform.position);
        SetTextPosition(screenpos);
        //transform.position = screenpos;

        // var time = Time.time;
        // SetText(time.ToString());
    }
}
