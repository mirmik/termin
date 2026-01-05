using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class MirrorMarker : MonoBehaviour
{
    TMPro.TextMeshProUGUI proto;
    TMPro.TextMeshProUGUI text_element;

    string last_text = "";

    public void SetPrototype(TMPro.TextMeshProUGUI telement)
    {
        proto = telement;
    }

    void Start()
    {
        text_element = GetComponent<TMPro.TextMeshProUGUI>();
    }

    // Update is called once per frame
    void Update()
    {
        if (last_text != proto.text)
        {
            text_element.text = "<mark=#00000077>" + proto.text + "</mark>";
            last_text = proto.text;
        }
    }
}
