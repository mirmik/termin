using UnityEngine;
using UnityEngine.UI;

public class RotaryProgressBarView : MonoBehaviour
{
    public GameObject plane;
    Material material;
    public Texture2D image;

    void Awake()
    {
        material = new Material(MaterialKeeper.Instance.GetMaterial("RotaryProgressBarMaterial"));
        plane.GetComponent<Renderer>().material = material;

        // set texture to material
        material.SetTexture("_MainTex", image);
        material.SetFloat("_Progress", 0.0f);
    }

    public void Show()
    {
        if (!plane.activeSelf)
        {
            plane.SetActive(true);
            gameObject.SetActive(true);
        }
    }

    public void Hide()
    {
        if (plane.activeSelf)
        {
            plane.SetActive(false);
            gameObject.SetActive(false);
        }
    }

    public void SetProgressValue(float value)
    {
        material.SetTexture("_MainTex", image);
        material.SetFloat("_Progress", value);
    }
};
