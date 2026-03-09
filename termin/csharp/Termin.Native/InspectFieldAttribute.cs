using System;

namespace Termin.Native;

/// <summary>
/// Marks a property as an inspectable field for a CSharpComponent.
/// The field will be registered in the native inspect system and
/// appear in the editor inspector panel.
/// </summary>
[AttributeUsage(AttributeTargets.Property)]
public class InspectFieldAttribute : Attribute
{
    /// <summary>
    /// The field path used to identify this field in the inspect system.
    /// </summary>
    public string Path { get; }

    /// <summary>
    /// Display label in the inspector. Defaults to Path if not set.
    /// </summary>
    public string? Label { get; set; }

    /// <summary>
    /// Value kind: "double", "float", "int", "bool", "string", "vec3", etc.
    /// </summary>
    public string Kind { get; set; } = "double";

    /// <summary>
    /// Minimum value (for numeric fields).
    /// </summary>
    public double Min { get; set; } = 0;

    /// <summary>
    /// Maximum value (for numeric fields).
    /// </summary>
    public double Max { get; set; } = 1;

    /// <summary>
    /// Step size (for numeric fields).
    /// </summary>
    public double Step { get; set; } = 0.01;

    public InspectFieldAttribute(string path)
    {
        Path = path;
    }
}
