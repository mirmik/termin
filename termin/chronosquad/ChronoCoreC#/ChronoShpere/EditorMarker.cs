using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class EditorMarker : MonoBehaviour
{
    public static EditorMarker Instance;
    GameObject markerObject;

    LineRenderer lineRenderer;

    void Awake()
    {
        Instance = this;

        lineRenderer = gameObject.AddComponent<LineRenderer>();
        lineRenderer.startWidth = 0.2f;
        lineRenderer.endWidth = 0.2f;
        lineRenderer.startColor = Color.red;
        lineRenderer.endColor = Color.red;

        var material = new Material(Shader.Find("Sprites/Default"));
        lineRenderer.material = material;
        material.color = Color.red;

        lineRenderer.enabled = false;
        //markerObject.SetActive(false);

        //transform.Find("Arrow").gameObject.SetActive(false);
    }

    void Start()
    {
        ChronosphereController.instance.EditorModeChanged += OnEditorModeChanged;
    }

    void OnEditorModeChanged(bool editorMode)
    {
        if (!editorMode)
        {
            SetMarkerObject(null);
            lineRenderer.enabled = false;
        }
    }

    void Update()
    {
        if (markerObject != null)
        {
            SetMarkerPosition2(markerObject.transform.position);
        }
    }

    public void SetMarkerObject(GameObject obj)
    {
        if (obj == null)
        {
            lineRenderer.positionCount = 0;
            return;
        }

        markerObject = obj;
        lineRenderer.enabled = true;
        var position = obj.transform.position;
        SetMarkerPosition2(position);
    }

    public void SetMarkerPosition2(Vector3 position)
    {
        lineRenderer.positionCount = 2;
        lineRenderer.SetPosition(0, position + new Vector3(0, 0, 0));
        lineRenderer.SetPosition(1, position + new Vector3(0, 2.0f, 0));
    }

    public GameObject GetMarkedObject()
    {
        return markerObject;
    }
}
