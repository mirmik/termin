using System.Diagnostics;
using System;
using System.Collections;
using System.Numerics;
using UnityEngine.Rendering;

#if !UNITY_64 && !UNITY_EDITOR


public static class GeometryUtility
{
    public static bool TestPlanesAABB(Plane[] planes, Bounds bounds)
    {
        return true;
    }

    public static bool TestPlanesAABB(Plane[] planes, Vector3 center, Vector3 size)
    {
        return true;
    }

    public static Plane[] CalculateFrustumPlanes(Camera camera, Plane[] planes)
    {
        return null;
    }

    public static Plane[] CalculateFrustumPlanes(Camera camera)
    {
        return null;
    }

    public static Plane[] CalculateFrustumPlanes(Camera camera, bool e)
    {
        return null;
    }
}

public static class Gizmos
{
    static public void DrawIcon(Vector3 pos, string name, bool allowScaling = true) { }

    static public void DrawLine(Vector3 a, Vector3 b) { }

    static public void DrawRay(Vector3 a, Vector3 b) { }

    static public void DrawSphere(Vector3 pos, float radius) { }

    static public void DrawWireSphere(Vector3 pos, float radius) { }

    static public void DrawWireCube(Vector3 pos, Vector3 radius) { }

    static public void DrawCube(Vector3 pos, Vector3 size) { }

    static public Color color { get; set; }
}

public enum WrapMode { }

public enum WeightedMode { }

public class NavMeshDataInstance
{
    public bool valid;
}

public class RequireComponent : Attribute
{
    public RequireComponent(Type t) { }
}

public class ExecuteInEditMode : Attribute
{
    public ExecuteInEditMode() { }
}

public class SerializeFieldAttribute : Attribute
{
    public SerializeFieldAttribute() { }
}

public class IgnoredByDeepProfilerAttributeAttribute : Attribute
{
    public IgnoredByDeepProfilerAttributeAttribute() { }
}

public class ExecuteAlways : Attribute { }

public class Keyframe
{
    public float value;
    public float inTangent;
    public float inWeight;
    public float outTangent;
    public float outWeight;
    public float time;
    public WeightedMode weightedMode;

    public Keyframe(
        float time,
        float value,
        float InTangent,
        float OutTangent,
        float InWeight,
        float OutWeight
    ) { }
}

interface IObjectPool<T>
{
    T Get();
    void Release(T obj);
}

class SimpleFilter : MonoBehaviour
{
    public bool IsMatch(string str)
    {
        return true;
    }
}

public static class Time
{
    public static float time => 0;
    public static float deltaTime => 0;
    public static float fixedDeltaTime => 0;
}

public class LayerMask
{
    public static int NameToLayer(string name)
    {
        return 0;
    }

    static public int GetMask(string name)
    {
        return -1;
    }

    // convertable to int
    public static implicit operator int(LayerMask mask)
    {
        return 0;
    }

    // convertable from int
    public static implicit operator LayerMask(int mask)
    {
        return new LayerMask();
    }
}

public struct Size
{
    public int width;
    public int height;

    public Size(int width, int height)
    {
        this.width = width;
        this.height = height;
    }
}

public struct Screen
{
    static public int width = 1960;
    static public int height = 800;
    public static Rect rect => new Rect();
    public static Size currentResolution => new Size(1960, 800);
}

public enum PrimitiveType
{
    Sphere,
    Cube,
    Cylinder,
    Plane
}

namespace UnityEngine.UI { }

namespace TMPro
{
    public enum TextAlignmentOptions
    {
        TopLeft
    }

    public enum TextWrappingModes
    {
        Normal
    }

    public class TMP_FontAsset
    {
        public static TMP_FontAsset CreateFontAsset(UnityEngine.Font font)
        {
            return new TMP_FontAsset();
        }
    }

    public class TMP_Dropdown : MonoBehaviour
    {
        public float value;

        public UI.Dropdown.DropdownEvent onValueChanged;
    }
}

namespace UI.Dropdown
{
    public class DropdownEvent
    {
        public void AddListener(Action<int> action) { }
    }
}

public class CanvasScaler : MonoBehaviour
{
    public float scaleFactor;
}

public class AudioClip
{
    public string name;
}

public class AudioSource : MonoBehaviour
{
    public AudioClip clip;
    public float time;
    public float pitch;
    public float volume;

    public void Play() { }

    public void Stop() { }
}

public class NavMeshHit { }

public class ObjectPool<T> : IObjectPool<T>
{
    Func<T> _factory;
    Action<T> _reset;

    public ObjectPool(Func<T> factory, Action<T> reset = null)
    {
        _factory = factory;
        _reset = reset;
    }

    public T Get()
    {
        return _factory();
    }

    public void Release(T obj)
    {
        _reset(obj);
    }
}

public enum CollectObjects
{
    Children
}

public enum LoadSceneMode
{
    Single
}

public class NavMeshSurface : MonoBehaviour
{
    public int defaultArea;
    public int agentTypeID;

    public CollectObjects collectObjects;

    public void BuildNavMesh() { }

    public void RemoveData() { }
}

public class Scene
{
    public string name;
}

public static class SceneManager
{
    public static void LoadScene(string name) { }

    public static AsyncOperation LoadSceneAsync(string name)
    {
        return null;
    }

    // UnloadScene
    public static void UnloadScene(string name) { }

    public static void UnloadSceneAsync(string name) { }

    public static Scene GetActiveScene()
    {
        return new Scene();
    }

    static public Action<Scene, LoadSceneMode> sceneLoaded;
    static public Action<Scene> sceneUnloaded;
}

public enum FilterMode
{
    Point,
    Bilinear
}

public enum HideFlags
{
    None
}

public class CombineInstance
{
    public Mesh mesh;
    public Matrix4x4 transform;
}

public class NavMeshLink : MonoBehaviour
{
    public Vector3 startPoint;
    public Vector3 endPoint;
    public float width;
    public bool bidirectional;
    public bool autoUpdate;
    public int area = 0;

