using System;
using System.Reflection;
//using System.Text.Json.Serialization;
//using System.Text.Json;
using System.Collections.Generic;
using System.Linq;
using System.IO;
using System.Threading;

#if UNITY_64
using UnityEngine;
#endif

static public class FieldScanner
{
    static object lockobj = new object();

    public class ClassIterateInfo
    {
        public string class_name;
        public string file_path;
        public string text;
        public int start_index;
        public int end_index;
        public int code_generation_marker_begin;
        public int code_generation_marker_end;
        public MyList<FieldInfo> fields = new MyList<FieldInfo>();
        public string generated_code;
        public List<string> lines;
        public List<string> lines_without_generated_code;
        public List<string> lines_modified;
        public string modified_text;
    }

    public static long ModifyHash(long hash, int obj)
    {
        hash = (hash << 5) + hash + obj;
        return hash;
    }

    public static long ModifyHash(long hash, bool obj)
    {
        hash = (hash << 5) + hash + (obj ? 11235 : 543213);
        return hash;
    }

    public static long ModifyHash(long hash, long obj)
    {
        hash = (hash << 5) + hash + obj;
        return hash;
    }

    public static long ModifyHash(long hash, float obj)
    {
        byte[] bytes = BitConverter.GetBytes(obj);
        int int_obj = BitConverter.ToInt32(bytes, 0);
        hash = ModifyHash(hash, int_obj);
        return hash;
    }

    static long StringHash(string str)
    {
        if (str == null)
            return 42314123;

        long hash = 0;
        foreach (char c in str)
        {
            hash = (hash << 5) + hash + c;
        }
        return hash;
    }

    public static long ModifyHash(long hash, string obj)
    {
        hash = ModifyHash(hash, StringHash(obj));
        return hash;
    }

    public static long ModifyHash(long hash, ObjectId obj)
    {
        hash = ModifyHash(hash, StringHash(obj.name));
        return hash;
    }

    public static long ModifyHash(long hash, Type obj)
    {
        hash = ModifyHash(hash, StringHash(obj.Name));
        return hash;
    }

    public static long ModifyHash(long hash, ReferencedPoint obj)
    {
        hash = ModifyHash(hash, obj.GetHashCode());
        return hash;
    }

    public static long ModifyHash(long hash, ReferencedPose obj)
    {
        hash = ModifyHash(hash, obj.GetHashCode());
        return hash;
    }

    public static long ModifyHash(long hash, BracedCoordinates obj)
    {
        hash = ModifyHash(hash, obj.GetHashCode());
        return hash;
    }

    public static long ModifyHash(long hash, ParabolicCurve3d obj)
    {
        hash = ModifyHash(hash, obj.GetHashCode());
        return hash;
    }

    public static long ModifyHash(long hash, RestlessnessParameters obj)
    {
        hash = ModifyHash(hash, obj.GetHashCode());
        return hash;
    }

    public static long ModifyHash(long hash, DistructState obj)
    {
        hash = ModifyHash(hash, obj.GetHashCode());
        return hash;
    }

    public static long ModifyHash(long hash, WalkingType obj)
    {
        hash = ModifyHash(hash, (int)obj);
        return hash;
    }

    public static long ModifyHash(long hash, AnimationType obj)
    {
        hash = ModifyHash(hash, (int)obj);
        return hash;
    }

    public static long ModifyHash(long hash, PathFindingTarget obj)
    {
        hash = ModifyHash(hash, (int)obj);
        return hash;
    }

    public static long ModifyHash(long hash, Animatronic obj)
    {
        hash = ModifyHash(hash, obj.GetHashCode());
        return hash;
    }

    public static long ModifyHash(long hash, HackCommandType obj)
    {
        hash = ModifyHash(hash, obj.GetHashCode());
        return hash;
    }

    public static long ModifyHash(long hash, PatrolStateStruct obj)
    {
        hash = ModifyHash(hash, obj.GetHashCode());
        return hash;
    }

    public static long ModifyHash(long hash, DialogueGraph obj)
    {
        hash = ModifyHash(hash, obj.GetHashCode());
        return hash;
    }

    public static long ModifyHash(long hash, ParasiteMode obj)
    {
        hash = ModifyHash(hash, (int)obj);
        return hash;
    }

    public static long ModifyHash(long hash, Pose obj)
    {
        hash = ModifyHash(hash, obj.GetHashCode());
        return hash;
    }

    public static long ModifyHash(long hash, LookAroundSettings obj)
    {
        hash = ModifyHash(hash, obj.GetHashCode());
        return hash;
    }

    public static long ModifyHash(long hash, CommandSpecificState obj)
    {
        if (obj == null)
            return hash + 123;

        hash = ModifyHash(hash, obj.GetHashCode());
        return hash;
    }

    public static long ModifyHash(long hash, CubicCurve obj)
    {
        hash = ModifyHash(hash, obj.GetHashCode());
        return hash;
    }

