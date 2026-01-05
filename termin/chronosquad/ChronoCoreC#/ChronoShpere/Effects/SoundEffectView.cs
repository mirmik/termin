using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class SoundEffectView : MonoBehaviour
{
    bool _is_active = false;
    GameObject _model1;
    GameObject _model2;

    // Start is called before the first frame update
    void Awake()
    {
        _model1 = transform.Find("Sphere1").gameObject;
        _model2 = transform.Find("Sphere2").gameObject;

        _model1.SetActive(false);
        _model2.SetActive(false);
        _is_active = false;

        gameObject.SetActive(false);
    }

    public void Show()
    {
        if (_is_active)
            return;

        gameObject.SetActive(true);
        _is_active = true;
        _model1.SetActive(true);
        _model2.SetActive(true);
    }

    public void Hide()
    {
        if (!_is_active)
            return;

        gameObject.SetActive(false);
        _is_active = false;
        _model1.SetActive(false);
        _model2.SetActive(false);
    }

    public void SetRadius(float volume, float diff)
    {
        float r1 = volume + diff;
        float r2 = volume;
        _model1.transform.localScale = new Vector3(r1, r1, r1);
        _model2.transform.localScale = new Vector3(r2, r2, r2);
    }

    void Update()
    {
        if (!_is_active)
            return;

        float period = 0.8f;
        float time = Time.time / period;
        time -= Mathf.Floor(time);
        var scale = time * 1.5f;
        SetRadius(scale, 0.5f);
    }
}
