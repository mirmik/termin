#if UNITY_64
using UnityEngine;
#endif

using System;
using System.Collections.Generic;

public class ObjectProxy
{
    ITimeline _tl = null;
    string _name = null;

    ObjectOfTimeline cached_object = null;

    public ObjectProxy(string name, ITimeline tl)
    {
        _tl = tl;
        _name = name;
    }

    public ObjectOfTimeline Object()
    {
        if (cached_object == null)
            cached_object = _tl.GetObject(_name);
        return cached_object;
    }

    public void AttachTo(string name, ITimeline timeline)
    {
        _tl = timeline;
        _name = name;
        cached_object = null;
    }

    public bool HasObject()
    {
        return _tl.TryGetObject(_name) != null;
    }

    public ObjectOfTimeline TryGetObject()
    {
        return _tl.TryGetObject(_name);
    }

    public T CreateObject<T>(string name, ITimeline tl) where T : ObjectOfTimeline, new()
    {
        this._name = name;
        this._tl = tl;

        var _object = new T();
        _object.SetName(name);
        _object.SetProtoId(name);
        (tl as Timeline).AddObject(_object);
        return _object;
    }
}