    public static long ModifyHash(long hash, Vector3 obj)
    {
        hash = ModifyHash(hash, obj.x);
        hash = ModifyHash(hash, obj.y);
        hash = ModifyHash(hash, obj.z);
        return hash;
    }

    static string GenerateHashCodeFunctionForType(ClassIterateInfo info)
    {
        string result = "";
        result += "public override long HashCode()\n";
        result += "{\n";
        result += "\tlong result = 0;\n";
        foreach (var field in info.fields)
        {
            result += "\tresult = FieldScanner.ModifyHash(result, " + field.Name + ");\n";
        }
        result += "\treturn result;\n";
        result += "}\n";
        return result;
    }

    static string GenerateEqualsFunctionForType(ClassIterateInfo info)
    {
        string result = "";
        result += "public override bool Equals(object obj)\n";
        result += "{\n";
        result += "\tif (obj == null)\n";
        result += "\t\treturn false;\n";
        result += "\tif (obj.GetType() != GetType())\n";
        result += "\t\treturn false;\n";
        result += "\tvar other = obj as " + info.class_name + ";\n";
        result += "\treturn \n";
        foreach (var field in info.fields)
        {
            result += "\t\t" + field.Name + " == other." + field.Name + " && \n";
        }
        result += "true;\n";
        result += "}\n";
        result += "public override int GetHashCode()\n";
        result += "{\n";
        result += "\treturn (int)HashCode();\n";
        result += "}\n";
        return result;
    }

    static string GenerateCodeForType(ClassIterateInfo info)
    {
        string result = "";
        result += "//BEGIN################################################################\n";
        result += "// This code was generated by FieldScanner\n";
        result += "\n";
        result += GenerateHashCodeFunctionForType(info);
        result += "\n";
        result += GenerateEqualsFunctionForType(info);
        result += "//END################################################################\n";
        return result;
    }

    static public List<string> FindAllDerivedTypes(Type maintype)
    {
        var derived_types = GetDerivedTypes(maintype);
        var result = new List<string>();
        foreach (var type in derived_types)
        {
            result.Add(type.Name);
        }
        return result;
    }

    static public List<string> GetFiles(string directory_path)
    {
        var result = new List<string>();
        // iterate directory directory_path recursively
        var files = Directory.GetFiles(directory_path, "*.cs", SearchOption.AllDirectories);

        return files.ToList();
    }

    static public void ReadLines(ClassIterateInfo info)
    {
        info.lines = info.text.Split('\n').ToList();
    }

    static public void MakeLinesWithoutGeneratedCode(ClassIterateInfo info)
    {
        info.lines_without_generated_code = new List<string>();
        info.lines_modified = new List<string>();
        bool inside = false;
        for (int i = 0; i < info.lines.Count; i++)
        {
            if (i == info.code_generation_marker_begin)
                inside = true;
            if (!inside)
                info.lines_without_generated_code.Add(info.lines[i]);
            if (i == info.code_generation_marker_end)
                inside = false;
        }
    }

    static public void MakeLinesWithNewGeneratedCode(ClassIterateInfo info)
    {
        // lines of generated code
        var generated_lines = info.generated_code.Split('\n').ToList();

        // insert generated code before end of class
        var lines = new List<string>();
        for (int i = 0; i < info.lines_without_generated_code.Count; i++)
        {
            if (i == info.end_index)
            {
                foreach (var line in generated_lines)
                {
                    lines.Add(line);
                }
            }
            lines.Add(info.lines_without_generated_code[i]);
        }
        info.lines_modified = lines;
    }

    static public void MakeModifiedText(ClassIterateInfo info)
    {
        info.modified_text = "";
        foreach (var line in info.lines_modified)
        {
            info.modified_text += line + "\n";
        }
    }

    static public Dictionary<string, ClassIterateInfo> GetFilesOfTypes(
        MyList<Type> types,
        List<string> files
    )
    {
        var result = new Dictionary<string, ClassIterateInfo>();
        foreach (var file in files)
        {
            var text = File.ReadAllText(file);
            foreach (var type in types)
            {
                if (
                    text.Contains("class " + type.Name + " ")
                    || text.Contains("class " + type.Name + "\n")
                    || text.Contains("class " + type.Name + "\r")
                )
                {
                    var info = new ClassIterateInfo();
                    info.class_name = type.Name;
                    info.file_path = file;
                    info.text = text;
                    info.fields = GetFieldsFromType(type);
                    info.fields = GetUnicalFields(info.fields);
                    info.generated_code = GenerateCodeForType(info);
                    ReadLines(info);
                    FilterMultipleEmptyLines(info);
                    FindCodeGenerationMarkers(
                        info.lines,
                        out info.code_generation_marker_begin,
                        out info.code_generation_marker_end
                    );
                    MakeLinesWithoutGeneratedCode(info);
                    BeginLastStringOfClass(
                        info,
                        type.Name,
                        out info.start_index,
                        out info.end_index
                    );
                    MakeLinesWithNewGeneratedCode(info);
                    MakeModifiedText(info);
                    result[type.Name] = info;
                }
            }
        }
        return result;
    }

