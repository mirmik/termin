using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class TechnicalAcumen : MonoBehaviour
{
    ObjectController objectController;

    // Start is called before the first frame update
    void Start()
    {
        objectController = GetComponent<ObjectController>();
        var obj = objectController.GetObject();
        TechnicalAcumenComponent technicalAcumenComponent = new TechnicalAcumenComponent(obj);
        obj.AddComponent(technicalAcumenComponent);
    }

    // Update is called once per frame
    void Update() { }
}
