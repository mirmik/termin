using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

#if UNITY_64
using Newtonsoft.Json;
using UnityEditor;
using UnityEngine;
using Object = UnityEngine.Object;
#endif

public struct SpeedOverdrive
{
    public float speed;
    public float overdrive;

    public SpeedOverdrive(float speed, float overdrive)
    {
        this.speed = speed;
        this.overdrive = overdrive;
    }
}

public class AnimationCurveManager : MonoBehaviour
{
    public string UnicalName;
    public string BindToFile;
    public List<AnimationClip> clips = new List<AnimationClip>();
    private List<ClipInfo> ClipCurves = new List<ClipInfo>();
    static Dictionary<string, List<ClipInfo>> _animation_curves =
        new Dictionary<string, List<ClipInfo>>();

    string filePath()
    {
        return Application.streamingAssetsPath + "/" + UnicalName + "AnimationCurves.dat";
    }

    string overdriveFilePath()
    {
        return Application.streamingAssetsPath + "/" + UnicalName + "AnimationCurvesOverdrive.txt";
    }

    [Serializable]
    public sealed class ClipInfo
    {
        //public int ClipInstanceID;
        public string clipName;
        public List<CurveInfo> CurveInfos = new List<CurveInfo>();

        // default constructor is sometimes required for (de)serialization
        public ClipInfo() { }

        public ClipInfo(Object clip, string name, List<CurveInfo> curveInfos)
        {
            clipName = name;
            CurveInfos = curveInfos;
        }
    }

    [Serializable]
    public sealed class CurveInfo
    {
        public string PathKey;

        public List<KeyFrameInfo> Keys = new List<KeyFrameInfo>();
        public WrapMode PreWrapMode;
        public WrapMode PostWrapMode;

        // default constructor is sometimes required for (de)serialization
        public CurveInfo() { }

        public CurveInfo(string pathKey, AnimationCurve curve)
        {
            PathKey = pathKey;

            foreach (var keyframe in curve.keys)
            {
                Keys.Add(new KeyFrameInfo(keyframe));
            }

            PreWrapMode = curve.preWrapMode;
            PostWrapMode = curve.postWrapMode;
        }
    }

    [Serializable]
    public sealed class KeyFrameInfo
    {
        public float Value;
        public float InTangent;
        public float InWeight;
        public float OutTangent;
        public float OutWeight;
        public float Time;
        public WeightedMode WeightedMode;

        // default constructor is sometimes required for (de)serialization
        public KeyFrameInfo() { }

        public KeyFrameInfo(Keyframe keyframe)
        {
            Value = keyframe.value;
            InTangent = keyframe.inTangent;
            InWeight = keyframe.inWeight;
            OutTangent = keyframe.outTangent;
            OutWeight = keyframe.outWeight;
            Time = keyframe.time;
            WeightedMode = keyframe.weightedMode;
        }
    }

    public AnimationClip GetClipByNamePartial(string name)
    {
        if (clips == null)
            return null;

        foreach (var clip in clips)
        {
            //if (clip.name.Contains(name))
            //{
            if (clip.name == "Armature|" + name)
                return clip;
            //}
        }
        return null;
    }

    // every animation curve belongs to a specific clip and
    // a specific property of a specific component on a specific object
    // for making this easier lets simply use a combined string as key
    private string CurveKey(string pathToObject, string propertyName)
    {
        return $"{UnicalName}:{pathToObject}:{propertyName}";
    }

    bool _is_init = false;

    private void Awake() { }

    public void Init()
    {
        GuardView guard_view = GetComponent<GuardView>();
        if (guard_view != null)
        {
            Debug.Log($"AnimationManager Awake: GuardView not found ({gameObject.name})");
        }

        if (!_is_init)
            LoadClipCurves();
    }

    public void SetAnimationCurveManagerFromOtherObject(AnimationCurveManager other)
    {
        ClipCurves = other.ClipCurves;
        _is_init = true;
    }