    // found agent type 'S'
    public int agentTypeID;
    public int costModifier;
    public string tag;
    public HideFlags hideFlags;

    public void UpdateLink() { }
}

public class Sprite
{
    public Texture2D texture;
    public Rect rect;
    public Vector2 center;

    public static Sprite Create(Texture2D texture, Rect rect, Vector2 center)
    {
        var sprite = new Sprite
        {
            texture = texture,
            rect = rect,
            center = center
        };
        return sprite;
    }
}

namespace TMPro
{
    public class TextMeshProUGUI : MonoBehaviour
    {
        public int fontSize = 20;
        public TextWrappingModes textWrappingMode = TextWrappingModes.Normal;
        public string text;
        public RectTransform rectTransform;
        public Color color;
        public TextAlignmentOptions alignment;
        public TMP_FontAsset font;

        public int preferredWidth;
        public int preferredHeight;
    }

    public class TMP_InputField : MonoBehaviour
    {
        public string text;
        public int fontSize = 20;
        public bool textWrappingMode = false;
        public RectTransform rectTransform;
        public Color color;
        public TextAlignmentOptions alignment;
        public TMP_FontAsset font;

        public void ActivateInputField() { }

        public void DeactivateInputField() { }
    }
}

public static class NavMeshBuilder
{
    public static NavMeshData BuildNavMeshData(
        UnityEngine.AI.NavMeshBuildSettings settings,
        List<NavMeshBuildSource> navMeshDataSources,
        Bounds bounds,
        Vector3 vec,
        Quaternion q
    )
    {
        return default(NavMeshData);
    }
}

public enum RenderMode
{
    ScreenSpaceOverlay
}

public class Canvas : MonoBehaviour
{
    public RenderMode renderMode;
}

public enum NavMeshBuildSourceShape
{
    Mesh,
    Box,
    Capsule,
    Sphere
}

public class NavMeshBuildSource
{
    public NavMeshBuildSourceShape shape;
    public Matrix4x4 transform;
    public int area;
    public Vector3 size;
    public object sourceObject;
    public object component;
}

public class NavMeshData { }

public static class Mathf
{
    public const float PI = 3.1415926535897932384626433832795f;
    public const float Infinity = float.PositiveInfinity;

    static public float Tan(float f)
    {
        return (float)Math.Tan((double)f);
    }

    public const float Deg2Rad = (float)(PI / 180.0f);
    public const float Rad2Deg = (float)(180.0f / PI);

    static public float Lerp(float a, float b, float t)
    {
        return a + (b - a) * t;
    }

    // arcsin
    static public float Asin(float a)
    {
        return (float)Math.Asin((double)a);
    }

    static public float Acos(float a)
    {
        return (float)Math.Acos((double)a);
    }

    static public float Sin(float a)
    {
        return (float)Math.Sin((double)a);
    }

    static public float Atan(float a)
    {
        return (float)Math.Atan((double)a);
    }

    static public float Cos(float a)
    {
        return (float)Math.Cos((double)a);
    }

    static public float Abs(float a)
    {
        return (float)Math.Abs((double)a);
    }

    static public float Sqrt(float a)
    {
        return (float)Math.Sqrt((double)a);
    }

    static public float Pow(float a, float b)
    {
        return (float)Math.Pow((double)a, (double)b);
    }

    static public float Min(float a, float b)
    {
        return Math.Min(a, b);
    }

    static public float Atan2(float a, float b)
    {
        return (float)Math.Atan2((double)a, (double)b);
    }

    // fract
    static public float Fract(float a)
    {
        return a - (float)Math.Floor(a);
    }

    static public float Min(float a, float b, float c)
    {
        return Math.Min(a, Math.Min(b, c));
    }

    static public float Max(float a, float b)
    {
        return Math.Max(a, b);
    }

    static public float Max(float a, float b, float c)
    {
        return Math.Max(a, Math.Max(b, c));
    }

    static public float Min(float a, float b, float c, float d)
    {
        return Math.Min(a, Math.Min(b, Math.Min(c, d)));
    }

    static public float Max(float a, float b, float c, float d)
    {
        return Math.Max(a, Math.Max(b, Math.Max(c, d)));
    }

    static public float Clamp(float a, float min, float max)
    {
        return Math.Min(Math.Max(a, min), max);
    }

    // floor
    static public float Floor(float a)
    {
        return (float)Math.Floor(a);
    }

    static public float Sign(float a)
    {
        return Math.Sign(a);
    }

    // ceil
    static public float Ceil(float a)
    {
        return (float)Math.Ceiling(a);
    }
}

public class BoxCollider : Collider
{
    public Vector3 size;
    public Vector3 center;
}

public class MeshCollider : Collider
{
    public Vector3 size;
    public Vector3 center;

    public Mesh sharedMesh;
}

public class CapsuleCollider : Collider
{
    public Vector3 size;
    public Vector3 center;
    public float radius;
    public float height;
}

public class SphereCollider : Collider
{
    public Vector3 size;
    public Vector3 center;
    public float radius;
}

public class NavMeshLinkData
{
    public Vector3 startPosition;
    public Vector3 endPosition;
    public float width;
    public int area;
    public int agentTypeID;
    public float costModifier;
    public bool bidirectional;
}

public class NavMeshLinkInstance
{
    public GameObject owner;
}

public enum CursorMode
{
    Auto
}

public static class Cursor
{
    static public bool visible;

    static public void SetCursor(Texture2D texture, Vector2 hotSpot, CursorMode mode) { }
}

public class RectTransform : MonoBehaviour
{
    public Vector2 anchorMin;
    public Vector2 anchorMax;
    public Vector2 offsetMin;
    public Vector2 offsetMax;
    public Vector2 sizeDelta;
    public Vector2 pivot;
    public Vector3 anchoredPosition;
    public Rect rect;
}

public class Image : MonoBehaviour
{
    public Material material;
    public Sprite sprite;
    public RectTransform rectTransform;
    public Vector3 anchorMin;
    public Vector3 anchorMax;
    public Color color;
    public Texture2D mainTexture;
}

