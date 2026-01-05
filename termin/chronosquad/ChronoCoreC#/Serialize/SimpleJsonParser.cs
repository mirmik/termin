#if UNITY_64
using UnityEngine;
#endif

using System;
using System.Collections.Generic;
using System.Reflection;

using System.Linq;

static class SimpleJsonParser
{
    public static string SerializeTrentDictionary(
        Dictionary<string, object> dct,
        int tabs = 0,
        bool pretty = true
    )
    {
        string text = "{";

        if (pretty)
        {
            text += "\n";

            for (int i = 0; i < tabs; ++i)
            {
                text += "\t";
            }
        }

        for (int i = 0; i < dct.Count; ++i)
        {
            var pair = dct.ElementAt(i);
            text += "\"" + pair.Key + "\":" + SerializeTrent(pair.Value, tabs + 1, pretty);
            if (i != dct.Count - 1)
            {
                text += ",";
            }

            if (pretty)
            {
                text += "\n";
                for (int j = 0; j < tabs; ++j)
                {
                    text += "\t";
                }
            }
        }

        text += "}";

        return text;
    }

    public static string SerializeTrentList(IList<object> lst, int tabs = 0, bool pretty = true)
    {
        string text = "[";

        if (pretty)
        {
            text += "\n";

            for (int i = 0; i < tabs; ++i)
            {
                text += "\t";
            }
        }

        for (int i = 0; i < lst.Count; ++i)
        {
            text += SerializeTrent(lst[i], tabs + 1, pretty);
            if (i != lst.Count - 1)
            {
                text += ",";
            }

            if (pretty)
            {
                text += "\n";
                for (int j = 0; j < tabs; ++j)
                {
                    text += "\t";
                }
            }
        }

        text += "]";

        return text;
    }

    public static string SerializeTrent(object dct, int tabs = 0, bool pretty = true)
    {
        switch (dct)
        {
            case Dictionary<string, object> sub_dct:
                return SerializeTrentDictionary(sub_dct, tabs + 1, pretty);
            case string str:
                return "\"" + str + "\"";
            case IList<object> lst:
                return SerializeTrentList(lst, tabs + 1, pretty);
            case float f:
                return f.ToString(System.Globalization.CultureInfo.InvariantCulture);
            case null:
                return "null";
            default:
                return dct.ToString();
        }
    }

    public static string DeserializeTrentString(string json, ref int index)
    {
        string result = "";
        index++;
        while (index < json.Length && json[index] != '\"')
        {
            result += json[index];
            index++;
        }
        index++;
        return result;
    }

    public static object DeserializeTrentNumber(string json, ref int index)
    {
        string result = "";
        bool is_float = false;
        while (
            index < json.Length
            && (
                Char.IsDigit(json[index])
                || json[index] == '-'
                || json[index] == '.'
                || json[index] == 'e'
                || json[index] == 'E'
            )
        )
        {
            if (json[index] == '.' || json[index] == 'e')
            {
                is_float = true;
            }
            result += json[index];
            index++;
        }

        try
        {
            if (is_float)
            {
                return double.Parse(result, System.Globalization.CultureInfo.InvariantCulture);
            }

            return double.Parse(result);
        }
        catch (Exception ex)
        {
            Debug.LogError($"Error parsing number ({result}): " + ex.Message);
            throw;
        }
    }

    public static Dictionary<string, object> DeserializeTrentDictionary(string json, ref int index)
    {
        var dict = new Dictionary<string, object>();

        index++;

        while (index < json.Length)
        {
            SkipWhitespace(json, ref index);
            char c1 = json[index];

            if (c1 == '}')
            {
                index++;
                break;
            }

            var key = DeserializeTrentString(json, ref index);
            SkipWhitespace(json, ref index);
            index++;
            var value = DeserializeTrent(json, ref index);

            dict[key] = value;

            SkipWhitespace(json, ref index);
            char c2 = json[index];

            if (c2 == ',')
            {
                index++;
            }
            else if (c2 == '}')
            {
                index++;
                break;
            }
            else
            {
                Debug.LogError($"Unreachable code {c2}");
                break;
            }
        }

        return dict;
    }

