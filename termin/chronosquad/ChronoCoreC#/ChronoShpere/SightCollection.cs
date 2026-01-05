using System.Collections;
using System.Collections.Generic;
using UnityEngine;

struct SightData
{
    public Camera camera;
    public RenderTexture texture;
    public HeroCameraRegistrator registrator;

    public Matrix4x4 GetViewMatrix()
    {
        return camera.worldToCameraMatrix;
    }

    public Matrix4x4 GetProjMatrix()
    {
        return camera.projectionMatrix;
    }

    public Vector3 GetPosition()
    {
        return camera.transform.position;
    }

    public SightData(Camera camera, RenderTexture texture, HeroCameraRegistrator registrator)
    {
        this.camera = camera;
        this.texture = texture;
        this.registrator = registrator;
    }
}

public class SightCollection : MonoBehaviour
{
    static public SightCollection Instance = null;

    void Awake()
    {
        Instance = this;
    }

    Dictionary<GameObject, SightData> sight_textures = new Dictionary<GameObject, SightData>();

    List<SightData> sight_textures_list = new List<SightData>();

    public void RegisterHeroTexture(
        GameObject go,
        Camera camera,
        RenderTexture rt,
        HeroCameraRegistrator registrator
    )
    {
        var sight_data = new SightData(camera, rt, registrator);
        sight_textures.Add(go, sight_data);
        MakeList();
    }

    public void MakeList()
    {
        sight_textures_list.Clear();
        foreach (var sight_data in sight_textures.Values)
        {
            sight_textures_list.Add(sight_data);
        }
    }

    public void UnregisterHeroTexture(GameObject go)
    {
        sight_textures.Remove(go);
        MakeList();
    }

    public int Count()
    {
        return sight_textures.Count;
    }

    public RenderTexture GetTexture(int i)
    {
        return sight_textures_list[i].texture;
    }

    public Matrix4x4 GetViewMatrix(int i)
    {
        return sight_textures_list[i].GetViewMatrix();
    }

    public float GetDistance(int i)
    {
        return sight_textures_list[i].registrator.GetDistance();
    }

    public Matrix4x4 GetProjMatrix(int i)
    {
        return sight_textures_list[i].GetProjMatrix();
    }

    public Vector3 GetPosition(int i)
    {
        return sight_textures_list[i].GetPosition();
    }
}
