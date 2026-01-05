using System.Collections.Generic;
using System.IO;
using UnityEngine;
#if UNITY_EDITOR
using UnityEditor;
#endif

public class InternalEditor : MonoBehaviour
{
#if UNITY_EDITOR
    MyList<Activity> activity_list;
    UserInterfaceCanvas userInterfaceCanvas;

    public CreateGuardAction CreateGuard
    {
        get => GetComponent<CreateGuardAction>();
    }

    public MoveEditorAction MoveEditor
    {
        get => GetComponent<MoveEditorAction>();
    }

    public RemoveEditorAction RemoveEditor
    {
        get => GetComponent<RemoveEditorAction>();
    }

    public CreateYetOnePointAction CreateYetOnePoint
    {
        get => GetComponent<CreateYetOnePointAction>();
    }

    // public MyList<GameAction> GetAllGameActions()
    // {
    // 	var array = GetComponents<GameAction>();
    // 	var list = new List<GameAction>(array);
    // 	foreach (var action in list)
    // 	{
    // 		list.Add(action);
    // 	}
    // 	return list;
    // }

    void Start()
    {
        ChronosphereController.instance.EditorModeChanged += OnEditorModeChanged;
        userInterfaceCanvas = UserInterfaceCanvas.Instance;
    }

    void OnEditorModeChanged(bool mode)
    {
        if (mode)
        {
            activity_list = new MyList<Activity>();
            activity_list.Add(CreateGuard._activity);
            activity_list.Add(MoveEditor._activity);
            activity_list.Add(RemoveEditor._activity);
            activity_list.Add(CreateYetOnePoint._activity);

            foreach (var activity in activity_list)
            {
                activity.SetTooltipOffset(new Vector2(-180, 0));
            }
        }
        else
        {
            activity_list = null;
        }
        userInterfaceCanvas.SetVerticalActivities(activity_list);
    }

    [MenuItem("Tools/Editor/Apply editor changes")]
    public static void ApplyEditorChanges()
    {
        ObjectController.FindPrefabsForTemporarlyObjects();
        PatrolPointCollection.RestoreAllPatrolPointsFromTemporaryStore();
        PatrolPointCollection.InitOrRestoreFirstPointGlobal();
    }

    [MenuItem("Tools/Editor/Clean temporary objects")]
    public static void CleanTemporaryObjects()
    {
        var ObjectTMPDirectory = GameCore.ObjectTMPDirectory();
        var PatrolPointsTMPDirectory = GameCore.PatrolPointsTMPDirectory();

        Debug.Log("ObjectTMPDirectory: " + ObjectTMPDirectory);
        Debug.Log("PatrolPointsTMPDirectory: " + PatrolPointsTMPDirectory);

        if (Directory.Exists(ObjectTMPDirectory))
        {
            Directory.Delete(ObjectTMPDirectory, true);
        }

        if (Directory.Exists(PatrolPointsTMPDirectory))
        {
            Directory.Delete(PatrolPointsTMPDirectory, true);
        }
    }

#endif
}