public class Button : MonoBehaviour { }

public class AsyncOperation : IEnumerator
{
    public float progress;
    public bool isDone;
    public object Current => null;

    public void Reset() { }

    public bool MoveNext()
    {
        return false;
    }
}

public class Component
{
    public virtual GameObject gameObject { get; set; }
}

public class MonoBehaviour : Component
{
    public bool enabled;

    public static void StartCoroutine(IEnumerator ops) { }

    public static Mesh Instantiate(Mesh mesh)
    {
        return new Mesh();
    }

    public void DontDestroyOnLoad(GameObject obj) { }

    static public void DestroyImmediate(GameObject obj) { }

    static public void DestroyImmediate(MonoBehaviour obj) { }

    public static GameObject Instantiate(GameObject mesh)
    {
        return new GameObject();
    }

    public static GameObject Instantiate(GameObject mesh, Vector3 pos, Quaternion rot)
    {
        return new GameObject();
    }

    public Transform transform
    {
        get { return gameObject.transform; }
        set { gameObject.transform = value; }
    }

    public Vector3 localPosition
    {
        get { return transform.localPosition; }
        set { transform.localPosition = value; }
    }

    public Vector3 position
    {
        get { return transform.position; }
        set { transform.position = value; }
    }

    public Quaternion localRotation
    {
        get { return transform.localRotation; }
        set { transform.localRotation = value; }
    }

    public Quaternion rotation
    {
        get { return transform.rotation; }
        set { transform.rotation = value; }
    }

    static public T[] FindObjectsByType<T>() where T : Component
    {
        return new T[0];
    }

    static public T[] FindObjectsByType<T>(FindObjectsSortMode mode) where T : Component
    {
        return new T[0];
    }

    public void Destroy(object obj) { }

    public T GetComponent<T>() where T : class
    {
        return gameObject.GetComponent<T>();
    }

    public MyList<T> GetComponents<T>() where T : Component
    {
        return new MyList<T>();
    }

    public T GetComponentInChildren<T>() where T : Component
    {
        return GetComponent<T>();
    }

    public MyList<T> GetComponentsInChildren<T>() where T : Component
    {
        return new MyList<T>();
    }

    public T FindFirstObjectByType<T>() where T : Component
    {
        return GameObject.FindFirstObjectByType<T>();
    }

    public string name
    {
        get { return gameObject.name; }
        set { gameObject.name = value; }
    }
}

public class RenderTexture : Texture2D
{
    public RenderTexture(int width, int height, int depth) : base(width, height) { }

    public RenderTexture(int width, int height, int depth, RenderTextureFormat a)
        : base(width, height) { }

    public FilterMode filterMode;
}

public class CommandBuffer
{
    public string name = "HologramDepthRender";

    public void SetViewProjectionMatrices(Matrix4x4 a, Matrix4x4 b) { }

    public void SetRenderTarget(Texture2D tex) { }

    public void SetRenderTarget(RenderTargetIdentifier rt) { }

    public void ClearRenderTarget(bool a, bool b, Color c, float f = 0.0f) { }

    public void SetGlobalTexture(string s, Texture2D tex) { }

    public void SetGlobalTexture(string s, RenderTargetIdentifier tex) { }

    public void DrawRenderer(Renderer renderer, Material material, int i = 0) { }

    public void Blit(RenderTargetIdentifier a, RenderTargetIdentifier b) { }

    public void Blit(RenderTargetIdentifier a, RenderTargetIdentifier b, Material m) { }

    public void Blit(BuiltinRenderTextureType a, BuiltinRenderTextureType b, Material m) { }

    public void Blit(Texture2D a, RenderTargetIdentifier b, Material m) { }

    public void SetupCameraProperties(Camera camera) { }

    public void Clear() { }
}

public static class Application
{
    static public string streamingAssetsPath = "";
    static public int targetFrameRate = 60;

    static public bool isEditor => false;
    static public bool isPlaying => true;
}

public class AnimationCurve
{
    public WrapMode postWrapMode;
    public WrapMode preWrapMode;

    public float Evaluate(float t)
    {
        return 0;
    }

    public Keyframe[] keys;

    public AnimationCurve(Keyframe[] keys)
    {
        this.keys = keys;
    }
}

public class AnimationClip
{
    public float length;
    public string name;
}

static public class RenderSettings
{
    public static Color ambientLight = new Color(0.5f, 0.5f, 0.5f, 1);
    public static Material skybox;
}

public class Material
{
    public Color color;
    public Shader shader;

    public static Material Find(string name)
    {
        return new Material();
    }

    public void EnableKeyword(string s) { }

    public bool HasProperty(string s)
    {
        return true;
    }

    public Material() { }

    public Material(string str) { }

    public Material(Material material) { }

    public void SetColor(string name, Color color) { }

    public Material(Shader shader) { }

    public void SetFloat(string name, float value) { }

    //public void SetTexture(string name, Texture texture) { }

    public void SetVector(string name, Vector4 vector) { }

    public void SetVector(string name, Vector3 vector) { }

    public void SetVector(string name, Vector2 vector) { }

    public void SetTexture(string name, Texture2D texture) { }

    public void SetMatrix(string name, Matrix4x4 matrix) { }

    public void SetInt(string name, int value) { }

    public string name;
}

public static class GL
{
    public static Matrix4x4 GetGPUProjectionMatrix(Matrix4x4 a, bool b)
    {
        return a;
    }
}

public class Shader
{
    public string name;

    public static Shader Find(string name)
    {
        return new Shader();
    }

    public static void SetGlobalFloat(string name, float value) { }

    public static void SetGlobalInt(string name, int value) { }

    public static void SetGlobalVector(string name, Vector4 value) { }

    public static void SetGlobalVector(string name, Vector3 value) { }

    public static void SetGlobalVector(string name, Vector2 value) { }

    public static void SetGlobalColor(string name, Color value) { }

    public static void SetGlobalMatrix(string name, Matrix4x4 value) { }

    public static void SetGlobalTexture(string name, Texture2D value) { }
}

