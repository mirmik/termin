using System;
using System.Collections.Generic;
using System.Reflection;
using System.Runtime.InteropServices;

namespace Termin.Native;

/// <summary>
/// Static runtime that dispatches native component lifecycle callbacks
/// to CSharpComponent instances.  Call Initialize() once at startup,
/// then RegisterType&lt;T&gt;() for each component type.
/// </summary>
public static class CSharpComponentRuntime
{
    // GCHandle IntPtr -> CSharpComponent instance
    private static readonly Dictionary<IntPtr, CSharpComponent> _instances = new();

    // Type name -> factory
    private static readonly Dictionary<string, Func<CSharpComponent>> _factories = new();

    // Type name -> inspectable PropertyInfo[]
    private static readonly Dictionary<string, PropertyInfo[]> _inspectProperties = new();

    private static bool _initialized;

    // Prevent delegates from being collected by GC
    private static readonly List<Delegate> _pinnedDelegates = new();

    // Shared factory callback (one for all types)
    private static FactoryDelegate? _factoryDelegate;
    private static IntPtr _factoryPtr;

    // ====================================================================
    // Delegate types matching C callback signatures
    // ====================================================================

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate void VoidCb(IntPtr csSelf);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate void FloatCb(IntPtr csSelf, float dt);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate IntPtr FactoryDelegate(IntPtr userdata);

    // Inspect callbacks
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate TcValue InspectGetCb(IntPtr obj, IntPtr typeName, IntPtr path);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate void InspectSetCb(IntPtr obj, IntPtr typeName, IntPtr path, TcValue value, TcSceneHandle scene);

    // ====================================================================
    // Public API
    // ====================================================================

    /// <summary>
    /// Initialize the C# component runtime. Must be called once before
    /// any C# components are created (typically at app startup).
    /// </summary>
    public static void Initialize()
    {
        if (_initialized) return;
        _initialized = true;

        // Lifecycle callbacks
        var callbacks = new TerminCore.CSharpCallbacks
        {
            Start              = Pin<VoidCb>(OnStart),
            Update             = Pin<FloatCb>(OnUpdate),
            FixedUpdate        = Pin<FloatCb>(OnFixedUpdate),
            BeforeRender       = Pin<VoidCb>(OnBeforeRender),
            OnDestroy          = Pin<VoidCb>(OnDestroyCallback),
            OnAddedToEntity    = Pin<VoidCb>(OnAddedToEntity),
            OnRemovedFromEntity = Pin<VoidCb>(OnRemovedFromEntity),
            OnAdded            = Pin<VoidCb>(OnAddedCallback),
            OnRemoved          = Pin<VoidCb>(OnRemovedCallback),
            OnSceneInactive    = Pin<VoidCb>(OnSceneInactive),
            OnSceneActive      = Pin<VoidCb>(OnSceneActive),
            RefAdd             = Pin<VoidCb>(OnRefAdd),
            RefRelease         = Pin<VoidCb>(OnRefRelease),
        };
        TerminCore.ComponentSetCSharpCallbacks(ref callbacks);

        // Inspect callbacks
        var getPtr = Pin<InspectGetCb>(InspectGetHandler);
        var setPtr = Pin<InspectSetCb>(InspectSetHandler);
        TerminCore.InspectSetCSharpCallbacks(getPtr, setPtr);

        // Factory
        _factoryDelegate = CSharpFactory;
        _pinnedDelegates.Add(_factoryDelegate);
        _factoryPtr = Marshal.GetFunctionPointerForDelegate(_factoryDelegate);
    }

    /// <summary>
    /// Register a C# component type so it can be created from the native
    /// component registry (e.g. from the inspector "Add Component" menu).
    /// </summary>
    public static void RegisterType<T>(string typeName) where T : CSharpComponent, new()
    {
        Initialize();

        _factories[typeName] = () => new T();

        // Register inspect metadata
        RegisterInspectFields(typeName, typeof(T));

        // Register in native component registry.
        // userdata = pointer to a nul-terminated type name string (leaked intentionally — types are registered once).
        var typeNamePtr = Marshal.StringToHGlobalAnsi(typeName);
        TerminCore.ComponentRegistryRegister(typeName, _factoryPtr, typeNamePtr, (int)ComponentKind.CSharp);
    }

    // ====================================================================
    // Factory — called from native tc_component_registry_create()
    // ====================================================================

    private static IntPtr CSharpFactory(IntPtr userdata)
    {
        var typeName = Marshal.PtrToStringAnsi(userdata);
        if (typeName == null || !_factories.TryGetValue(typeName, out var factory))
            return IntPtr.Zero;

        var component = factory();
        var gcHandle = GCHandle.Alloc(component);
        var gcPtr = GCHandle.ToIntPtr(gcHandle);
        component.GcHandle = gcHandle;

        var nativePtr = TerminCore.ComponentNewCSharp(gcPtr, typeName);
        component.NativePtr = nativePtr;

        _instances[gcPtr] = component;
        return nativePtr;
    }

    // ====================================================================
    // Inspect field registration (via reflection)
    // ====================================================================

    private static void RegisterInspectFields(string typeName, Type type)
    {
        TerminCore.InspectCSharpRegisterType(typeName);

        var props = type.GetProperties(BindingFlags.Public | BindingFlags.Instance);
        var inspectList = new List<PropertyInfo>();

        foreach (var prop in props)
        {
            var attr = prop.GetCustomAttribute<InspectFieldAttribute>();
            if (attr == null) continue;

            inspectList.Add(prop);

            TerminCore.InspectCSharpRegisterField(
                typeName,
                attr.Path,
                attr.Label ?? attr.Path,
                attr.Kind,
                attr.Min,
                attr.Max,
                attr.Step);
        }

        _inspectProperties[typeName] = inspectList.ToArray();
    }

