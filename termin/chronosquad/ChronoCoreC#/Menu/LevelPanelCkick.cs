using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.EventSystems;

public class LevelPanelClick : MonoBehaviour, IPointerClickHandler
{
    LevelElement element;

    // Start is called before the first frame update
    void Start() { }

    // Update is called once per frame
    void Update() { }

    public void SetLevelElement(LevelElement element)
    {
        this.element = element;
    }

    // on mouse click
    public void OnPointerClick(PointerEventData eventData)
    {
        element.OnPointerClick();
    }
}
