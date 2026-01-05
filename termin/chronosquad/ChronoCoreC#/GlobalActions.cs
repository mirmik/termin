using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class GlobalActions : MonoBehaviour
{
    public static GlobalActions Instance;

    // Start is called before the first frame update
    void Awake()
    {
        Instance = this;
    }

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

    // Update is called once per frame
    void Update() { }
}
