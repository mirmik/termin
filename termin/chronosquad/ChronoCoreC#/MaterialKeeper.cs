using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class MaterialKeeper : MonoBehaviour
{
    static MaterialKeeper _instance;
    bool _inited;

    static public MaterialKeeper Instance
    {
        get
        {
            if (_instance == null)
            {
                _instance = GameObject.FindFirstObjectByType<MaterialKeeper>();
                //_instance.Init();
            }
            return _instance;
        }
    }

    public void Awake()
    {
        if (_instance != null && _instance != this)
        {
            Destroy(gameObject);
            return;
        }

        Init();
    }

    public GameObject FindPrefabInList(string name)
    {
        foreach (var prefab in prefabs)
        {
            if (prefab.name == name)
            {
                return prefab;
            }
        }
        return null;
    }

    public Material FindMaterialInList(string name)
    {
        foreach (var material in materials)
        {
            if (material.name == name)
            {
                return material;
            }
        }
        return null;
    }

    public void Init()
    {
        _instance = this;
        if (_inited)
        {
            return;
        }

        _inited = true;

        dict_materials = new Dictionary<string, Material>();
        dict_shaders = new Dictionary<string, Shader>();
        dict_textures = new Dictionary<string, Texture2D>();
        dict_prefabs = new Dictionary<string, GameObject>();
        dict_audioClips = new Dictionary<string, AudioClip>();
        dict_fonts = new Dictionary<string, Font>();
        dict_tmpFonts = new Dictionary<string, TMPro.TMP_FontAsset>();

        foreach (var material in materials)
        {
            dict_materials[material.name] = material;
        }

        foreach (var shader in shaders)
        {
            dict_shaders[shader.name] = shader;
        }

        foreach (var texture in textures)
        {
            dict_textures[texture.name] = texture;
        }

        foreach (var prefab in prefabs)
        {
            dict_prefabs[prefab.name] = prefab;
        }

        foreach (var audioClip in audioClips)
        {
            dict_audioClips[audioClip.name] = audioClip;
        }

        foreach (var font in fonts)
        {
            dict_fonts[font.name] = font;
        }

        foreach (var font in fonts)
        {
            try
            {
                dict_tmpFonts[font.name] = TMPro.TMP_FontAsset.CreateFontAsset(font);
            }
            catch (System.Exception e)
            {
                Debug.Log(
                    "Failed to create TMP_FontAsset from font " + font.name + " " + e.Message
                );
            }
        }

        // dont destroy on load
        DontDestroyOnLoad(gameObject);
    }

    public List<Material> materials;
    public List<Shader> shaders;
    public List<Texture2D> textures;
    public List<GameObject> prefabs;
    public List<AudioClip> audioClips;
    public List<Font> fonts;

    Dictionary<string, Material> dict_materials = new Dictionary<string, Material>();
    Dictionary<string, Shader> dict_shaders = new Dictionary<string, Shader>();
    Dictionary<string, Texture2D> dict_textures = new Dictionary<string, Texture2D>();
    Dictionary<string, GameObject> dict_prefabs = new Dictionary<string, GameObject>();
    Dictionary<string, AudioClip> dict_audioClips = new Dictionary<string, AudioClip>();
    Dictionary<string, Font> dict_fonts = new Dictionary<string, Font>();
    Dictionary<string, TMPro.TMP_FontAsset> dict_tmpFonts =
        new Dictionary<string, TMPro.TMP_FontAsset>();

#if UNITY_64
    public Material GetMaterial(string name)
    {
        if (dict_materials.Count == 0)
        {
            foreach (var material in materials)
            {
                dict_materials[material.name] = material;
            }
        }

        return dict_materials[name];
    }

    public Shader GetShader(string name)
    {
        return dict_shaders[name];
    }

    public Texture2D GetTexture(string name)
    {
        if (name == null)
        {
            return null;
        }

        Texture2D texture;
        if (!dict_textures.TryGetValue(name, out texture))
        {
            //Debug.Log("Failed to get texture " + name);
            return null;
        }
        return texture;
    }

    public GameObject GetPrefab(string name)
    {
        return dict_prefabs[name];
    }

    public GameObject Instantiate(string name)
    {
        return GameObject.Instantiate(dict_prefabs[name]);
    }

    public AudioClip GetAudioClip(string name)
    {
        return dict_audioClips[name];
    }

    public Font GetFont(string name)
    {
        return dict_fonts[name];
    }

    public TMPro.TMP_FontAsset GetTMPFont(string name)
    {
        return dict_tmpFonts[name];
    }

#else
    public Material GetMaterial(string name)
    {
        return null;
    }

    public Shader GetShader(string name)
    {
        return null;
    }

    public Texture2D GetTexture(string name)
    {
        return null;
    }

    public GameObject GetPrefab(string name)
    {
        return null;
    }

    public AudioClip GetAudioClip(string name)
    {
        return null;
    }

    public Font GetFont(string name)
    {
        return null;
    }

    public TMPro.TMP_FontAsset GetTMPFont(string name)
    {
        return null;
    }

    public GameObject Instantiate(string name)
    {
        return null;
    }
#endif
}
