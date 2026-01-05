using UnityEngine;
using System.Collections.Generic;

public class BetweenScenesInformation
{
    public int finishedSceneIndex = 0;
}

public class BetweenScenesInformationAccessor : MonoBehaviour
{
    public static BetweenScenesInformation Instance { get; private set; }

    private void Awake()
    {
        if (Instance == null)
        {
            Instance = new BetweenScenesInformation();
        }
    }

    public int GetFinishedSceneIndex()
    {
        return Instance.finishedSceneIndex;
    }
}