    public SpeedOverdrive GetOverdrive(string clipName)
    {
        SpeedOverdrive so;
        if (Overdrive.ContainsKey(clipName))
        {
            var dct = Overdrive[clipName];
            so = new SpeedOverdrive(dct["speed"], dct["overdrive"]);
        }
        else
        {
            so = new SpeedOverdrive(1.0f, 1.0f);
        }
        //Debug.Log($"GetOverdrive: {clipName} {so.speed} {so.overdrive}");
        return so;
    }

#if UNITY_EDITOR
    // Call this from the ContextMenu (or later via editor script)
    [ContextMenu("Save Animation Curves")]
    private void SaveAnimationCurves()
    {
        // set dirty
        UnityEditor.EditorUtility.SetDirty(this);
        UnityEditor.EditorUtility.SetDirty(this.transform.parent.gameObject);

        ClipCurves.Clear();

        foreach (var clip in clips)
        {
            string name = clip.name;

            var curveInfos = new List<CurveInfo>();
            ClipCurves.Add(new ClipInfo(clip, name, curveInfos));

            foreach (var binding in AnimationUtility.GetCurveBindings(clip))
            {
                var key = CurveKey(binding.path, binding.propertyName);
                var curve = AnimationUtility.GetEditorCurve(clip, binding);

                curveInfos.Add(new CurveInfo(key, curve));
            }
        }

        // create the StreamingAssets folder if it does not exist
        try
        {
            if (!Directory.Exists(Application.streamingAssetsPath))
            {
                Directory.CreateDirectory(Application.streamingAssetsPath);
            }
        }
        catch (IOException ex)
        {
            Debug.LogError(ex.Message);
        }

        // create a new file e.g. AnimationCurves.dat in the StreamingAssets folder
        var json = JsonConvert.SerializeObject(ClipCurves);
        File.WriteAllText(filePath(), json);

        LoadOverdrive();
        FillOverdrive(ClipCurves);
        SaveOverdrive();

        ClipCurves.Clear();
        AssetDatabase.Refresh();
        AssetDatabase.SaveAssets();
    }

    [ContextMenu("Update From Binded FBX")]
    private void UpdateFromBindedFBX()
    {
        // set dirty
        UnityEditor.EditorUtility.SetDirty(this);
        UnityEditor.EditorUtility.SetDirty(this.transform.parent.gameObject);

        var path = BindToFile;
        Debug.Log($"BindToFile: {BindToFile}");

        //clips.Clear();
        List<AnimationClip> clips = new List<AnimationClip>();

        Object[] objects = AssetDatabase.LoadAllAssetsAtPath(path);
        foreach (var obj in objects)
        {
            if (obj is AnimationClip)
            {
                // if name starts with __preview__ it is a preview animation and should be ignored
                if (obj.name.StartsWith("__preview__"))
                    continue;
                clips.Add(obj as AnimationClip);
            }
        }

        this.clips = clips.OrderBy(x => x.name).ToList();

        AssetDatabase.SaveAssets();
    }
#endif

    public Dictionary<string, Dictionary<string, float>> Overdrive =
        new Dictionary<string, Dictionary<string, float>>();

    void LoadOverdrive()
    {
        var path = overdriveFilePath();

        if (!File.Exists(path))
        {
            Debug.Log("File not found!" + path);
            return;
        }

        var json = File.ReadAllText(path);
        var overdrive = JsonConvert.DeserializeObject<
            Dictionary<string, Dictionary<string, float>>
        >(json);

        Overdrive = overdrive;
    }

    void SaveOverdrive()
    {
        var path = overdriveFilePath();

        Debug.Log("SaveOverdrive: " + Overdrive.Count);

        var json = JsonConvert.SerializeObject(Overdrive, Formatting.Indented);
        File.WriteAllText(path, json);
    }

    void FillOverdrive(List<ClipInfo> ClipCurves)
    {
        foreach (var clip in ClipCurves)
        {
            if (Overdrive.ContainsKey(clip.clipName))
            {
                if (!Overdrive[clip.clipName].ContainsKey("speed"))
                    Overdrive[clip.clipName]["speed"] = 1.0f;

                if (!Overdrive[clip.clipName].ContainsKey("overdrive"))
                    Overdrive[clip.clipName]["overdrive"] = 1.0f;
            }
            else
            {
                Overdrive[clip.clipName] = new Dictionary<string, float>();
                Overdrive[clip.clipName]["speed"] = 1.0f;
                Overdrive[clip.clipName]["overdrive"] = 1.0f;
            }
        }
    }

    private void LoadClipCurves()
    {
        _is_init = true;

        if (_animation_curves.ContainsKey(UnicalName))
        {
            ClipCurves = _animation_curves[UnicalName];
            return;
        }

        if (!File.Exists(filePath()))
        {
            Debug.LogErrorFormat(this, "File \"{0}\" not found!", filePath());
            _animation_curves[UnicalName] = new List<ClipInfo>();
            return;
        }

        var json = File.ReadAllText(filePath());
        ClipCurves = JsonConvert.DeserializeObject<List<ClipInfo>>(json);
        _animation_curves[UnicalName] = new List<ClipInfo>(ClipCurves);

        LoadOverdrive();
        FillOverdrive(ClipCurves);
    }