public class GameObject : Component
{
    public bool activeSelf = true;

    public override GameObject gameObject => this;

    static public void DestroyImmediate(GameObject obj) { }

    public Transform transform;

    public int layer = 0;

    public Scene scene;

    static public T[] FindObjectsByType<T>() where T : Component
    {
        return new T[0];
    }

    static public T[] FindObjectsOfType<T>() where T : Component
    {
        return new T[0];
    }

    static public T[] FindObjectsByType<T>(FindObjectsSortMode mode) where T : Component
    {
        return new T[0];
    }

    public GameObject()
    {
        this.transform = new Transform(this);
    }

    public MyList<Component> _components = new MyList<Component>();

    public string name;

    static public GameObject CreatePrimitive(PrimitiveType type)
    {
        var a = new GameObject("primitive");
        a.AddComponent<Renderer>();
        return a;
    }

    public T[] GetComponentsInChildren<T>()
    {
        return new T[0];
    }

    public T[] GetComponents<T>()
    {
        return new T[0];
    }

    public static GameObject Instantiate(GameObject instance_prototype)
    {
        var go = new GameObject("instance");
        go.name = instance_prototype.name;
        go.transform = new Transform(go);
        foreach (var component in instance_prototype._components)
        {
            var new_component =
                component.GetType().GetConstructor(new Type[] { }).Invoke(new object[] { })
                as MonoBehaviour;
            new_component.gameObject = go;
            go._components.Add(new_component);
        }
        return go;
    }

    public T AddComponent<T>() where T : Component, new()
    {
        var component = new T();
        component.gameObject = this;
        _components.Add(component);
        return component;
    }

    public void SetActive(bool active)
    {
        activeSelf = active;
    }

    // public T GetComponent<T>() where T : Component
    // {
    // 	foreach (var component in _components)
    // 	{
    // 		if (component is T)
    // 		{
    // 			return (T)component;
    // 		}
    // 	}
    // 	return null;
    // }

    // GetComponent from  interface
    public T GetComponent<T>() where T : class
    {
        foreach (var component in _components)
        {
            if (component is T)
            {
                return component as T;
            }
        }
        return null;
    }

    public bool TryGetComponent<T>(out T component) where T : Component
    {
        component = GetComponent<T>();
        return component != null;
    }

    static public void Destroy(object obj) { }

    public GameObject(string name)
    {
        this.name = name;
        this.transform = new Transform(this);
    }

    static public GameObject Find(string name)
    {
        return new GameObject("found");
    }

    static public T FindFirstObjectByType<T>() where T : Component
    {
        var a = new GameObject("found");
        //a.AddComponent<T>();
        return a.GetComponent<T>();
    }

    public void Preset() { }

    static public string WithoutPostfix(string str)
    {
        var lst = str.Split("|");
        return lst[0];
    }
}

public class LineRenderer : MonoBehaviour
{
    public Material material;
    public float startWidth;
    public float endWidth;
    public Color startColor;
    public Color endColor;
    public bool useWorldSpace;
    public UnityEngine.Rendering.ShadowCastingMode shadowCastingMode;

    public void SetPosition(int i, Vector3 pos) { }

    public int positionCount;

    public void SetPositions(Vector3[] projection) { }

    public bool loop;
}

public class MeshRenderer : Renderer
{
    public Material[] sharedMaterials { get; set; }
}

public class Ray
{
    public Vector3 direction;
    public Vector3 origin;

    public Ray() { }

    public Ray(Vector3 pos, Vector3 dir) { }

    public Vector3 GetPoint(float distance)
    {
        return new Vector3();
    }
}

public enum MeshTopology
{
    Triangles
}

public class Plane
{
    Vector3 pos = new Vector3();
    Vector3 normal = new Vector3();

    public Plane(Vector3 inNormal, Vector3 inPoint)
    {
        this.pos = inPoint;
        this.normal = inNormal;
    }

    public Plane() { }

    public bool Raycast(Ray ray, out float enter, float maxdist = float.MaxValue)
    {
        enter = 0;
        return true;
    }
}

public enum DepthTextureMode
{
    Depth,
    DepthNormals,
    None
}

public class Camera : MonoBehaviour
{
    public Rect rect;
    public bool orthographic;
    public float orthographicSize;
    public float aspect;

    public float fieldOfView;

    public Texture2D targetTexture;

    public Matrix4x4 projectionMatrix;
    public Matrix4x4 worldToCameraMatrix;
    public DepthTextureMode depthTextureMode;

    public int cullingMask;

    //farClipPlane
    public float farClipPlane;
    public float nearClipPlane;

    public Vector2 WorldToScreenPoint(Vector3 v)
    {
        return Vector2.zero;
    }

    public static Camera main { get; set; }

    public void Render() { }

    public Ray ScreenPointToRay(Vector2 pos)
    {
        return new Ray();
    }

    public Ray ScreenPointToRay(Vector3 pos)
    {
        return new Ray();
    }

    public Vector2 WorldToViewportPoint(Vector3 v)
    {
        return new Vector2();
    }

    public void AddCommandBuffer(CameraEvent evt, CommandBuffer buf) { }

    public void RemoveCommandBuffer(CameraEvent evt, CommandBuffer buf) { }
}

public static class Graphics
{
    // blit
    public static void Blit(Texture2D source, RenderTexture dest, Material mat) { }

    public static void ExecuteCommandBuffer(CommandBuffer buf) { }
}

public class RenderTargetIdentifier
{
    public RenderTargetIdentifier(RenderTexture rt) { }
}

public struct Rect
{
    public float x;
    public float y;
    public float width;
    public float height;

    public Rect(float x, float y, float width, float height)
    {
        this.x = x;
        this.y = y;
        this.width = width;
        this.height = height;
    }

    public bool Contains(Vector2 pos)
    {
        return pos.x >= x && pos.x <= x + width && pos.y >= y && pos.y <= y + height;
    }
}

public class MeshFilter : MonoBehaviour
{
    public Mesh mesh { get; set; }
    public Mesh sharedMesh { get; set; }
}

