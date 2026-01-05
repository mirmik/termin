using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class TrapAction : MonoBehaviour
{
    ObjectController _controller;

    void Start()
    {
        _controller = this.GetComponent<ObjectController>();

        var obj = _controller.GetObject();
        TrapComponent trap = new TrapComponent(obj);

        _controller.GetObject().AddComponent(trap);
    }
}
