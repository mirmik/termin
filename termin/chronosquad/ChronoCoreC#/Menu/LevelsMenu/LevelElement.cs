using TMPro;
using UnityEngine;
using UnityEngine.UI;

public class LevelElement : MonoBehaviour
{
    string str;
    Vector3 pos;

    TextMeshProUGUI text_ui;

    // image
    Image panel_ui;
    public RectTransform rectTransform;

    Image image_ui;

    public ScrTree levelRecord;

    LevelsManager levelsManager;

    Sprite sprite;

    Canvas canvas;

    Color panel_color;
    int index;

    void Start()
    {
        text_ui = transform.Find("Text").GetComponent<TextMeshProUGUI>();
        panel_ui = this.GetComponent<Image>();
        image_ui = transform.Find("Image").GetComponent<Image>();
        rectTransform = GetComponent<RectTransform>();

        if (str != null)
        {
            text_ui.text = str;
        }

        //if (pos != null)
        //{
        //	text_ui.transform.position = pos;
        //	panel_ui.transform.position = pos + new Vector3(0, 110, 0);
        //	image_ui.transform.position = pos + new Vector3(0, 150, 0);
        //}

        text_ui.GetComponent<LevelPanelClick>().SetLevelElement(this);
        panel_ui.GetComponent<LevelPanelClick>().SetLevelElement(this);
        image_ui.GetComponent<LevelPanelClick>().SetLevelElement(this);

        if (sprite != null)
        {
            image_ui.sprite = sprite;
            //Debug.Log("Set sprite: " + sprite);
        }

        if (panel_color != null)
        {
            panel_ui.color = panel_color;
        }

        if (levelsManager != null)
        {
            levelsManager.SetPositionByIndex(this, index);
        }
    }

    public void SetLevelsManager(LevelsManager levelsManager)
    {
        this.levelsManager = levelsManager;
    }

    public void SetIndex(int i)
    {
        this.index = i;
    }

    public void SetPosition(Vector3 position)
    {
        pos = position;
        //transform.position = position;
    }

    public void SetImage(Texture texture)
    {
        sprite = Sprite.Create(
            (Texture2D)texture,
            new Rect(0, 0, texture.width, texture.height),
            new Vector2(0.5f, 0.5f)
        );
    }

    public void SetText(string text)
    {
        if (text_ui == null)
        {
            str = text;
        }
        else
            text_ui.text = text;
    }

    // on click
    public void OnPointerClick()
    {
        levelsManager.OnLevelElementClick(this);
    }

    public void MarkAsSelected()
    {
        panel_ui.color = new Color(0.0f, 0.6f, 0.3f, 0.7f);
    }

    public void MarkAsUnselected()
    {
        Color color = new Color(0, 0, 0, 0.7f);
        if (panel_ui != null)
            panel_ui.color = color;
        else
            panel_color = color;
    }
}
