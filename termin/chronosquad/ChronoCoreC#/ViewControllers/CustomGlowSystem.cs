using System.Collections;
using System.Collections.Generic;
#if UNITY_64
using UnityEngine;
using UnityEngine.Rendering;
#endif

public class CustomGlowSystem
{
    static CustomGlowSystem m_Instance; // singleton
    public static CustomGlowSystem instance
    {
        get
        {
            if (m_Instance == null)
                m_Instance = new CustomGlowSystem();
            return m_Instance;
        }
    }

    public Dictionary<TimelineController, MyList<GlowObj>> m_GlowObjs =
        new Dictionary<TimelineController, MyList<GlowObj>>();

    public void RegisterTimeline(TimelineController tl)
    {
        if (!m_GlowObjs.ContainsKey(tl))
        {
            m_GlowObjs[tl] = new MyList<GlowObj>();
        }
    }

    public void Add(
        TimelineController tl,
        ObjectController o,
        Material mat
    //, Material phantom_material
    )
    {
        var glow_obj = new GlowObj(
            o,
            mat
        //, phantom_material
        );

        RegisterTimeline(tl);
        m_GlowObjs[tl].Add(glow_obj);
    }

    public void Remove(GlowObj o)
    {
        foreach (var kv in m_GlowObjs)
        {
            kv.Value.Remove(o);
        }
    }
}

public class GlowObj
{
    public ObjectController obj;
    public Material material;

    //public Material phantom_material;

    //public CommandBuffer commandBuffer;

    // public Material PhantomMaterial()
    // {
    //     return phantom_material;
    // }

    public Material GlowMaterial()
    {
        return material;
    }

    public GlowObj(
        ObjectController g,
        Material m
    //, Material phantom_material
    )
    {
        obj = g;
        material = m;
        //this.phantom_material = phantom_material;
    }
}