    public static void FilterMultipleEmptyLines(ClassIterateInfo info)
    {
        var lines = info.lines;
        var new_lines = new List<string>();
        bool empty_line = false;

        foreach (var line in lines)
        {
            if (line.Trim() == "")
            {
                if (!empty_line)
                {
                    new_lines.Add(line);
                    empty_line = true;
                }
            }
            else
            {
                new_lines.Add(line);
                empty_line = false;
            }
        }
        info.lines = new_lines;
    }

    public static MyList<FieldInfo> GetUnicalFields(MyList<FieldInfo> fields)
    {
        var result = new MyList<FieldInfo>();
        foreach (var field in fields)
        {
            bool contains = result.Any(f => f.Name == field.Name);
            if (!contains)
                result.Add(field);
        }
        return result;
    }

    static public void ReplaceFile(ClassIterateInfo text)
    {
        var path = text.file_path;
        var new_text = text.modified_text;
        File.WriteAllText(path, new_text);
    }

    static public void BeginLastStringOfClass(
        ClassIterateInfo info,
        string class_name,
        out int start_index,
        out int end_index
    )
    {
        List<string> lines = info.lines_without_generated_code;
        start_index = -1;
        end_index = -1;
        bool found_first = false;
        int parenthesis = 0;

        for (int i = 0; i < lines.Count; i++)
        {
            if (lines[i].Contains("class " + class_name))
                start_index = i;

            if (start_index != -1)
            {
                int open_parenthesis = lines[i].Count(c => c == '{');
                // count of open parenthesis in line
                parenthesis += open_parenthesis;

                if (open_parenthesis > 0)
                    found_first = true;

                // count of close parenthesis in line
                parenthesis -= lines[i].Count(c => c == '}');
            }

            if (start_index != -1 && parenthesis == 0 && found_first)
            {
                end_index = i;
                return;
            }
        }
    }

    static public void FindCodeGenerationMarkers(List<string> lines, out int begin, out int end)
    {
        begin = -1;
        end = -1;
        bool start_found = false;
        bool end_found = false;

        for (int i = 0; i < lines.Count; i++)
        {
            if (lines[i].Trim().StartsWith("//BEGIN"))
            {
                if (start_found)
                    throw new Exception("Multiple //BEGIN markers found");

                start_found = true;
                begin = i;
            }
            if (lines[i].Trim().StartsWith("//END"))
            {
                if (end_found)
                    throw new Exception("Multiple //END markers found");
                end_found = true;
                end = i;
            }
        }
    }

    static Dictionary<Type, MyList<FieldInfo>> GetFieldsFromType_Lazy =
        new Dictionary<Type, MyList<FieldInfo>>();

    static public MyList<Type> GetDerivedTypes(Type maintype)
    {
        var derived_types = new MyList<Type>();
        foreach (var domain_assembly in AppDomain.CurrentDomain.GetAssemblies())
        {
            var assembly_types = domain_assembly
                .GetTypes()
                .Where(type => type.IsSubclassOf(maintype) && !type.IsAbstract);

            derived_types.AddRange(assembly_types);
        }
        return derived_types;
    }

    public static MyList<FieldInfo> GetFieldsFromType(Type type)
    {
        lock (lockobj)
        {
            MyList<FieldInfo> result;
            bool contains = GetFieldsFromType_Lazy.TryGetValue(type, out result);
            if (contains)
                return result;

            result = new MyList<FieldInfo>();

            var fields = type.GetFields(
                BindingFlags.NonPublic | BindingFlags.Public | BindingFlags.Instance
            );

            foreach (var field in fields)
            {
                if (field.GetCustomAttribute<IgnoreRefflectionAttribute>() == null)
                    result.Add(field);
            }

            if (type.BaseType != null)
            {
                var base_type = type.BaseType;
                var base_fields = GetFieldsFromType(base_type);
                foreach (var field in base_fields)
                {
                    result.Add(field);
                }
            }

            GetFieldsFromType_Lazy.Add(type, result);
            return result;
        }
    }

    static public Dictionary<Type, MyList<FieldInfo>> DoScan(Type maintype)
    {
        var fields_of_type = new Dictionary<Type, MyList<FieldInfo>>();
        var derived_types = GetDerivedTypes(maintype);

        foreach (Type type in derived_types)
            fields_of_type.Add(type, GetFieldsFromType(type));

        return fields_of_type;
    }

#if UNITY_64
    static public string SerializeCardToJson(BasicMultipleAction act)
    {
        string json = JsonUtility.ToJson(act);
        return json;
    }

    static public BasicMultipleAction DeserializeCardFromJson(string json)
    {
        var act = JsonUtility.FromJson<BasicMultipleAction>(json);
        return act;
    }
#endif
}
