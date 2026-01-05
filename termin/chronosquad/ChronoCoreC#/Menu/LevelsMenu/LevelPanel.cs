using UnityEngine;
using TMPro;

public class LevelPanel : MonoBehaviour
{
    //TextMeshProUGUI text_ui;

    LevelsManager levelsManager;

    void Start()
    {
        //text_ui = GetComponentInChildren<TextMeshProUGUI>();
    }

    public void SetLevelsManager(LevelsManager levelsManager)
    {
        this.levelsManager = levelsManager;
    }

    public void SetText(string text)
    {
        //text_ui.text = text;
    }

    public void SetRecord(ScrTree record)
    {
        //text_ui.text = record.free_text;
    }

    // onclick
    public void OnPointerClick()
    {
        // Debug.Log("LevelPanel clicked");
        // //levelsManager.OnLevelPanelClick(this);
    }
}
