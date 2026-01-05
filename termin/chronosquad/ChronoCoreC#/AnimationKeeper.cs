using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class AnimationKeeper : MonoBehaviour
{
    static AnimationKeeper _instance;

    public static AnimationKeeper Instance
    {
        get
        {
            if (_instance == null)
            {
                _instance = GameObject.FindFirstObjectByType<AnimationKeeper>();
            }
            return _instance;
        }
    }

    Dictionary<string, AnimationCurveManager> _managers =
        new Dictionary<string, AnimationCurveManager>();
    bool inited = false;

    void Init()
    {
        foreach (var child in GetComponentsInChildren<AnimationCurveManager>())
        {
            if (!_managers.ContainsKey(child.UnicalName))
                _managers.Add(child.UnicalName, child);
        }
        inited = true;
    }

    void Awake()
    {
        _instance = this;
        if (!inited)
            Init();
    }

    public AnimationCurveManager GetManager(string name)
    {
        if (!inited)
            Init();

        if (_managers.ContainsKey(name))
            return _managers[name];
        return null;
    }
}