    public bool HasCurve(AnimationClip clip, string pathToObject, string propertyName)
    {
        List<ClipInfo> ClipCurves2 = _animation_curves[UnicalName];

        // either not loaded yet or error -> try again
        if (ClipCurves2 == null || ClipCurves2.Count == 0)
            LoadClipCurves();

        // still null? -> error
        if (ClipCurves2 == null || ClipCurves2.Count == 0)
        {
            Debug.LogError("Apparantly no ClipCurves2 loaded!");
            return false;
        }

        var clipInfo = ClipCurves2.FirstOrDefault(ci => ci.clipName == clip.name);

        // does this clip exist in the dictionary?
        if (clipInfo == null)
        {
            Debug.LogErrorFormat(
                this,
                $"The clip \"{clip.name}\" was not found in ClipCurves2! for {UnicalName}"
            );
            return false;
        }

        var key = CurveKey(pathToObject, propertyName);

        var curveInfo = clipInfo.CurveInfos.FirstOrDefault(c => string.Equals(c.PathKey, key));

        // does the curve key exist for the clip?
        if (curveInfo == null)
        {
            return false;
        }

        return true;
    }

    static Dictionary<
        Tuple<string, AnimationClip, string, string>,
        AnimationCurve
    > _animation_curves_cache =
        new Dictionary<Tuple<string, AnimationClip, string, string>, AnimationCurve>();

    // now for getting a specific clip's curves
    public AnimationCurve GetCurve(AnimationClip clip, string pathToObject, string propertyName)
    {
        if (
            _animation_curves_cache.ContainsKey(
                new Tuple<string, AnimationClip, string, string>(
                    UnicalName,
                    clip,
                    pathToObject,
                    propertyName
                )
            )
        )
        {
            return _animation_curves_cache[
                new Tuple<string, AnimationClip, string, string>(
                    UnicalName,
                    clip,
                    pathToObject,
                    propertyName
                )
            ];
        }

        List<ClipInfo> ClipCurves2 = _animation_curves[UnicalName];

        // either not loaded yet or error -> try again
        if (ClipCurves2 == null || ClipCurves2.Count == 0)
            LoadClipCurves();

        // still null? -> error
        if (ClipCurves2 == null || ClipCurves2.Count == 0)
        {
            Debug.LogError("Apparantly no ClipCurves2 loaded!");
            return null;
        }

        var clipInfo = ClipCurves2.FirstOrDefault(ci => ci.clipName == clip.name);

        // does this clip exist in the dictionary?
        if (clipInfo == null)
        {
            Debug.LogErrorFormat(this, "The clip \"{0}\" was not found in ClipCurves2!", clip.name);
            return null;
        }

        var key = CurveKey(pathToObject, propertyName);

        var curveInfo = clipInfo.CurveInfos.FirstOrDefault(c => string.Equals(c.PathKey, key));

        // does the curve key exist for the clip?
        if (curveInfo == null)
        {
            Debug.LogErrorFormat(
                this,
                "The key \"{0}\" was not found for clip \"{1}\"",
                key,
                clip.name
            );
            return null;
        }

        var keyframes = new Keyframe[curveInfo.Keys.Count];

        for (var i = 0; i < curveInfo.Keys.Count; i++)
        {
            var keyframe = curveInfo.Keys[i];

            keyframes[i] = new Keyframe(
                keyframe.Time,
                keyframe.Value,
                keyframe.InTangent,
                keyframe.OutTangent,
                keyframe.InWeight,
                keyframe.OutWeight
            )
            {
                weightedMode = keyframe.WeightedMode
            };
        }

        var curve = new AnimationCurve(keyframes)
        {
            postWrapMode = curveInfo.PostWrapMode,
            preWrapMode = curveInfo.PreWrapMode
        };

        _animation_curves_cache[
            new Tuple<string, AnimationClip, string, string>(
                UnicalName,
                clip,
                pathToObject,
                propertyName
            )
        ] = curve;

        // otherwise finally return the AnimationCurve
        return curve;
    }
}

// public static class JsonConvert {
// 	public static string SerializeObject(object value)
// 	{
// 		return "";
// 	}

// 	public static T DeserializeObject<T>(string value)
// 	{
// 		return default(T);
// 	}
// }

public class RectTransformUtility
{
    public static bool RectangleContainsScreenPoint(RectTransform rectTransform, Vector2 position)
    {
        return false;
    }
}