public class RaycastHit
{
    public Vector3 point;
    public Vector3 normal;
    public float distance;

    public RaycastHit() { }

    public GameObject collider;
    public GameObject gameObject;

    public Transform transform;
}

public class Color
{
    public static Color red = new Color();
    public static Color green = new Color();
    public static Color blue = new Color();
    public static Color white = new Color();
    public static Color black = new Color();
    public static Color yellow = new Color();
    public static Color cyan = new Color();
    public static Color magenta = new Color();
    public static Color gray = new Color();
    public static Color grey = new Color();
    public static Color clear = new Color();

    public Color() { }

    public Color(float a, float b, float c, float d) { }

    public Color(float a, float b, float c) { }

    public static Color operator +(Color a, Color b)
    {
        return new Color();
    }

    public static Color operator *(Color a, float c)
    {
        return new Color();
    }

    public static Color operator *(float c, Color a)
    {
        return new Color();
    }
}

public class Transform : Component
{
    MyList<Transform> _children = new MyList<Transform>();
    Transform _parent = null;

    public Transform() { }

    public Transform transform => this;

    public Vector3 TransformDirection(Vector3 dir)
    {
        return dir;
    }

    public T[] GetComponentsInChildren<T>() where T : Component
    {
        return default(T[]);
    }

    public void SetPositionAndRotation(Vector3 pos, Quaternion rot) { }

    public void SetLocalPositionAndRotation(Vector3 pos, Quaternion rot) { }

    public Vector3 TransformPoint(Vector3 dir)
    {
        return dir;
    }

    public Vector3 InverseTransformDirection(Vector3 dir)
    {
        return dir;
    }

    public Vector3 InverseTransformPoint(Vector3 dir)
    {
        return dir;
    }

    public void Rotate(Vector3 axis, float angle) { }

    public void Rotate(Vector3 axis) { }

    public Transform(GameObject obj)
    {
        gameObject = obj;
    }

    public Transform GetChild(int i)
    {
        return new Transform();
    }

    public int childCount => _children.Count;

    public Transform parent
    {
        get { return _parent; }
        set
        {
            if (_parent != null)
            {
                _parent._children.Remove(this);
            }
            _parent = value;
            if (_parent != null)
            {
                _parent._children.Add(this);
            }
        }
    }
    public string name => gameObject.name;

    public Vector3 position;
    public Vector3 localScale;
    public Quaternion localRotation;
    public Vector3 localPosition;
    public Quaternion rotation;

    public Vector3 forward => new Vector3(0, 0, 1);
    public Vector3 right => new Vector3(1, 0, 0);
    public Vector3 up => new Vector3(0, 1, 0);

    public Matrix4x4 localToWorldMatrix;

    public void SetParent(Transform parent, bool worldPositionStays = true)
    {
        this.parent = parent;
    }

    public T GetComponent<T>()
    {
        return default(T);
    }

    public bool TryGetComponent<T>(out T result) where T : MonoBehaviour
    {
        result = default(T);
        return false;
    }

    //public GameObject gameObject;

    public IEnumerator<Transform> GetEnumerator()
    {
        return _children.GetEnumerator();
    }

    public Transform Find(string name)
    {
        foreach (var child in _children)
        {
            if (child.name == name)
            {
                return child;
            }
        }
        return null;
    }
}

public static class Physics
{
    public class QueryParameters
    {
        public int layerMask;

        public QueryParameters(int layerMask)
        {
            this.layerMask = layerMask;
        }
    }

    public static bool Raycast(Ray ray, out RaycastHit hit, float maxDistance = float.MaxValue)
    {
        hit = new RaycastHit();
        return true;
    }

    public static RaycastHit[] RaycastAll(Ray ray, float maxDistance, int layerMask)
    {
        return new RaycastHit[0];
    }

    public static RaycastHit[] RaycastAll(
        Vector3 origin,
        Vector3 direction,
        float maxDistance,
        int layerMask
    )
    {
        return new RaycastHit[0];
    }

    public static bool Raycast(
        Vector3 origin,
        Vector3 direction,
        out RaycastHit hit,
        float maxDistance,
        int layerMask
    )
    {
        hit = new RaycastHit();
        return true;
    }

    public static bool Raycast(
        Vector3 origin,
        Vector3 direction,
        out RaycastHit hit,
        float maxDistance
    )
    {
        hit = new RaycastHit();
        return true;
    }

    public static bool Raycast(
        Vector3 origin,
        Vector3 direction,
        out RaycastHit hit,
        QueryParameters queryParameters,
        int layerMask
    )
    {
        hit = new RaycastHit();
        return true;
    }

    public static bool Raycast(Ray ray, out RaycastHit hit, float maxDistance, int layerMask)
    {
        hit = new RaycastHit();
        return true;
    }

    public static Collider[] OverlapSphere(Vector3 pos, float radius, int layerMask)
    {
        return new Collider[0];
    }

    public static Collider[] OverlapSphere(Vector3 pos, float radius)
    {
        return new Collider[0];
    }

    public static void Simulate(float fixeddelta) { }
}

public enum FindObjectsSortMode
{
    None
}

public static class QualitySettings
{
    static public string[] names = new string[0];

    public static int antiAliasing = 0;
    public static int vSyncCount;

    public static void SetQualityLevel(int i) { }

    public static int pixelLightCount = 0;

    public static int shadowCascades = 0;

    public static int shadowDistance = 0;
}

public enum CameraEvent
{
    AfterDepthTexture,
    AfterForwardOpaque,
    BeforeForwardOpaque,
    AfterForwardAlpha,
    BeforeSkybox,
    BeforeForwardAlpha
}

public enum EventType
{
    KeyDown,
    KeyUp,
    ScrollWheel,
    MouseDown,
    MouseUp,
    MouseDrag
}

