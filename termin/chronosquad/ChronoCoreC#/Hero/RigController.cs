using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using System.Text;
using System;

// using Unity.Collections;
// using Unity.Jobs;
// using UnityEngine.Jobs;
//using System.Threading.Tasks;

public struct TransformInfo
{
    public Vector3 position;
    public Quaternion rotation;
}

public struct PathData
{
    public string path;
    public long hash;

    public PathData(string path, long hash)
    {
        this.path = path;
        this.hash = hash;
    }
}

public class RigController : MonoBehaviour
{
    //static Dictionary<string, Dictionary<PathData, GameObject>> _rigs = new Dictionary<string, Dictionary<PathData, GameObject>>();

    static public long StringToHash(string str)
    {
        long hash = 0;
        for (int i = 0; i < str.Length; i++)
        {
            hash = hash * 31 + str[i];
        }
        return hash;
    }

    List<string> filter_channels = new List<string>()
    {
        // "HandIndex",
        // "HandMiddle",
        // "HandRing",
        // "HandPinky",
        // "HandThumb",
    };

    protected Transform _model_object;
    protected Transform _armature;
    protected bool _inited = false;
    protected Dictionary<PathData, Transform> _pathes = new Dictionary<PathData, Transform>();
    protected Dictionary<string, Transform> _pathes_by_name = new Dictionary<string, Transform>();
    protected Dictionary<long, Transform> _hashes = new Dictionary<long, Transform>();

    private MyList<Transform> _sorted_entries = new MyList<Transform>();
    private Transform[] _sorted_entries_array;

    //private TransformInfo[] _sorted_memorize;
    //TransformAccessArray m_AccessArray;

    Dictionary<long, int> _hash_to_index = new Dictionary<long, int>();

    public Dictionary<long, int> HashToIndexMap
    {
        get { return _hash_to_index; }
    }

    Dictionary<PathData, Transform> GetPathes()
    {
        MyList<string> nodes = new MyList<string>();
        Transform iterator = _armature;
        Dictionary<PathData, Transform> accumulator = new Dictionary<PathData, Transform>();
        GetPathesIteration(nodes, iterator, accumulator);
        return accumulator;
    }

    public bool IsInFilter(string clip_name)
    {
        foreach (var filter_channel in filter_channels)
        {
            if (clip_name.Contains(filter_channel))
            {
                return true;
            }
        }
        return false;
    }

    public void Init()
    {
        _model_object = this.transform.Find("Model");
        if (_model_object == null)
        {
            Debug.LogWarning("Model not found: " + this.gameObject.name);
            return;
        }

        _armature = _model_object.Find("Armature");
        if (_armature == null)
        {
            Debug.LogWarning("Armature not found: " + this.gameObject.name);
            return;
        }

        _pathes = GetPathes();
        _hashes = new Dictionary<long, Transform>();
        _sorted_entries = new MyList<Transform>();
        _hash_to_index = new Dictionary<long, int>();

        int i = 0;
        foreach (KeyValuePair<PathData, Transform> entry in _pathes)
        {
            bool skip = false;
            foreach (var filter_channel in filter_channels)
            {
                if (entry.Key.path.Contains(filter_channel))
                {
                    skip = true;
                    break;
                }
            }
            if (skip)
                continue;
            PathData path = entry.Key;
            Transform transform = entry.Value;
            _pathes_by_name.Add(path.path, transform);
            _hashes.Add(path.hash, transform.transform);
            _hash_to_index.Add(entry.Key.hash, i);
            _sorted_entries.Add(entry.Value.transform);
            i++;
        }
        _sorted_entries_array = _sorted_entries.ToArray();
        //m_AccessArray = new TransformAccessArray(_sorted_entries_array);
        _inited = true;
    }

    public MyList<string> PathesList
    {
        get
        {
            if (!_inited)
                Init();
            var result = new MyList<string>();
            foreach (KeyValuePair<PathData, Transform> entry in _pathes)
            {
                result.Add(entry.Key.path);
            }
            return result;
        }
    }

    public Dictionary<PathData, Transform> Pathes
    {
        get
        {
            if (!_inited)
                Init();
            return _pathes;
        }
    }

