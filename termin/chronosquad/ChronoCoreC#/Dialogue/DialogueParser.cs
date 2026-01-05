using System.IO;
using System.Collections.Generic;

#if UNITY_64
using UnityEngine;
#endif

public class DialogueNode
{
    public string text;
    public string speaker;
    public string[] options;
    public MyList<DialogueNode> next = new MyList<DialogueNode>();

    public DialogueNode() { }

    public DialogueNode(string text)
    {
        this.text = text;
    }
}

public class DialogueGraph
{
    public MyList<string> icons_names = new MyList<string>();
    public Dictionary<string, Texture2D> icons = new Dictionary<string, Texture2D>();

    public DialogueNode entrance;

    public void CompileIcons()
    {
        foreach (var name in icons_names)
        {
            var texture = MaterialKeeper.Instance.GetTexture(name);
            icons.Add(name, texture);
        }
    }

    public DialogueGraph() { }

    public DialogueGraph(string text)
    {
        DialogueNode entrance = new DialogueNode(text);
        this.entrance = entrance;
    }
}

static class DialogueParser
{
    static string RemoveExtraSpaces(string text)
    {
        string result = "";
        bool space = false;
        foreach (var c in text)
        {
            if (c == ' ')
            {
                if (space)
                    continue;
                space = true;
            }
            else
            {
                space = false;
            }
            result += c;
        }
        return result;
    }

    static string RemoveNewLines(string text)
    {
        string result = "";
        foreach (var c in text)
        {
            if (c == '\n')
                continue;
            if (c == '\r')
                continue;
            result += c;
        }
        return result;
    }

    public static TimelineScriptApplyDialogueGraph ParseJson(string path)
    {
        DialogueGraph graph = new DialogueGraph();
        DialogueNode entrance = null;

        // jsontext
        string jsontext = File.ReadAllText(path);
        var json = SimpleJsonParser.DeserializeTrent(jsontext);
        var dct = json as Dictionary<string, object>;

        // images
        var images = dct["icons"] as MyList<object>;
        foreach (var pair in images)
        {
            var value = pair as string;
            graph.icons_names.Add(value);
        }
        graph.CompileIcons();

        // messages
        var messages = dct["messages"] as MyList<object>;
        foreach (var pair in messages)
        {
            var value = pair as string;
            var split = value.Split('>');
            var no = int.Parse(split[0]) - 1;
            value = split[1];
            value = RemoveNewLines(value);
            value = RemoveExtraSpaces(value);
            var new_entrance = new DialogueNode();
            new_entrance.text = value;
            new_entrance.speaker = images[no] as string;
            new_entrance.next = new MyList<DialogueNode>();
            if (graph.entrance == null)
                graph.entrance = new_entrance;
            else
                entrance.next.Add(new_entrance);
            entrance = new_entrance;
        }

        entrance = graph.entrance;
        while (entrance != null && entrance.next.Count > 0)
        {
            entrance = entrance.next[0];
        }

        return new TimelineScriptApplyDialogueGraph(graph);
    }

    public static TimelineScriptApplyScr ParseScr(string path)
    {
        ScrParser parser = new ScrParser();
        parser.Parse(File.ReadAllText(path));
        return new TimelineScriptApplyScr(parser.result);
    }

    public static TimelineScript Parse(string path)
    {
        var ext = Path.GetExtension(path);
        if (ext == ".json")
            return ParseJson(path);
        else if (ext == ".scr")
            return ParseScr(path);
        else
            return null;
    }
}
