using System.Collections;
using System.Collections.Generic;

#if UNITY_64
using UnityEngine;
using UnityEngine.AI;
using Unity.AI.Navigation;
#endif

public class LinkInGameHighlighter : MonoBehaviour
{
    LineRenderer _line_renderer;

    bool ENABLE_HIGHLIGHTER = false;

    void Awake()
    {
        _line_renderer = this.gameObject.GetOrAddComponent<LineRenderer>();
        _line_renderer.material = new Material(Shader.Find("Sprites/Default"));
        _line_renderer.startColor = Color.red;
        _line_renderer.endColor = Color.red;
        _line_renderer.startWidth = 0.1f;
        _line_renderer.endWidth = 0.1f;
        _line_renderer.positionCount = 2;
        _line_renderer.useWorldSpace = false;
        _line_renderer.enabled = true;

        //_navmesh_link = this.gameObject.GetComponent<NavMeshLink>();
    }

    public void UpdateFromLinkData(LinkData link_data, Color color)
    {
        _line_renderer.enabled = ENABLE_HIGHLIGHTER;
        _line_renderer.startColor = color;
        _line_renderer.endColor = color;
        _line_renderer.SetPosition(
            0,
            transform.InverseTransformPoint(link_data.link.startPosition)
        );
        _line_renderer.SetPosition(1, transform.InverseTransformPoint(link_data.link.endPosition));
    }

    public void Disable(Vector3 position, Vector3 direction)
    {
        _line_renderer.enabled = ENABLE_HIGHLIGHTER;
        _line_renderer.startColor = Color.black;
        _line_renderer.endColor = Color.black;
        _line_renderer.SetPosition(0, transform.InverseTransformPoint(position));
        _line_renderer.SetPosition(
            1,
            transform.InverseTransformPoint(position + direction * 100.0f)
        );
    }

    public void Enable(bool en)
    {
        ENABLE_HIGHLIGHTER = en;
        _line_renderer.enabled = en;
    }

    // void Update()
    // {
    // 	if (_navmesh_link == null)
    // 	{
    // 		return;
    // 	}

    // 	//var start = _navmesh_link.transform.TransformPoint(_navmesh_link.startPoint);
    // 	//var end = _navmesh_link.transform.TransformPoint(_navmesh_link.endPoint);
    // 	var start = _navmesh_link.startPoint;
    // 	var end = _navmesh_link.endPoint;

    // 	_line_renderer.SetPosition(0, start);
    // 	_line_renderer.SetPosition(1, end);
    // }
}