public enum KeyCode
{
    Backslash,
    Backspace,
    Tab,
    UpArrow,
    DownArrow,
    Return,
    LeftArrow,
    RightArrow,
    Space,
    J,
    BackQuote,
    LeftShift,
    LeftControl,
    RightShift,
    RightControl,
    LeftAlt,
    RightAlt,
    Delete,
    Escape,
    F1,
    F2,
    F3,
    F4,
    F5,
    F6,
    F7,
    F8,
    F9,
    F10,
    F11,
    F12,
    Alpha0,
    Alpha1,
    Alpha2,
    Alpha3,
    Alpha4,
    Alpha5,
    Alpha6,
    Alpha7,
    Alpha8,
    Alpha9,
    A,
    B,
    C,
    D,
    E,
    F,
    G,
    H,
    I,
    K,
    L,
    M,
    N,
    O,
    P,
    Q,
    R,
    S,
    T,
    U,
    V,
    W,
    X,
    Y,
    Z,
}

public class Event
{
    public Vector2 delta;
    public EventType type;
    static public Event current { get; set; }
    public KeyCode keyCode;
    public int button;

    public Vector2 mousePosition;

    public bool isKey;
}

public class Mesh
{
    public Vector3[] vertices;
    public int[] triangles;
    public Vector2[] uv;
    public Vector2[] uv2;
    public Vector3[] normals;
    public Vector4[] tangents;
    public string name;

    public int vertexCount => 0;

    public static Mesh Instantiate(Mesh mesh)
    {
        return new Mesh();
    }

    public void SetIndices(int[] indices, MeshTopology triangles, int i) { }

    public void MarkDynamic() { }

    public void Clear() { }

    public void CombineMeshes(CombineInstance[] arr, bool b = false, bool c = false) { }

    public void RecalculateBounds() { }

    public void RecalculateNormals() { }
}

public class GraphicRaycaster : MonoBehaviour
{
    //public void Raycast(PointerEventData eventData, MyList<RaycastResult> resultAppendList) { }
}

public class Bounds
{
    public Vector3 center;
    public Vector3 size;

    public Bounds(Vector3 center, Vector3 size)
    {
        this.center = center;
        this.size = size;
    }

    public Vector3 min;
    public Vector3 max;

    public bool Contains(Vector3 pos)
    {
        return true;
    }

    public bool Intersects(Bounds b)
    {
        return true;
    }

    public void Encapsulate(Vector3 pos) { }

    public void Expand(Vector3 f) { }

    public void SetMinMax(Vector3 min, Vector3 max) { }

    public void SetCenterAndSize(Vector3 center, Vector3 size) { }

    public bool IntersectRay(Ray ray, out float distance)
    {
        distance = 0;
        return true;
    }

    public bool IntersectRay(Ray ray)
    {
        return true;
    }
}

public class SkinnedMeshRenderer : MeshRenderer
{
    Mesh _mesh;

    public Mesh sharedMesh
    {
        get { return _mesh; }
        set { _mesh = value; }
    }

    public Bounds localBounds { get; set; }
}

public class Collider : MonoBehaviour
{
    public Vector3 ClosestPoint(Vector3 pos)
    {
        return Vector3.zero;
    }

    public Bounds bounds;

    public bool isTrigger;
}

namespace UnityEngine.EventSystems
{
    public struct PointerEventData { }
}

interface IPointerClickHandler { }

public enum TextureFormat
{
    RGBAFloat
}

public class Texture2D : Texture
{
    public Texture2D(int width, int height) : base(width, height) { }

    public Texture2D(int width, int height, TextureFormat textureFormat, bool mipChain)
        : base(width, height) { }

    public byte[] EncodeToPNG()
    {
        return new byte[0];
    }

    public void LoadImage(byte[] bytes) { }
}

public class Texture
{
    public string name;
    public int width;
    public int height;

    public Texture(int width, int height)
    {
        this.width = width;
        this.height = height;
    }

    public void Apply() { }

    public void SetPixel(int x, int y, Color color) { }
}

static public class Debug
{
    public static void Log(string msg)
    {
        Console.WriteLine(msg);
    }

    public static void DrawLine(Vector3 p1, Vector3 p2, Color color, int s) { }

    public static void LogErrorFormat(string format, params object[] args) { }

    public static void LogErrorFormat(Object context, string format, params object[] args) { }

    public static void Assert(bool cond)
    {
        if (!cond)
        {
            var trace = new System.Diagnostics.StackTrace(true);
            var frame = trace.GetFrame(1);
            var method = frame.GetMethod();
            var method_name = method.Name;
            var line = frame.GetFileLineNumber();
            var file_path = frame.GetFileName();
            Console.WriteLine($"Assetation failed: {file_path}:{line}");

            foreach (var f in trace.GetFrames())
            {
                var m = f.GetMethod();
                var mn = m.Name;
                var l = f.GetFileLineNumber();
                var fp = f.GetFileName();
                Console.WriteLine($"{fp}:{l}");
            }

            //Environment.Exit(1);
        }
    }

    public static void Assert(bool cond, string str)
    {
        if (!cond)
        {
            var trace = new System.Diagnostics.StackTrace(true);
            var frame = trace.GetFrame(1);
            var method = frame.GetMethod();
            var method_name = method.Name;
            var line = frame.GetFileLineNumber();
            var file_path = frame.GetFileName();
            Console.WriteLine($"Assetation failed: {str} {file_path}:{line}");

            foreach (var f in trace.GetFrames())
            {
                var m = f.GetMethod();
                var mn = m.Name;
                var l = f.GetFileLineNumber();
                var fp = f.GetFileName();
                Console.WriteLine($"{fp}:{l}");
            }
            Environment.Exit(1);
        }
    }

    public static void LogError(string msg)
    {
        Console.WriteLine(msg);
    }

    public static void LogWarning(string msg)
    {
        Console.WriteLine(msg);
    }

    public static void LogErrorFormat(string msg, object r)
    {
        Console.WriteLine(msg);
    }
}

public class Renderer : MonoBehaviour
{
    public Material material { get; set; }
    public Bounds bounds { get; set; }

    public ShadowCastingMode shadowCastingMode;
}

