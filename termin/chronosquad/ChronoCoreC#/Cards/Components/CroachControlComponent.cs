using System.Collections.Generic;
using UnityEngine;

public class CroachControlComponent : ItemComponent
{
    public bool IsCroachControl;
    public bool IsCroach;
    public bool IsBraced;

    public CroachControlComponent(ObjectOfTimeline owner) : base(owner) { }

    public override ItemComponent Copy(ObjectOfTimeline owner)
    {
        var c = new CroachControlComponent(owner);
        c.IsCroach = IsCroach;
        c.IsCroachControl = IsCroachControl;
        c.IsBraced = IsBraced;
        return c;
    }

    public virtual Dictionary<string, object> ToTrent()
    {
        Dictionary<string, object> dict = new Dictionary<string, object>();
        dict["is_croach_control"] = IsCroachControl;
        dict["is_croach"] = IsCroach;
        dict["is_braced"] = IsBraced;
        return dict;
    }

    public virtual void FromTrent(Dictionary<string, object> dict)
    {
        IsCroach = (bool)dict["is_croach"];
        IsCroachControl = (bool)dict["is_croach_control"];
        IsBraced = (bool)dict["is_braced"];
    }
}
