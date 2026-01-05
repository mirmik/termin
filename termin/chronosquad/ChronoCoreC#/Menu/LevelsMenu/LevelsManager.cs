using System.Collections;
using System.Collections.Generic;
using System.IO;
using TMPro;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.UI;

public class LevelsManager : MonoBehaviour
{
    string levelsDirectory = GameCore.DialoguePathBase() + "Levels/";
    MyList<ScrTree> levels = new MyList<ScrTree>();
    MyList<LevelElement> levelElements = new MyList<LevelElement>();

    //LevelPanel levelPanel;
    GameObject levelElementPrefab;

    GridLayoutGroup levelsGrid;

    TextMeshProUGUI panelText;
    Canvas canvas;

    LevelElement chosen_level;
    LoadScript _load_script;
    AudioSource _audio_source;

    //button
    public void OnLevelElementClick(LevelElement levelElement)
    {
        chosen_level?.MarkAsUnselected();
        panelText.text = levelElement.levelRecord.free_text;
        chosen_level = levelElement;
        levelElement.MarkAsSelected();
    }

    void Start()
    {
        CreateAudioSourceIfNeed();
        levelElementPrefab = MaterialKeeper.Instance.GetPrefab("LevelElementPrefab");
        canvas = GameObject.Find("BackgroundCanvas").GetComponent<Canvas>();
        panelText = GameObject.Find("PanelText").GetComponent<TextMeshProUGUI>();
        _load_script = GameObject.Find("LoadScreen").GetComponent<LoadScript>();
        levelsGrid = GameObject.Find("LevelsGrid").GetComponent<GridLayoutGroup>();
        LoadLevels();
    }

    void CreateAudioSourceIfNeed()
    {
        // find objects with name "MenuAudioSource". not a tag
        GameObject[] objs = GameObject.FindObjectsByType<GameObject>(FindObjectsSortMode.None);
        foreach (GameObject go in objs)
        {
            if (go.name.StartsWith("MenuAudioSource"))
            {
                _audio_source = go.GetComponent<AudioSource>();
                break;
            }
        }

        if (_audio_source == null)
        {
            GameObject go = GameObject.Instantiate(
                MaterialKeeper.Instance.GetPrefab("MenuAudioSource")
            );
            _audio_source = go.GetComponent<AudioSource>();
            _audio_source.volume = PlayerPrefs.GetFloat("MusicVolume", 1.0f);
            DontDestroyOnLoad(go);
        }
    }

    void LoadLevels()
    {
        MyList<ScrTree> levels = new MyList<ScrTree>();
        string[] files = Directory.GetFiles(levelsDirectory, "*.scr");
        int index = 0;
        foreach (string file in files)
        {
            ScrParser parser = new ScrParser();
            var text = File.ReadAllText(file);
            var scrtree = parser.Parse(text);
            levels.Add(scrtree);
            AddLevelElement(scrtree, index);
            index++;
        }
        this.levels = levels;
    }

    void SetPositionInCell(int row, int col, LevelElement el)
    {
        //setup anchor 0-0.33-0.66-1

        //var rectTrans = el.rectTransform;
        //rectTrans.anchorMin = new Vector2(
        //	0.33f * (col-1),
        //	0.33f * (row - 1));
        //      rectTrans.anchorMax = new Vector2(
        //	0.33f * col, 0.33f * row);
        //      rectTrans.pivot = new Vector2(0.5f, 0.5f);
        //      rectTrans.sizeDelta = new Vector2(0, 0);
        //      rectTrans.anchoredPosition = new Vector2(0, 0);
        //      rectTrans.localScale = new Vector3(1, 1, 1);
        //      rectTrans.localRotation = Quaternion.Euler(0, 0, 0);
        //      rectTrans.localPosition = new Vector3(0, 0, 0);

        //var xcellSize = 350;
        //var ycellSize = 330;
        //var cellPadding = 10;
        //var x = col * (xcellSize + cellPadding) + 200;
        //var y = row * -(ycellSize + cellPadding) + 800;
        //el.SetPosition(new Vector3(x, y, 0));
    }

    public void SetPositionByIndex(LevelElement levelElement, int index)
    {
        levelElement.transform.SetParent(levelsGrid.transform, worldPositionStays: false);
        SetPositionInCell(index / 3, index % 3, levelElement);
    }

    void AddLevelElement(ScrTree levelRecord, int index)
    {
        var levelElement_go = Instantiate(levelElementPrefab);
        var levelElement = levelElement_go.GetComponent<LevelElement>();
        levelElement.SetLevelsManager(this);
        levelElement.SetText(levelRecord.scene_username);
        levelElement.levelRecord = levelRecord;
        levelElements.Add(levelElement);
        levelElement.MarkAsUnselected();

        if (levelRecord.scene_image != "" && levelRecord.scene_image != null)
        {
            Texture texture = MaterialKeeper.Instance.GetTexture(levelRecord.scene_image);
            levelElement.SetImage(texture);
            //Debug.Log("Set image: " + levelRecord.scene_image);
        }

        levelElement.SetIndex(index);
        //SetPositionInCell(index/3, index%3, levelElement);
    }

    public void SetText(string text)
    {
        panelText.text = text;
    }

    public void OnLoadButton()
    {
        if (chosen_level == null)
        {
            Debug.Log("No level chosen");
            return;
        }

        foreach (var level in levelElements)
        {
            level.gameObject.SetActive(false);
        }

        LoadScene(chosen_level.levelRecord.scene_machname);
    }

    void LoadScene(string scene_name)
    {
        DestroyAllAudioSources();
        _load_script.Show();
        StartCoroutine(LoadSceneAsync(scene_name));
    }

    void DestroyAllAudioSources()
    {
        foreach (var audio in GameObject.FindObjectsByType<AudioSource>(FindObjectsSortMode.None))
        {
            Destroy(audio.gameObject);
        }
    }

    IEnumerator LoadSceneAsync(string scene_name)
    {
        AsyncOperation operation = SceneManager.LoadSceneAsync(scene_name);

        while (!operation.isDone)
        {
            _load_script.SetProgress(operation.progress);
            yield return null;
        }
    }

    public void ToMainMenu()
    {
        SceneManager.LoadScene("Menu");
    }
}
