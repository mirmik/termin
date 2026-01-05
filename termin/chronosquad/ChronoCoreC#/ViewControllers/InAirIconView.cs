using UnityEngine;
using UnityEngine.UI;

public class InAirIconView : MonoBehaviour
{
    public GameObject plane;
    Material material;
    Image image;

    void Awake()
    {
        material = new Material(MaterialKeeper.Instance.GetMaterial("RotaryProgressBarMaterial"));
        plane.GetComponent<Renderer>().material = material;

        // set texture to material
        //	material.SetTexture("_MainTex", image);
        material.SetFloat("_Progress", 0.0f);
    }

    public void SetImage(Image img)
    {
        image = img;

        // set texture to material
        material.SetTexture("_MainTex", image.mainTexture);
    }

    public void Show()
    {
        plane.SetActive(true);
    }

    public void Hide()
    {
        plane.SetActive(false);
    }

    public void SetProgressValue(float value)
    {
        material.SetFloat("_Progress", value);
    }
};
