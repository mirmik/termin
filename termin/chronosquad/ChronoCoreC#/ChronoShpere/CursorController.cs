using System.Collections;
using System.Collections.Generic;
using System;

#if UNITY_64|| UNITY_EDITOR

using UnityEngine;
#endif

public enum CursorType
{
    Default,
    SwapHost,
    Hack
}

public class CursorController : MonoBehaviour
{
    static CursorController _instance;

    public static CursorController Instance
    {
        get
        {
            if (_instance == null)
            {
                _instance = GameObject.FindFirstObjectByType<CursorController>();
            }
            return _instance;
        }
    }

    public Texture2D cursorTexture;

    public Texture2D cursorTexture_Hack;
    public Texture2D cursorTexture_SwapHost;

    void Awake()
    {
        _instance = this;
    }

    // Start is called before the first frame update
    void Start()
    {
        //set cursor image
        Cursor.SetCursor(cursorTexture, Vector2.zero, CursorMode.Auto);
    }

    public void SetCursor(CursorType cursorType)
    {
        switch (cursorType)
        {
            case CursorType.Default:
                Cursor.SetCursor(cursorTexture, Vector2.zero, CursorMode.Auto);
                break;
            case CursorType.SwapHost:
                Cursor.SetCursor(cursorTexture_SwapHost, new Vector2(256, 256), CursorMode.Auto);
                break;
            case CursorType.Hack:
                Cursor.SetCursor(cursorTexture_Hack, new Vector2(256, 256), CursorMode.Auto);
                break;
        }
    }
}
