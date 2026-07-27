#if NETSTANDARD2_1
namespace System.Runtime.CompilerServices;

/// <summary>
/// Compiler-recognized attribute missing from the netstandard2.1 reference
/// assembly. The emitted module initializer is supported by modern runtimes.
/// </summary>
[System.AttributeUsage(System.AttributeTargets.Method, Inherited = false)]
internal sealed class ModuleInitializerAttribute : System.Attribute
{
}
#endif
