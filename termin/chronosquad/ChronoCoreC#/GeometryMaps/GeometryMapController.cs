using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;

public class GeometryMapController : MonoBehaviour
{
    //Material material;
    Texture2D texture;
    RenderTargetIdentifier memory_rtid;

    //RenderTexture memory_rt;
    RenderTargetIdentifier current_sight_rtid;

    //RenderTexture current_sight_rt;

    Material geometry_map_material;

    Material latency_blitter_material;

    void Awake()
    {
        return;

        // material = new Material(GetComponent<Renderer>().material);
        // GetComponent<Renderer>().material = material;
        // var s = transform.localScale;

        // memory_rt = new RenderTexture(1024, 1024, 0, RenderTextureFormat.ARGBFloat);
        // memory_rtid = new RenderTargetIdentifier(memory_rt);
        // memory_rt.filterMode = FilterMode.Bilinear;

        // current_sight_rt = new RenderTexture(1024, 1024, 16);
        // current_sight_rtid = new RenderTargetIdentifier(current_sight_rt);
        // current_sight_rt.filterMode = FilterMode.Bilinear;

        // material.SetTexture("MemoryMap", memory_rt);
    }

    public RenderTargetIdentifier MemoryRTID()
    {
        return memory_rtid;
    }

    public RenderTargetIdentifier CurrentSightRTID()
    {
        return current_sight_rtid;
    }

    void Start()
    {
        return;

        // texture = LoadTexture();

        // geometry_map_material = new Material(
        //     MaterialKeeper.Instance.GetMaterial("GeometryMapsMaterial")
        // );
        // latency_blitter_material = new Material(
        //     MaterialKeeper.Instance.GetMaterial("LattencyBlitterMaterial")
        // );
        // latency_blitter_material.SetTexture("CurrentSight", current_sight_rt);
    }

    public Material GeometryMapMaterial()
    {
        return geometry_map_material;
    }

    public Material LattencyBlitterMaterial()
    {
        return latency_blitter_material;
    }

    Texture2D LoadTexture()
    {
        var tex = new Texture2D(1024, 1024);
        var bytes = System.IO.File.ReadAllBytes(GeometryMapPath());
        tex.LoadImage(bytes);
        return tex;
    }

    // Update is called once per frame
    void Update()
    {
        return;

        // var m = transform.localToWorldMatrix;
        // var s = transform.localScale;
        // geometry_map_material.SetMatrix("ModelMatrix", m);
        // geometry_map_material.SetVector("ModelScale", s);
    }

    public string IerarchyPath()
    {
        return GeometryMapBuilder.IerarchyPath(gameObject);
    }

    public string GeometryMapPath()
    {
        var scene_name = SceneManager.GetActiveScene().name;
        var ierarchy_path = IerarchyPath();
        return "Assets/StreamingAssets/GeometryMaps/" + scene_name + "/" + ierarchy_path + ".png";
    }

    public string GeometryMapPathScale()
    {
        var scene_name = SceneManager.GetActiveScene().name;
        var ierarchy_path = IerarchyPath();
        return "Assets/StreamingAssets/GeometryMaps/" + scene_name + "/" + ierarchy_path + ".scl";
    }

    public ScaleStruct GetScale()
    {
        return new ScaleStruct(Vector3.one, Vector3.one);

        // var scl_path = GeometryMapPathScale();
        // var scale = System.IO.File.ReadAllText(scl_path);
        // var parts = scale.Split('\n');
        // var minval = parts[0].Split(',');
        // var maxval = parts[1].Split(',');
        // var g = System.Globalization.CultureInfo.InvariantCulture;
        // var min = new Vector3(
        //     float.Parse(minval[0], g),
        //     float.Parse(minval[1], g),
        //     float.Parse(minval[2], g)
        // );
        // var max = new Vector3(
        //     float.Parse(maxval[0], g),
        //     float.Parse(maxval[1], g),
        //     float.Parse(maxval[2], g)
        // );

        //geometry_map_material.SetVector("MinScale", min);
        //geometry_map_material.SetVector("MaxScale", max);

        //return new ScaleStruct(min, max);
    }

    public Texture2D GetTexture()
    {
        return texture;
    }
}

public struct ScaleStruct
{
    public Vector3 min;
    public Vector3 max;

    public ScaleStruct(Vector3 min, Vector3 max)
    {
        this.min = min;
        this.max = max;
    }
}