    // ====================================================================
    // Lifecycle callbacks (called from native via function pointers)
    // ====================================================================

    private static void OnStart(IntPtr s)              => Get(s)?.DispatchStart();
    private static void OnUpdate(IntPtr s, float dt)   => Get(s)?.DispatchUpdate(dt);
    private static void OnFixedUpdate(IntPtr s, float dt) => Get(s)?.DispatchFixedUpdate(dt);
    private static void OnBeforeRender(IntPtr s)       => Get(s)?.DispatchBeforeRender();
    private static void OnDestroyCallback(IntPtr s)    => Get(s)?.DispatchOnDestroy();
    private static void OnAddedToEntity(IntPtr s)      => Get(s)?.DispatchOnAddedToEntity();
    private static void OnRemovedFromEntity(IntPtr s)  => Get(s)?.DispatchOnRemovedFromEntity();
    private static void OnAddedCallback(IntPtr s)      => Get(s)?.DispatchOnAdded();
    private static void OnRemovedCallback(IntPtr s)    => Get(s)?.DispatchOnRemoved();
    private static void OnSceneInactive(IntPtr s)      => Get(s)?.DispatchOnSceneInactive();
    private static void OnSceneActive(IntPtr s)        => Get(s)?.DispatchOnSceneActive();

    // Ref counting
    private static void OnRefAdd(IntPtr csSelf)
    {
        // GCHandle already prevents collection — nothing extra needed
    }

    private static void OnRefRelease(IntPtr csSelf)
    {
        if (_instances.TryGetValue(csSelf, out var comp))
        {
            _instances.Remove(csSelf);
            if (comp.GcHandle.IsAllocated)
                comp.GcHandle.Free();
        }
    }

    // ====================================================================
    // Inspect getter / setter callbacks
    // ====================================================================

    private static TcValue InspectGetHandler(IntPtr obj, IntPtr typeNamePtr, IntPtr pathPtr)
    {
        var comp = Get(obj);
        if (comp == null) return TerminCore.ValueNil();

        var typeName = Marshal.PtrToStringAnsi(typeNamePtr);
        var path = Marshal.PtrToStringAnsi(pathPtr);
        if (typeName == null || path == null) return TerminCore.ValueNil();

        var prop = FindProperty(typeName, path);
        if (prop == null) return TerminCore.ValueNil();

        var value = prop.GetValue(comp);
        return ToTcValue(value);
    }

    private static void InspectSetHandler(IntPtr obj, IntPtr typeNamePtr, IntPtr pathPtr,
                                           TcValue value, TcSceneHandle scene)
    {
        var comp = Get(obj);
        if (comp == null) return;

        var typeName = Marshal.PtrToStringAnsi(typeNamePtr);
        var path = Marshal.PtrToStringAnsi(pathPtr);
        if (typeName == null || path == null) return;

        var prop = FindProperty(typeName, path);
        if (prop == null || !prop.CanWrite) return;

        var converted = FromTcValue(value, prop.PropertyType);
        if (converted != null)
            prop.SetValue(comp, converted);
    }

    // ====================================================================
    // Helpers
    // ====================================================================

    private static CSharpComponent? Get(IntPtr csSelf)
    {
        if (csSelf == IntPtr.Zero) return null;
        _instances.TryGetValue(csSelf, out var comp);
        return comp;
    }

    private static IntPtr Pin<T>(T callback) where T : Delegate
    {
        _pinnedDelegates.Add(callback);
        return Marshal.GetFunctionPointerForDelegate(callback);
    }

    private static PropertyInfo? FindProperty(string typeName, string path)
    {
        if (!_inspectProperties.TryGetValue(typeName, out var props))
            return null;

        foreach (var p in props)
        {
            var attr = p.GetCustomAttribute<InspectFieldAttribute>();
            if (attr?.Path == path)
                return p;
        }
        return null;
    }

    private static TcValue ToTcValue(object? value)
    {
        return value switch
        {
            bool b   => TerminCore.ValueBool(b),
            int i    => TerminCore.ValueInt(i),
            long l   => TerminCore.ValueInt(l),
            float f  => TerminCore.ValueFloat(f),
            double d => TerminCore.ValueDouble(d),
            string s => TerminCore.ValueString(s),
            _        => TerminCore.ValueNil(),
        };
    }

    private static object? FromTcValue(TcValue v, Type target)
    {
        if (target == typeof(double))
            return v.Type switch
            {
                TcValueType.Double => v.DoubleValue,
                TcValueType.Float  => (double)v.FloatValue,
                TcValueType.Int    => (double)v.IntValue,
                _ => null,
            };

        if (target == typeof(float))
            return v.Type switch
            {
                TcValueType.Float  => v.FloatValue,
                TcValueType.Double => (float)v.DoubleValue,
                TcValueType.Int    => (float)v.IntValue,
                _ => null,
            };

        if (target == typeof(int))
            return v.Type == TcValueType.Int ? (int)v.IntValue : (object?)null;

        if (target == typeof(long))
            return v.Type == TcValueType.Int ? v.IntValue : (object?)null;

        if (target == typeof(bool))
            return v.Type == TcValueType.Bool ? v.GetBool() : (object?)null;

        if (target == typeof(string))
            return v.Type == TcValueType.String ? v.GetString() : null;

        return null;
    }
}