static public class Input
{
    public static Vector2Int mouseScrollDelta => new Vector2Int(0, 0);

    public static bool GetKey(KeyCode key)
    {
        return false;
    }

    public static Vector3 mousePosition = new Vector3(0, 0, 0);

    public static bool GetMouseButtonDown(int button)
    {
        return false;
    }

    public static int GetAxis(string s)
    {
        return 0;
    }

    public static bool GetMouseButton(int button)
    {
        return false;
    }
}

namespace UnityEngine.AI
{
    public enum NavMeshPathStatus
    {
        PathComplete
    }

    public class NavMeshBuildSettings
    {
        public int agentTypeID;
        public bool overrideVoxelSize = false;
        public float voxelSize = 0.1f;
    }

    public class NavMeshHit
    {
        public Vector3 position;
        public int mask;
        public bool hit;
    }

    public class NavMeshTriangulation
    {
        public Vector3[] vertices;
        public int[] indices;
    }

    static class NavMesh
    {
        public const int AllAreas = -1;

        public static NavMeshDataInstance AddNavMeshData(NavMeshData data)
        {
            return new NavMeshDataInstance();
        }

        public static void RemoveNavMeshData(NavMeshDataInstance a) { }

        public static NavMeshLinkInstance AddLink(NavMeshLinkData lnk)
        {
            return new NavMeshLinkInstance();
        }

        public static int GetAreaFromName(string name)
        {
            return -1;
        }

        public static int GetSettingsCount()
        {
            return -0;
        }

        public static string GetSettingsNameFromID(int agentTypeID)
        {
            return "";
        }

        public static NavMeshBuildSettings GetSettingsByIndex(int index)
        {
            return new NavMeshBuildSettings();
        }

        public static bool SamplePosition(Vector3 pos, out NavMeshHit hit, float dist, int areas)
        {
            hit = new NavMeshHit();
            hit.position = pos;
            return true;
        }

        static public void CalculatePath(
            Vector3 start_position,
            Vector3 pos,
            int areas,
            NavMeshPath path
        )
        {
            path.corners = new Vector3[2] { start_position, pos };
        }

        static public NavMeshTriangulation CalculateTriangulation()
        {
            return new NavMeshTriangulation();
        }
    }

    public class NavMeshPath
    {
        public Vector3[] corners = new Vector3[0];
        public NavMeshPathStatus status;
    }
}

public static class JsonConvert
{
    public static T DeserializeObject<T>(string json)
    {
        return default(T);
    }

    public static string SerializeObject<T>(T obj)
    {
        return "";
    }

    public static string SerializeObject<T>(T obj, Formatting format)
    {
        return "";
    }
}

public enum Formatting
{
    None,
    Indented
}

public static class Resources
{
    static public T Load<T>(string path)
    {
        return default(T);
    }

    static public T GetBuiltinResource<T>(string path)
    {
        return default(T);
    }
}

public class Slider : MonoBehaviour
{
    public float value;
}

public class ContextMenu : Attribute
{
    public ContextMenu(string str) { }
}

static class NavMesh
{
    public static NavMeshLinkInstance AddLink(NavMeshLinkData lnk)
    {
        return new NavMeshLinkInstance();
    }

    public static void RemoveLink(NavMeshLinkInstance lnk) { }

    public static int GetAreaFromName(string name)
    {
        return -1;
    }

    public static int GetSettingsCount()
    {
        return -0;
    }

    public static string GetSettingsNameFromID(int agentTypeID)
    {
        return "";
    }

    public static UnityEngine.AI.NavMeshBuildSettings GetSettingsByIndex(int index)
    {
        return new UnityEngine.AI.NavMeshBuildSettings();
    }

    public static NavMeshDataInstance AddNavMeshData(NavMeshData data)
    {
        return new NavMeshDataInstance();
    }

    public static void RemoveNavMeshData(NavMeshDataInstance a) { }
}

public static class PlayerPrefs
{
    public static void SetInt(string key, int value) { }

    public static int GetInt(string key, int def)
    {
        return 0;
    }

    public static void SetFloat(string key, float value) { }

    public static float GetFloat(string key, float def)
    {
        return 0;
    }

    public static void SetString(string key, string value) { }

    public static string GetString(string key, string def)
    {
        return "";
    }
}

public enum RenderTextureFormat
{
    RFloat,
    R8,
    RG16,
    RGB565,
    ARGBFloat
}

namespace UnityEngine.Rendering
{
    public enum ShadowCastingMode
    {
        Off
    }
}

namespace Unity
{
    namespace AI
    {
        namespace Navigation { }
    }

    namespace Collections
    {
        public enum Allocator
        {
            TempJob
        }

        public class NativeArray<T>
        {
            T[] array;
            public T this[int index]
            {
                get => GetValue(index);
                set => SetValue(index, value);
            }

            public void SetValue(int index, T obj)
            {
                array[index] = obj;
            }

            public T GetValue(int index)
            {
                return array[index];
            }

            public void Dispose() { }

            public int Count() => array.Count();

            public NativeArray(int i)
            {
                array = new T[i];
            }

            public NativeArray(int i, Allocator alloc)
            {
                array = new T[i];
            }

            public NativeArray<T> GetSubArray(int s, int j)
            {
                var narr = new NativeArray<T>(j);
                for (int i = 0; i < j; i++)
                {
                    narr[i] = this[s + i];
                }
                return narr;
            }
        }
    }

    namespace Jobs
    {
        public class QueryParameters
        {
            public int layerMask;

            public QueryParameters(int layerMask)
            {
                this.layerMask = layerMask;
            }
        }

        class RaycastCommand
        {
            public Vector3 from;
            public Vector3 direction;
            public RaycastHit hit = null;
            public float distance;
            public QueryParameters queryParameters;

            public RaycastCommand(
                Vector3 from,
                Vector3 direction,
                float distance,
                QueryParameters queryParameters
            )
            {
                this.from = from;
                this.direction = direction;
                this.distance = distance;
                this.queryParameters = queryParameters;
            }

