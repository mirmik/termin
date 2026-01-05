using System.Collections;
using System.Collections.Generic;

#if UNITY_64
using UnityEngine;
#endif

struct LinkPair
{
    public ObjectId _a;
    public ObjectId _b;
    public bool admin_flag;
}

public class NetworkView : MonoBehaviour
{
    //const int count_of_points = 48;
    const int count_of_points = 2;
    MyList<NetPointView> _net_points = new MyList<NetPointView>();
    TimelineController _timeline_controller;

    Dictionary<LinkPair, GameObject> _visual_links = new Dictionary<LinkPair, GameObject>();

    GameObject _network_links;

    void Awake()
    {
        _timeline_controller = GetComponent<TimelineController>();
    }

    LinkPair MakeLinkPair(ObjectId a, ObjectId b, bool admin_flag)
    {
        if (a.hash.CompareTo(b.hash) < 0)
        {
            return new LinkPair
            {
                _a = a,
                _b = b,
                admin_flag = admin_flag
            };
        }
        else
        {
            return new LinkPair
            {
                _a = b,
                _b = a,
                admin_flag = admin_flag
            };
        }
    }

    public void StartNetwork()
    {
        var objects = _timeline_controller.GetObjects();
        foreach (var obj in objects)
        {
            var net_point_view = obj.GetComponent<NetPointView>();
            if (net_point_view != null)
            {
                _net_points.Add(net_point_view);
                net_point_view.StartNetwork();
            }
        }

        _network_links = new GameObject("NetworkLinks");
        _network_links.transform.parent = transform;

        CreateVisualLinks();
    }

    void CreateVisualLinks()
    {
        foreach (var net_point_view in _net_points)
        {
            foreach (var link in net_point_view.GetLinks())
            {
                var link_pair = MakeLinkPair(
                    new ObjectId(net_point_view.name),
                    link.name,
                    link.admin_flag
                );
                if (!_visual_links.ContainsKey(link_pair))
                {
                    var link_obj = new GameObject("Link");
                    link_obj.transform.parent = _network_links.transform;
                    var line_renderer = link_obj.AddComponent<LineRenderer>();
                    line_renderer.material = new Material(
                        MaterialKeeper.Instance.GetMaterial("NetworkLineMaterial")
                    );
                    line_renderer.positionCount = count_of_points;
                    float width = 0.015f;
                    line_renderer.startWidth = width;
                    line_renderer.endWidth = width;
                    _visual_links.Add(link_pair, link_obj);
                }
            }
        }

        UpdateVisualLinksPosition();
    }

    void UpdateVisualLinksPosition()
    {
        foreach (var pair in _visual_links)
        {
            var link_obj = pair.Value;
            var line_renderer = link_obj.GetComponent<LineRenderer>();
            var link_pair = pair.Key;

            var a_obj = _timeline_controller.GetObject(link_pair._a);
            var b_obj = _timeline_controller.GetObject(link_pair._b);

            if (a_obj != null && b_obj != null)
            {
                int ahash = link_pair._a.GetHashCode();
                int bhash = link_pair._b.GetHashCode();
                int seed = (ahash ^ bhash) % 1000;
                var a_pos = a_obj.transform.position + new Vector3(0, 2.5f, 0);
                var b_pos = b_obj.transform.position + new Vector3(0, 2.5f, 0);
                line_renderer.material.SetVector("_apos", a_pos);
                line_renderer.material.SetVector("_bpos", b_pos);
                line_renderer.material.SetFloat("_seed", seed);
                UpdateLineRenderer(line_renderer, a_pos, b_pos);
            }
        }
    }

    public void UpdateLineRenderer(LineRenderer line_renderer, Vector3 a_pos, Vector3 b_pos)
    {
        float step = 1.0f / (count_of_points - 1);
        Vector3 dir = b_pos - a_pos;
        Vector3 diff = dir * step;

        Vector3 a = a_pos;
        for (int i = 0; i < count_of_points; i++)
        {
            line_renderer.SetPosition(i, a);
            a = a + diff;
        }
    }

    void Update()
    {
        UpdateVisualLinksPosition();
    }
}