    public static MyList<object> DeserializeTrentList(string json, ref int index)
    {
        var list = new MyList<object>();

        index++;

        while (index < json.Length)
        {
            SkipWhitespace(json, ref index);
            char c1 = json[index];

            if (c1 == ']')
            {
                index++;
                break;
            }

            var value = DeserializeTrent(json, ref index);

            list.Add(value);

            SkipWhitespace(json, ref index);
            char c2 = json[index];

            if (c2 == ',')
            {
                index++;
            }
            else if (c2 == ']')
            {
                index++;
                break;
            }
            else
            {
                Debug.LogError($"Unreachable code {c2}");
                break;
            }
        }

        return list;
    }

    static void SkipWhitespace(string json, ref int index)
    {
        while (index < json.Length && Char.IsWhiteSpace(json[index]))
        {
            index++;
        }
    }

    public static object DeserializeMnemonic(string json, ref int index)
    {
        string result = "";
        while (index < json.Length && Char.IsLetter(json[index]))
        {
            result += json[index];
            index++;
        }

        if (result == "null")
        {
            return null;
        }
        else if (result == "true")
        {
            return true;
        }
        else if (result == "false")
        {
            return false;
        }
        else
        {
            throw new Exception("Unknown mnemonic: " + result);
        }
    }

    public static object DeserializeTrent(string json, ref int index)
    {
        SkipWhitespace(json, ref index);
        char c = json[index];

        bool is_alpha = Char.IsLetter(c);
        if (is_alpha)
        {
            return DeserializeMnemonic(json, ref index);
        }

        switch (c)
        {
            case '{':
                return DeserializeTrentDictionary(json, ref index);
            case '[':
                return DeserializeTrentList(json, ref index);
            case '\"':
                return DeserializeTrentString(json, ref index);
            default:
                return DeserializeTrentNumber(json, ref index);
        }
    }

    public static Tuple<int, int> IndexToLineOffset(string text, int index)
    {
        int line = 1;
        int offset = 1;
        for (int i = 0; i < index; ++i)
        {
            if (text[i] == '\n')
            {
                line++;
                offset = 1;
            }
            else
            {
                offset++;
            }
        }
        return new Tuple<int, int>(line, offset);
    }

    public static object DeserializeTrent(string json)
    {
        int index = 0;
        try
        {
            return DeserializeTrent(json, ref index);
        }
        catch (Exception)
        {
            Tuple<int, int> line_offset = IndexToLineOffset(json, index);
            Debug.Log(
                "Error parsing number at line " + line_offset.Item1 + " offset " + line_offset.Item2
            );
            throw;
        }
    }

    public static List<object> ListToTrent<T>(MyList<T> list) where T : ITrentCompatible
    {
        var trent_list = new List<object>();
        foreach (var item in list)
        {
            trent_list.Add(item.ToTrent());
        }
        return trent_list;
    }

    public static List<object> ListToTrent<T>(IList<T> list) where T : ITrentCompatible
    {
        var trent_list = new List<object>();
        foreach (var item in list)
        {
            trent_list.Add(item.ToTrent());
        }
        return trent_list;
    }

    public static List<T> ListFromTrent<T>(IList<object> trent_list) where T : ITrentCompatible
    {
        var list = new List<T>();
        foreach (var item in trent_list)
        {
            if (item is Dictionary<string, object>)
            {
                var trent = item as Dictionary<string, object>;
                var obj = Activator.CreateInstance<T>();
                (obj as ITrentCompatible).FromTrent(trent);
                list.Add(obj);
            }
        }
        return list;
    }

    static public object Vector3ToTrent(Vector3 vec)
    {
        return new List<object> { vec.x, vec.y, vec.z };
    }

    static public Vector3 Vector3FromTrent(object trent)
    {
        var lst = trent as IList<object>;
        return new Vector3((float)(double)lst[0], (float)(double)lst[1], (float)(double)lst[2]);
    }

    static public object QuaternionToTrent(Quaternion quat)
    {
        return new List<object> { quat.x, quat.y, quat.z, quat.w };
    }

    static public List<float> QuaternionFromTrent(object trent)
    {
        var lst = trent as IList<object>;
        return new List<float>
        {
            (float)(double)lst[0],
            (float)(double)lst[1],
            (float)(double)lst[2],
            (float)(double)lst[3]
        };
    }
}

public interface ITrentCompatible
{
    object ToTrent();
    void FromTrent(object trent);
}