    void GetPathesIteration(
        MyList<string> nodes,
        Transform transform,
        Dictionary<PathData, Transform> accumulator
    )
    {
        nodes.Add(transform.name);

        StringBuilder sb = new StringBuilder();
        foreach (var node in nodes)
        {
            sb.Append(node);
            sb.Append("/");
        }
        var name = sb.ToString();
        name = name.Substring(0, name.Length - 1);
        //name = string.Join("/", nodes);


        accumulator.Add(new PathData(name, StringToHash(name)), transform);
        foreach (Transform child in transform.transform)
        {
            GetPathesIteration(nodes, child, accumulator);
        }
        nodes.RemoveAt(nodes.Count - 1);
    }

    Transform TransformForPath(PathData path)
    {
        return _pathes[path];
    }

    // find transform by name in the hierarchy
    GameObject FindTransform(string name)
    {
        Transform[] transforms = _model_object.GetComponentsInChildren<Transform>();
        foreach (Transform t in transforms)
        {
            if (t.name == name)
                return t.gameObject;
        }
        return null;
    }

    void ApplyImpl(AnimationValues priv_values)
    {
        if (priv_values.array_values != null)
        {
            ApplyImpl2(priv_values.array_values);
        }
        else
        {
            var values = priv_values.dict_values;
            foreach (KeyValuePair<string, AnimationChannelData> entry in values)
            {
                string path = entry.Key;
                AnimationChannelData data = entry.Value;
                Transform transform = _pathes_by_name[path];
                transform.SetLocalPositionAndRotation(data.position, data.rotation);
            }
        }
    }

    // NativeArray<AnimationChannelData> data;
    // PositionUpdaterJob job;
    // JobHandle jobHandle;

    void ApplyImpl2(MyList<AnimationChannelData> values)
    {
        // Parallel.For(0, values.Length, i =>
        // {
        // 	var val = values[i];
        // 	var transform = _sorted_entries_array[i];
        // 	transform.SetLocalPositionAndRotation(
        // 		val.position, val.rotation);
        // });

        // jobHandle.Complete();
        // data.Dispose();

        // data = new NativeArray<AnimationChannelData>(
        // 	values.Length, Allocator.Persistent);

        // for (int i = 0; i < values.Length; i++)
        // {
        // 	data[i] = values[i];
        // }

        // var job = new PositionUpdaterJob()
        // {
        // 	values = data
        // };

        if (_sorted_entries_array == null)
        {
            Debug.LogWarning("No sorted entries array");
            return;
        }

        if (_sorted_entries_array.Length != values.Count)
        {
            Debug.LogWarning("Different length of values and transforms");
            return;
        }

        int count = _sorted_entries_array.Length;
        for (int i = 0; i < count; i++)
        {
            var val = values[i];
            var transform = _sorted_entries_array[i];
            transform.SetLocalPositionAndRotation(val.position, val.rotation);
        }
        // jobHandle = job.Schedule(m_AccessArray);
    }

    // public struct PositionUpdaterJob : IJobParallelForTransform
    // {
    // 	[ReadOnly]
    // 	public NativeArray<AnimationChannelData> values;

    // 	public void Execute(int index, TransformAccess transform)
    // 	{
    // 		var value = values[index];
    // 		transform.localPosition = value.position;
    // 		transform.localRotation = value.rotation;
    // 	}
    // }


    void OnDestroy()
    {
        // TransformAccessArrays must be disposed manually.
        //m_AccessArray.Dispose();
    }

    // public void UpdateView()
    // {
    // 	if (values != null)
    // 		ApplyImpl(values);
    // 	if (values2 != null)
    // 		ApplyImpl2(values2);
    // }


    public void Apply(AnimationValues values)
    {
        //this.values = values;
        ApplyImpl(values); // Вызывается здесь вместо Update, чтобы не было проблем с порядком вызова
    }

    public void Apply(MyList<AnimationChannelData> values)
    {
        //values2 = values;
        ApplyImpl2(values); // Вызывается здесь вместо Update, чтобы не было проблем с порядком вызова
    }

    void SetAllValuesToZero()
    {
        foreach (KeyValuePair<long, Transform> entry in _hashes)
        {
            long path = entry.Key;
            Transform transform = entry.Value;
            transform.SetLocalPositionAndRotation(Vector3.zero, Quaternion.identity);
        }
    }

    // Start is called before the first frame update
    void Start()
    {
        if (!_inited)
            Init();
    }
}
