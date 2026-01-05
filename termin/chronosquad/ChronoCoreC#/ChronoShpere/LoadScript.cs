using System.Collections;
using System.Collections.Generic;

#if UNITY_64|| UNITY_EDITOR
using UnityEngine;
using UnityEngine.UI;
using UnityEngine.SceneManagement;
#endif

public class LoadScript : MonoBehaviour
{
    GameObject LoadScreen;
    Slider LoadBar;

    MyList<GameObject> objs = new MyList<GameObject>();

    void Start()
    {
        LoadScreen = gameObject;
        LoadBar = LoadScreen.transform.Find("Slider").GetComponent<Slider>();

        objs.Add(LoadScreen.transform.Find("Slider").gameObject);
        objs.Add(LoadScreen.transform.Find("Text").gameObject);
        objs.Add(LoadScreen.transform.Find("Background").gameObject);
        objs.Add(LoadScreen.transform.Find("TextLoading").gameObject);
        Deactivate();
    }

    public void Deactivate()
    {
        foreach (GameObject obj in objs)
        {
            obj.SetActive(false);
        }
    }

    public void Show()
    {
        foreach (GameObject obj in objs)
        {
            obj.SetActive(true);
        }
    }

    public void SetProgress(float progress)
    {
        LoadBar.value = progress;
    }
}