            static public JobHandle ScheduleBatch(
                Collections.NativeArray<RaycastCommand> commands_view,
                Collections.NativeArray<RaycastHit> results_view,
                int k
            )
            {
                Debug.Assert(commands_view != null);
                for (int i = 0; i < commands_view.Count(); ++i)
                {
                    var cmd = new RaycastHit();
                    cmd.collider = null;
                    results_view[i] = cmd;
                }

                return new JobHandle();
            }
        }

        public class JobHandle
        {
            public bool Complete() => true;
        }
    }
}

public enum BuiltinRenderTextureType
{
    CameraTarget
}

namespace UnityEngine
{
    static public class Debug
    {
        public static void Log(string msg)
        {
            Console.WriteLine(msg);
        }

        public static void DrawLine(Vector3 p1, Vector3 p2, Color color, int s) { }

        public static void LogErrorFormat(string format, params object[] args) { }

        public static void LogErrorFormat(Object context, string format, params object[] args) { }

        public static void Assert(bool cond)
        {
            if (!cond)
            {
                var trace = new System.Diagnostics.StackTrace(true);
                var frame = trace.GetFrame(1);
                var method = frame.GetMethod();
                var method_name = method.Name;
                var line = frame.GetFileLineNumber();
                var file_path = frame.GetFileName();
                Console.WriteLine($"Assetation failed: {file_path}:{line}");

                foreach (var f in trace.GetFrames())
                {
                    var m = f.GetMethod();
                    var mn = m.Name;
                    var l = f.GetFileLineNumber();
                    var fp = f.GetFileName();
                    Console.WriteLine($"{fp}:{l}");
                }

                Environment.Exit(1);
            }
        }

        public static void Assert(bool cond, string str)
        {
            if (!cond)
            {
                var trace = new System.Diagnostics.StackTrace(true);
                var frame = trace.GetFrame(1);
                var method = frame.GetMethod();
                var method_name = method.Name;
                var line = frame.GetFileLineNumber();
                var file_path = frame.GetFileName();
                Console.WriteLine($"Assetation failed: {str} {file_path}:{line}");

                foreach (var f in trace.GetFrames())
                {
                    var m = f.GetMethod();
                    var mn = m.Name;
                    var l = f.GetFileLineNumber();
                    var fp = f.GetFileName();
                    Console.WriteLine($"{fp}:{l}");
                }
                Environment.Exit(1);
            }
        }

        public static void LogError(string msg)
        {
            Console.WriteLine(msg);
        }

        public static void LogWarning(string msg)
        {
            Console.WriteLine(msg);
        }

        public static void LogErrorFormat(string msg, object r)
        {
            Console.WriteLine(msg);
        }
    }

    namespace SceneManagement
    {
        public class Scene
        {
            public string name;
        }

        public class SceneManager
        {
            public static void LoadScene(string name) { }

            public static AsyncOperation LoadSceneAsync(string name)
            {
                return null;
            }

            public static void UnloadSceneAsync(string name) { }

            public static Scene GetActiveScene()
            {
                return new Scene();
            }

            static public Action<Scene, LoadSceneMode> sceneLoaded;
        }
    }

    public class Font
    {
        public string name;
    }

    namespace SceneManagement { }
}

namespace UnityEngine.Rendering.Universal
{
    public class ScriptableRendererFeature : MonoBehaviour
    {
        public virtual void Create() { }

        public virtual void AddRenderPasses(
            ScriptableRenderer renderer,
            ref RenderingData renderingData
        ) { }
    }
}

// VisualScripting
namespace Unity.VisualScripting
{
    public class Unit { }

    public class EventUnit<T> : Unit { }

    public class ControlInput : Unit { }

    public class ControlOutput : Unit { }

    public class ValueInput : Unit { }

    public class ValueOutput : Unit { }

    public class Flow : Unit { }
}

// GridLayoutGroup
namespace UnityEngine.UI
{
    public enum GridLayoutGroup_Corner
    {
        UpperLeft,
        UpperRight,
        LowerLeft,
        LowerRight
    }

    public enum GridLayoutGroup_Axis
    {
        Horizontal,
        Vertical
    }

    public enum GridLayoutGroup_Constraint
    {
        Flexible,
        FixedColumnCount,
        FixedRowCount
    }

    public class GridLayoutGroup : MonoBehaviour
    {
        public GridLayoutGroup_Corner startCorner;
        public GridLayoutGroup_Axis startAxis;
        public Vector2 cellSize;
        public Vector2 spacing;
        public GridLayoutGroup_Constraint constraint;
        public int constraintCount;
    }
}

//ScriptableRenderer
namespace UnityEngine.Rendering.Universal
{
    public class ScriptableRenderer
    {
        public void EnqueuePass(ScriptableRenderPass pass) { }
    }

    public class ScriptableRenderPass
    {
        public RenderPassEvent renderPassEvent;

        public virtual void Configure(
            CommandBuffer cmd,
            RenderTextureDescriptor cameraTextureDescriptor
        ) { }

        public virtual void Execute(
            ScriptableRenderContext context,
            ref RenderingData renderingData
        ) { }

        public virtual void FrameCleanup(CommandBuffer cmd) { }
    }

    public struct ScriptableRenderContext
    {
        public void ExecuteCommandBuffer(CommandBuffer cmd) { }
    }

    public class RenderTextureDescriptor
    {
        public int width;
        public int height;
        public RenderTextureFormat colorFormat;
        public int depthBufferBits;
        public int msaaSamples;
    }

    public struct RenderingData
    {
        public CameraData cameraData;
    }

    public struct CameraData
    {
        public Camera camera;
    }

    public enum RenderPassEvent
    {
        BeforeRenderingOpaques,
        AfterRenderingOpaques,
        BeforeRenderingTransparents,
        AfterRenderingTransparents
    }
}

// CommandBufferPool
namespace UnityEngine.Rendering
{
    public static class CommandBufferPool
    {
        public static CommandBuffer Get(string name)
        {
            return new CommandBuffer();
        }

        public static void Release(CommandBuffer buf) { }
    }
}

#endif
