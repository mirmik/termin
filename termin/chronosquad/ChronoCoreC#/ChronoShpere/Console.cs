#if UNITY_64|| UNITY_EDITOR

using UnityEngine;

public static class Console
{
    public static void WriteLine(string str)
    {
        Debug.Log(str);
    }
}

#endif
