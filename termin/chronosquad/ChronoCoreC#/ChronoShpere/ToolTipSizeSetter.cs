using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

public class ToolTipSizeSetter : MonoBehaviour
{
    Image image;

    void Start()
    {
        image = GetComponent<Image>();

        var material = image.material;
        material.SetFloat("Transparency", 0.5f);
        material.SetFloat("Width", image.rectTransform.rect.width);
        material.SetFloat("Height", image.rectTransform.rect.height);
    }
}
