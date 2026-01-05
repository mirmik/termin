using System;
using System.Collections.Generic;
using UnityEngine;

public class HelpBook : ObjectController
{
    bool _is_init = false;

    public string PathToScript;

    void Start()
    {
        var path_to_script = GameCore.DialoguePathBase() + PathToScript;
        var text = System.IO.File.ReadAllText(path_to_script);

        var obj = GetObject();
        BookComponent book = new BookComponent(GetObject(), text);
        obj.AddComponent(book);
    }

    public override void InitObjectController(ITimeline tl)
    {
        if (_is_init)
            return;
        CreateObject<PhysicalObject>();
        _is_init = true;
    }
}
